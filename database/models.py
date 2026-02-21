"""Database models for workflow checkpoints and state persistence."""

from sqlalchemy import create_engine, Column, String, Integer, DateTime, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()


class WorkflowCheckpoint(Base):
    """Store checkpoints for Heavy Tick workflow recovery."""
    __tablename__ = 'workflow_checkpoints'
    
    id = Column(Integer, primary_key=True)
    workflow_id = Column(String(255), nullable=False, index=True)
    tick_number = Column(Integer, nullable=False)
    stage = Column(String(50), nullable=False)  # 'monologue', 'goal_selection', etc.
    state = Column(JSON, nullable=False)  # Full state snapshot
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<Checkpoint(workflow={self.workflow_id}, stage={self.stage})>"


class TaskExecution(Base):
    """Track individual task execution for debugging and metrics."""
    __tablename__ = 'task_executions'
    
    id = Column(Integer, primary_key=True)
    task_id = Column(String(255), unique=True, nullable=False)
    workflow_id = Column(String(255), nullable=False, index=True)
    task_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)  # 'PENDING', 'SUCCESS', 'FAILURE', 'RETRY'
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_ms = Column(Integer)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text)
    result = Column(JSON)
    
    def __repr__(self):
        return f"<TaskExecution(task={self.task_name}, status={self.status})>"


# Database connection
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://digital_being:password@localhost:5432/digital_being_db'
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(engine)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()