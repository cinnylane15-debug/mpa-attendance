import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field


# ── Auth ─────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: str = Field(default="admin", pattern="^(admin|viewer)$")


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


# ── Employee ─────────────────────────────────────────────────────────────

class EmployeeCreate(BaseModel):
    employee_id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    department: str = Field(..., min_length=1, max_length=100)


class EmployeeUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    department: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class EmployeeOut(BaseModel):
    id: int
    employee_id: str
    name: str
    department: str
    photo_path: Optional[str] = None
    has_face_encoding: bool = False
    is_active: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, emp):
        return cls(
            id=emp.id,
            employee_id=emp.employee_id,
            name=emp.name,
            department=emp.department,
            photo_path=emp.photo_path,
            has_face_encoding=emp.face_encoding is not None,
            is_active=emp.is_active,
            created_at=emp.created_at,
        )


# ── Attendance ───────────────────────────────────────────────────────────

class AttendanceOut(BaseModel):
    id: int
    employee_id: int
    employee_name: Optional[str] = None
    employee_code: Optional[str] = None
    check_in: Optional[datetime.datetime] = None
    check_out: Optional[datetime.datetime] = None
    date: datetime.date
    status: str
    method: str
    confidence: Optional[float] = None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class CheckInResponse(BaseModel):
    message: str
    employee_name: str
    employee_id: str
    confidence: float
    attendance_id: int


class CheckOutResponse(BaseModel):
    message: str
    employee_name: str
    employee_id: str
    check_out: datetime.datetime


# ── Dashboard ────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_employees: int
    active_employees: int
    today_present: int
    today_absent: int
    today_checked_out: int
    recent_activity: List[AttendanceOut]
