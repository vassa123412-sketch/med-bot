from datetime import datetime
import os, sys
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from core.config import settings

# Use a local SQLite file in the project root
DB_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "landing.db")
DB_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DB_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

class WebAnalysis(Base):
    __tablename__ = "web_analyses"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    analysis_type = Column(String(20), nullable=False)
    input_text = Column(Text, nullable=True)
    result = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    email = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime, nullable=True)

class WebPayment(Base):
    __tablename__ = "web_payments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    package_size = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    robokassa_inv_id = Column(String(64), nullable=True, index=True)
    status = Column(String(20), default="pending")
    email = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    paid_at = Column(DateTime, nullable=True)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    return SessionLocal()
