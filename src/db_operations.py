"""
Database əlaqə və əməliyyatlar
"""
import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, Optional
from database import Base, Application, ApplicationStatus, FormTypeDB, BlacklistedUser
from config import logger

# Database URL (Railway environment variable-dan)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/dsmf_bot")

# SQLAlchemy engine
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Database-i başlat (cədvəllər yarat)"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database cədvəlləri yaradıldı/yoxlandı")
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
        raise

@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Database session context manager"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        db.close()

def save_application(
    user_telegram_id: int,
    user_username: str,
    fullname: str,
    phone: str,
    fin: str,
    id_photo_file_id: str,
    form_type: str,
    subject: str,
    body: str,
    created_at,
) -> Application:
    """Müraciəti database-ə yaz"""
    with get_db() as db:
        app = Application(
            user_telegram_id=user_telegram_id,
            user_username=user_username,
            fullname=fullname,
            phone=phone,
            fin=fin,
            id_photo_file_id=id_photo_file_id,
            form_type=FormTypeDB.COMPLAINT if form_type == "Şikayət" else FormTypeDB.SUGGESTION,
            subject=subject,
            body=body,
            status=ApplicationStatus.PENDING,
            created_at=created_at,
            updated_at=created_at,
        )
        db.add(app)
        db.flush()
        db.refresh(app)
        # Session bağlanmazdan əvvəl id-ni əldə edək
        app_id = app.id
        logger.info(f"✅ Müraciət database-ə yazıldı: ID={app_id}, FIN={app.fin}")
        # Session-dan ayrılmış obyekt qaytaraq
        db.expunge(app)
        return app

def get_application_by_id(app_id: int) -> Application:
    """ID ilə müraciəti tap"""
    with get_db() as db:
        return db.query(Application).filter(Application.id == app_id).first()

def get_applications_by_user(user_telegram_id: int) -> list[Application]:
    """İstifadəçinin bütün müraciətləri"""
    with get_db() as db:
        return db.query(Application).filter(
            Application.user_telegram_id == user_telegram_id
        ).order_by(Application.created_at.desc()).all()

def get_applications_by_status(status: ApplicationStatus) -> list[Application]:
    """Status üzrə müraciətlər"""
    with get_db() as db:
        return db.query(Application).filter(
            Application.status == status
        ).order_by(Application.created_at.desc()).all()

def update_application_status(app_id: int, status: ApplicationStatus, notes: Optional[str] = None):
    """Müraciət statusunu yenilə"""
    with get_db() as db:
        app = db.query(Application).filter(Application.id == app_id).first()
        if app:
            app.status = status  # type: ignore[assignment]
            if notes:
                app.notes = notes  # type: ignore[assignment]
            db.commit()
            logger.info(f"✅ Müraciət {app_id} statusu yeniləndi: {status.value}")
            return app
        return None

def search_applications(fin: Optional[str] = None, phone: Optional[str] = None) -> list[Application]:
    """FIN və ya telefon ilə axtarış"""
    with get_db() as db:
        query = db.query(Application)
        if fin:
            query = query.filter(Application.fin == fin.upper())
        if phone:
            query = query.filter(Application.phone == phone)
        return query.order_by(Application.created_at.desc()).all()

def is_user_blacklisted(user_telegram_id: int) -> bool:
    """İstifadəçi qara siyahıdadırmı?"""
    with get_db() as db:
        return db.query(BlacklistedUser).filter(BlacklistedUser.user_telegram_id == user_telegram_id).first() is not None

def add_user_to_blacklist(user_telegram_id: int, reason: Optional[str] = None) -> None:
    with get_db() as db:
        existing = db.query(BlacklistedUser).filter(BlacklistedUser.user_telegram_id == user_telegram_id).first()
        if existing:
            return
        db.add(BlacklistedUser(user_telegram_id=user_telegram_id, reason=reason))
        db.commit()

def remove_user_from_blacklist(user_telegram_id: int) -> None:
    with get_db() as db:
        db.query(BlacklistedUser).filter(BlacklistedUser.user_telegram_id == user_telegram_id).delete()
        db.commit()

def count_user_rejections(user_telegram_id: int, days: int = 30) -> int:
    """Son N gündə imtina edilən müraciətlərin sayı"""
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=days)
    with get_db() as db:
        return db.query(Application).filter(
            Application.user_telegram_id == user_telegram_id,
            Application.status == ApplicationStatus.REJECTED,
            Application.created_at >= cutoff,
        ).count()

def list_blacklisted_users(limit: int = 100) -> list[BlacklistedUser]:
    """Son daxil olanlara görə qara siyahı siyahısı"""
    with get_db() as db:
        return db.query(BlacklistedUser).order_by(BlacklistedUser.created_at.desc()).limit(limit).all()

def get_overdue_applications(days: int = 3) -> list[Application]:
    """SLA aşan müraciətləri tap (N gündən çox pending/processing)"""
    from datetime import datetime, timedelta
    cutoff_date = datetime.now() - timedelta(days=days)
    with get_db() as db:
        return db.query(Application).filter(
            Application.status.in_([ApplicationStatus.PENDING, ApplicationStatus.PROCESSING]),
            Application.created_at <= cutoff_date
        ).order_by(Application.created_at).all()

def count_user_recent_applications(user_telegram_id: int, hours: int = 24) -> int:
    """Son N saat içində istifadəçinin müraciət sayını say"""
    from datetime import datetime, timedelta
    cutoff_time = datetime.now() - timedelta(hours=hours)
    with get_db() as db:
        return db.query(Application).filter(
            Application.user_telegram_id == user_telegram_id,
            Application.created_at >= cutoff_time
        ).count()

def export_to_csv(limit: int = 1000) -> str:
    """PostgreSQL-dən bütün müraciətləri CSV formatına çevir"""
    import csv
    import io
    from datetime import datetime
    
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    
    # Header sətri
    writer.writerow([
        "ID", "Tam Ad", "Telefon", "FIN", "Müraciət Tipi", 
        "Mövzu", "Məzmun", "Status", "Yaradılma Tarixi", "Yenilənmə Tarixi"
    ])
    
    # Məlumatları yaz
    with get_db() as db:
        apps = db.query(Application).order_by(Application.created_at.desc()).limit(limit).all()
        for app in apps:
            form_type = "Şikayət" if app.form_type == FormTypeDB.COMPLAINT else "Təklif"
            status_text = app.status.value if app.status is not None else "Naməlum"
            created_str = app.created_at.strftime("%d.%m.%Y %H:%M:%S") if app.created_at is not None else ""
            updated_str = app.updated_at.strftime("%d.%m.%Y %H:%M:%S") if app.updated_at is not None else ""
            
            writer.writerow([
                app.id,
                app.fullname or "",
                app.phone or "",
                app.fin or "",
                form_type,
                app.subject or "",
                app.body or "",
                status_text,
                created_str,
                updated_str,
            ])
    
    csv_content = csv_buffer.getvalue()
    csv_buffer.close()
    return csv_content
