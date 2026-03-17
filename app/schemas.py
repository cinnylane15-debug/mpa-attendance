import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from app.models import UserRole, AttendanceStatus, CheckMethod, CameraDirection


# -- Auth / User ---------------------------------------------------------------

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=6)
    role: UserRole = UserRole.viewer


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: UserRole
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None


# -- Employee ------------------------------------------------------------------

class EmployeeCreate(BaseModel):
    employee_id: str = Field(..., max_length=50)
    name: str = Field(..., max_length=200)
    department: Optional[str] = Field(None, max_length=100)


class EmployeeUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    department: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class EmployeeOut(BaseModel):
    id: int
    employee_id: str
    name: str
    department: Optional[str]
    photo_path: Optional[str]
    is_active: bool
    has_face_encoding: bool = False
    created_at: datetime.datetime

    class Config:
        from_attributes = True


# -- Attendance ----------------------------------------------------------------

class AttendanceRecordOut(BaseModel):
    id: int
    employee_id: int
    employee_name: Optional[str] = None
    check_in: Optional[datetime.datetime]
    check_out: Optional[datetime.datetime]
    date: datetime.date
    status: AttendanceStatus
    method: CheckMethod
    confidence: Optional[float]
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class FaceCheckInResponse(BaseModel):
    success: bool
    message: str
    employee_name: Optional[str] = None
    employee_id: Optional[str] = None
    confidence: Optional[float] = None
    attendance_id: Optional[int] = None


class CheckOutRequest(BaseModel):
    employee_id: str


class CheckOutResponse(BaseModel):
    success: bool
    message: str
    employee_name: Optional[str] = None
    check_out: Optional[datetime.datetime] = None


class AttendanceReportQuery(BaseModel):
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None
    employee_id: Optional[str] = None
    department: Optional[str] = None


# -- Camera --------------------------------------------------------------------

class CameraCreate(BaseModel):
    name: str = Field(..., max_length=200)
    location: Optional[str] = Field(None, max_length=200)
    rtsp_url: str = Field(..., max_length=500)
    direction: CameraDirection = CameraDirection.entry


class CameraUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    location: Optional[str] = Field(None, max_length=200)
    rtsp_url: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    direction: Optional[CameraDirection] = None


class CameraResponse(BaseModel):
    id: int
    name: str
    location: Optional[str]
    rtsp_url: str
    is_active: bool
    direction: CameraDirection
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class CameraStatusResponse(BaseModel):
    id: int
    name: str
    location: Optional[str]
    direction: CameraDirection
    is_active: bool
    is_processing: bool
    last_frame_at: Optional[datetime.datetime] = None


class LiveDetection(BaseModel):
    employee_name: str
    employee_id: str
    camera_name: str
    camera_location: Optional[str]
    direction: CameraDirection
    confidence: float
    detected_at: datetime.datetime


# -- Dashboard -----------------------------------------------------------------

class DashboardStats(BaseModel):
    total_employees: int
    active_employees: int
    today_present: int
    today_absent: int
    today_late: int
    recent_activity: List[AttendanceRecordOut]
