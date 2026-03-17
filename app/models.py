import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Float, Date, ForeignKey, Text,
    Enum as SAEnum,
)
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    viewer = "viewer"


class AttendanceStatus(str, enum.Enum):
    present = "present"
    late = "late"
    half_day = "half_day"
    absent = "absent"


class CheckMethod(str, enum.Enum):
    face_recognition = "face_recognition"
    manual = "manual"
    rtsp_auto = "rtsp_auto"


class CameraDirection(str, enum.Enum):
    entry = "entry"
    exit = "exit"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), default=UserRole.viewer, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    department = Column(String(100), nullable=True)
    face_encoding = Column(Text, nullable=True)  # JSON-serialized numpy array
    photo_path = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    attendance_records = relationship("AttendanceRecord", back_populates="employee")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    check_in = Column(DateTime, nullable=True)
    check_out = Column(DateTime, nullable=True)
    date = Column(Date, nullable=False, index=True)
    status = Column(SAEnum(AttendanceStatus), default=AttendanceStatus.present, nullable=False)
    method = Column(SAEnum(CheckMethod), default=CheckMethod.face_recognition, nullable=False)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    employee = relationship("Employee", back_populates="attendance_records")


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    location = Column(String(200), nullable=True)
    rtsp_url = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    direction = Column(
        SAEnum(CameraDirection), default=CameraDirection.entry, nullable=False
    )
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
