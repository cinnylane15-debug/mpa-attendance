from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date, time, datetime


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "teacher"


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Class ─────────────────────────────────────────────────────────────────────

class ClassCreate(BaseModel):
    name: str
    section: Optional[str] = None
    grade: Optional[str] = None
    teacher_id: Optional[int] = None


class ClassUpdate(BaseModel):
    name: Optional[str] = None
    section: Optional[str] = None
    grade: Optional[str] = None
    teacher_id: Optional[int] = None


class ClassResponse(BaseModel):
    id: int
    name: str
    section: Optional[str] = None
    grade: Optional[str] = None
    teacher_id: Optional[int] = None
    student_count: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Student ───────────────────────────────────────────────────────────────────

class StudentCreate(BaseModel):
    student_id: str
    name: str
    class_id: Optional[int] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    class_id: Optional[int] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    is_active: Optional[bool] = None


class StudentResponse(BaseModel):
    id: int
    student_id: str
    name: str
    class_id: Optional[int] = None
    class_name: Optional[str] = None
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    photo_path: Optional[str] = None
    has_face_embedding: bool = False
    is_active: bool = True
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Attendance ────────────────────────────────────────────────────────────────

class ManualCheckIn(BaseModel):
    student_id: str  # The student's student_id field


class ManualCheckOut(BaseModel):
    student_id: str


class AttendanceResponse(BaseModel):
    id: int
    student_id: int
    student_name: Optional[str] = None
    student_code: Optional[str] = None
    class_name: Optional[str] = None
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None
    date: date
    status: str
    method: str
    confidence: Optional[float] = None
    camera_name: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LiveDetection(BaseModel):
    student_name: str
    student_id: str
    camera_name: str
    confidence: float
    timestamp: datetime


# ── Camera ────────────────────────────────────────────────────────────────────

class CameraCreate(BaseModel):
    name: str
    location: Optional[str] = None
    rtsp_url: str
    is_active: bool = True
    direction: str = "entry"


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    rtsp_url: Optional[str] = None
    is_active: Optional[bool] = None
    direction: Optional[str] = None


class CameraResponse(BaseModel):
    id: int
    name: str
    location: Optional[str] = None
    rtsp_url: str
    is_active: bool
    direction: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Schedule ──────────────────────────────────────────────────────────────────

class ScheduleCreate(BaseModel):
    class_id: int
    day_of_week: int
    start_time: time
    end_time: time
    is_active: bool = True


class ScheduleUpdate(BaseModel):
    day_of_week: Optional[int] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    is_active: Optional[bool] = None


class ScheduleResponse(BaseModel):
    id: int
    class_id: int
    class_name: Optional[str] = None
    day_of_week: int
    start_time: time
    end_time: time
    is_active: bool

    model_config = {"from_attributes": True}


# ── Holiday ───────────────────────────────────────────────────────────────────

class HolidayCreate(BaseModel):
    name: str
    date: date
    description: Optional[str] = None


class HolidayUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[date] = None
    description: Optional[str] = None


class HolidayResponse(BaseModel):
    id: int
    name: str
    date: date
    description: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_students: int
    present_today: int
    absent_today: int
    late_today: int
    attendance_rate: float


class WeeklySummary(BaseModel):
    date: date
    present: int
    absent: int
    late: int


class ClassStats(BaseModel):
    class_id: int
    class_name: str
    total_students: int
    present_today: int
    absent_today: int
    late_today: int
    attendance_rate: float


# ── Export ────────────────────────────────────────────────────────────────────

class ExcelExportRequest(BaseModel):
    start_date: date
    end_date: date
    class_id: Optional[int] = None
