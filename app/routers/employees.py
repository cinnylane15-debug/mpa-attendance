import json
import os
import uuid
from typing import List, Optional

import face_recognition
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Employee
from app.schemas import EmployeeCreate, EmployeeUpdate, EmployeeOut
from app.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/employees", tags=["Employees"])


def _employee_to_out(emp: Employee) -> EmployeeOut:
    return EmployeeOut(
        id=emp.id,
        employee_id=emp.employee_id,
        name=emp.name,
        department=emp.department,
        photo_path=emp.photo_path,
        is_active=emp.is_active,
        has_face_encoding=emp.face_encoding is not None,
        created_at=emp.created_at,
    )


@router.get("/", response_model=List[EmployeeOut])
def list_employees(
    department: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    query = db.query(Employee)
    if department:
        query = query.filter(Employee.department == department)
    if is_active is not None:
        query = query.filter(Employee.is_active == is_active)
    employees = query.order_by(Employee.name).offset(skip).limit(limit).all()
    return [_employee_to_out(e) for e in employees]


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(
    employee_id: str,
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    emp = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    return _employee_to_out(emp)


@router.post("/", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: EmployeeCreate,
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
):
    if db.query(Employee).filter(Employee.employee_id == payload.employee_id).first():
        raise HTTPException(status_code=400, detail="Employee ID already exists")

    emp = Employee(
        employee_id=payload.employee_id,
        name=payload.name,
        department=payload.department,
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return _employee_to_out(emp)


@router.put("/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: str,
    payload: EmployeeUpdate,
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
):
    emp = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    if payload.name is not None:
        emp.name = payload.name
    if payload.department is not None:
        emp.department = payload.department
    if payload.is_active is not None:
        emp.is_active = payload.is_active

    db.commit()
    db.refresh(emp)
    return _employee_to_out(emp)


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(
    employee_id: str,
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
):
    emp = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.delete(emp)
    db.commit()


@router.post("/{employee_id}/photo", response_model=EmployeeOut)
def upload_face_photo(
    employee_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _current_user=Depends(require_admin),
):
    """Upload a face photo for an employee. Extracts and stores the face encoding."""
    emp = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Validate file type
    allowed = {"image/jpeg", "image/png", "image/jpg"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG/PNG images are accepted")

    # Read image bytes
    contents = file.read()

    # Save file to disk
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    filename = f"{employee_id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(contents)

    # Extract face encoding
    image = face_recognition.load_image_file(filepath)
    encodings = face_recognition.face_encodings(image)

    if len(encodings) == 0:
        os.remove(filepath)
        raise HTTPException(status_code=400, detail="No face detected in the uploaded image")
    if len(encodings) > 1:
        os.remove(filepath)
        raise HTTPException(
            status_code=400,
            detail="Multiple faces detected. Please upload a photo with a single face",
        )

    # Store encoding as JSON and photo path
    encoding_list = encodings[0].tolist()
    emp.face_encoding = json.dumps(encoding_list)
    emp.photo_path = filepath
    db.commit()
    db.refresh(emp)

    return _employee_to_out(emp)
