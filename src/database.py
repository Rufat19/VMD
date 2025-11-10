"""
Database models - PostgreSQL
"""
from datetime import datetime
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    BigInteger,
    Enum as SQLEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import enum

Base = declarative_base()

class BlacklistedUser(Base):
    """Çoxlu və ya sui-istifadə tipli imtina edilmiş müraciətlərə görə bloklanmış istifadəçi"""
    __tablename__ = "blacklisted_users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_telegram_id = Column(BigInteger, nullable=False, unique=True, index=True)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    def __repr__(self):
        return f"<BlacklistedUser(user_telegram_id={self.user_telegram_id})>"

class ApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"

class FormTypeDB(str, enum.Enum):
    COMPLAINT = "complaint"
    SUGGESTION = "suggestion"

class Application(Base):
    """Vətəndaş müraciəti"""
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Telegram user məlumatları
    user_telegram_id = Column(BigInteger, nullable=False, index=True)
    user_username = Column(String(255), nullable=True)
    
    # Anket məlumatları
    fullname = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    fin = Column(String(7), nullable=False, index=True)
    id_photo_file_id = Column(String(255), nullable=True)
    
    # Müraciət məlumatları
    form_type = Column(SQLEnum(FormTypeDB), nullable=False)
    subject = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    
    # Status və qeydlər
    status = Column(SQLEnum(ApplicationStatus), default=ApplicationStatus.PENDING, nullable=False, index=True)
    notes = Column(Text, nullable=True)  # Admin qeydləri
    reply_text = Column(Text, nullable=True)  # İcraçının cavab mətnı
    
    # Timestamps (Bakı vaxtı)
    created_at = Column(DateTime, nullable=False, index=True)
    updated_at = Column(DateTime, nullable=False, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<Application(id={self.id}, fin={self.fin}, status={self.status})>"
    
    def to_dict(self):
        """Dict formatına çevir"""
        return {
            "id": self.id,
            "user_telegram_id": self.user_telegram_id,
            "user_username": self.user_username,
            "fullname": self.fullname,
            "phone": self.phone,
            "fin": self.fin,
            "form_type": self.form_type.value,
            "subject": self.subject,
            "body": self.body,
            "status": self.status.value,
            "notes": self.notes,
            "reply_text": self.reply_text,
            "created_at": self.created_at.isoformat() if self.created_at is not None else None,  # type: ignore[union-attr]
            "updated_at": self.updated_at.isoformat() if self.updated_at is not None else None,  # type: ignore[union-attr]
        }
