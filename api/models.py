"""SQLAlchemy 2 database models for users, simulations, and tamper-evident audit ledger."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from api.database import Base

class UserRole(str, enum.Enum):
    VIEWER = "viewer"
    OFFICER = "officer"
    COORDINATOR = "coordinator"
    ADMIN = "admin"

class AuditAction(str, enum.Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default=UserRole.VIEWER.value, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    simulations = relationship("SimulationRecord", back_populates="user", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="user")
    custom_stocks = relationship("UserCustomStock", back_populates="user", cascade="all, delete-orphan")

class UserCustomStock(Base):
    __tablename__ = "user_custom_stocks"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    district = Column(String(100), nullable=False, index=True)
    medicine = Column(String(100), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    provenance = Column(String(50), default="USER-PROVIDED", nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="custom_stocks")

class SimulationRecord(Base):
    __tablename__ = "simulations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    inputs_json = Column(Text, nullable=False)
    results_hash = Column(String(64), nullable=False)  # SHA-256
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="simulations")
    audit_events = relationship("AuditEvent", back_populates="simulation")

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    simulation_id = Column(String(36), ForeignKey("simulations.id"), nullable=True)
    action = Column(String(20), nullable=False)  # APPROVE or REJECT
    reason_code = Column(String(100), nullable=False)
    plan_hash = Column(String(64), nullable=False)  # SHA-256 of transfer plan
    confidence = Column(Float, nullable=False)
    prev_hash = Column(String(64), nullable=False)  # Previous block SHA-256
    current_hash = Column(String(64), nullable=False)  # Current block SHA-256
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="audit_events")
    simulation = relationship("SimulationRecord", back_populates="audit_events")
