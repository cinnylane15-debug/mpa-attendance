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
from app.models import Employee, User
from app.schemas import EmployeeCreate, EmployeeUpdate, EmployeeOut
from app.auth import get_current_user

router = APIRouter(prefix="/api/employees", tags=["Employees"])


@router.post("/", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def create_employee(
    payload: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new employee."""
    existing = db.query(Employee).filter(Employee.employee_id == payload.employee_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Employee ID '{payload.employee_id}' already exists",
        )

    employee = Employee(
        employee_id=payload.employee_id,
        name=payload.name,
        department=payload.department,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return EmployeeOut.from_model(employee)


@router.get("/", response_model=List[EmployeeOut])
def list_employees(
    department: Optional[str] = Query(None),
    active_only: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List employees with optional filters."""
    query = db.query(Employee)
    if active_only:
        query = query.filter(Employee.is_active.is_(True))
    if department:
        query = query.filter(Employee.department == department)
    employees = query.order_by(Employee.name).offset(skip).limit(limit).all()
    return [EmployeeOut.from_model(e) for e in employees]


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single employee by database ID."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return EmployeeOut.from_model(employee)


@router.put("/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: int,
    payload: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an employee's details."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(employee, field, value)

    db.commit()
    db.refresh(employee)
    return EmployeeOut.from_model(employee)


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an employee."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    db.delete(employee)
    db.commit()


@router.post("/{employee_id}/upload-face", response_model=EmployeeOut)
def upload_face_photo(
    employee_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a face photo for an employee and compute the face encoding."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Validate file type
    if file.content_type not in ("image/jpeg", "image/png", "image/jpg"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG and PNG images are accepted",
        )

    # Read and save the uploaded file
    contents = file.read()
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    filename = f"{employee.employee_id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(settings.UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(contents)

    # Compute face encoding
    image = face_recognition.load_image_file(filepath)
    encodings = face_recognition.face_encodings(image)

    if len(encodings) == 0:
        os.remove(filepath)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No face detected in the uploaded image. Please upload a clear photo with a visible face.",
        )

    if len(encodings) > 1:
        os.remove(filepath)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Multiple faces detected. Please upload a photo with only one face.",
        )

    # Serialize the encoding as JSON
    encoding_list = encodings[0].tolist()
    employee.face_encoding = json.dumps(encoding_list)
    employee.photo_path = filepath

    db.commit()
    db.refresh(employee)
    return EmployeeOut.from_model(employee)
