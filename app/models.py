import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Date,
    Float,
    Boolean,
    ForeignKey,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="admin")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    department = Column(String(100), nullable=False)
    face_encoding = Column(Text, nullable=True)  # JSON-serialized numpy array
    photo_path = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    attendance_records = relationship(
        "AttendanceRecord", back_populates="employee", cascade="all, delete-orphan"
    )


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    check_in = Column(DateTime, nullable=True)
    check_out = Column(DateTime, nullable=True)
    date = Column(Date, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="present")  # present, late, absent
    method = Column(String(50), nullable=False, default="face_recognition")
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    employee = relationship("Employee", back_populates="attendance_records")
