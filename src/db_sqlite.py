"""
SQLite fallback database - PostgreSQL işləməzsə
"""
import sqlite3
from typing import Optional
import json
import os
from datetime import datetime
from contextlib import contextmanager
from config import logger, BAKU_TZ

SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "data/applications.db")

def init_sqlite_db():
    """SQLite database və cədvəllər yarat"""
    os.makedirs(os.path.dirname(SQLITE_DB_PATH), exist_ok=True)
    
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_telegram_id INTEGER NOT NULL,
                user_username TEXT,
                fullname TEXT NOT NULL,
                phone TEXT NOT NULL,
                fin TEXT NOT NULL,
                id_photo_file_id TEXT,
                form_type TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                notes TEXT,
                reply_text TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        # Blacklist cədvəli
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS blacklisted_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_telegram_id INTEGER NOT NULL UNIQUE,
                reason TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        
        # Index-lər
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fin ON applications(fin)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON applications(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user ON applications(user_telegram_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created ON applications(created_at)")
        
        # Migration: Add reply_text column if it doesn't exist (for existing SQLite dbs)
        cursor.execute("PRAGMA table_info(applications)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'reply_text' not in columns:
            logger.info("🔧 Adding reply_text column to SQLite applications table...")
            try:
                cursor.execute("ALTER TABLE applications ADD COLUMN reply_text TEXT")
                logger.info("✅ reply_text column added to SQLite")
            except Exception as e:
                logger.warning(f"⚠️ Could not add reply_text column: {e}")
        
        conn.commit()
        logger.info(f"✅ SQLite database hazırdır: {SQLITE_DB_PATH}")

@contextmanager
def get_sqlite_connection():
    """SQLite connection context manager"""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row  # Dict kimi əlçatan olsun
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"SQLite error: {e}")
        raise
    finally:
        conn.close()

def save_application_sqlite(
    user_telegram_id: int,
    user_username: str,
    fullname: str,
    phone: str,
    fin: str,
    id_photo_file_id: str,
    form_type: str,
    subject: str,
    body: str,
    created_at: datetime,
) -> dict:
    """Müraciəti SQLite-a yaz"""
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        
        created_str = created_at.strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("""
            INSERT INTO applications (
                user_telegram_id, user_username, fullname, phone, fin,
                id_photo_file_id, form_type, subject, body, status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_telegram_id, user_username, fullname, phone, fin,
            id_photo_file_id, form_type, subject, body, 'pending',
            created_str, created_str
        ))
        
        app_id = cursor.lastrowid
        logger.info(f"✅ SQLite-a yazıldı: ID={app_id}, FIN={fin}")
        
        return {
            "id": app_id,
            "user_telegram_id": user_telegram_id,
            "user_username": user_username,
            "fullname": fullname,
            "phone": phone,
            "fin": fin,
            "form_type": form_type,
            "subject": subject,
            "body": body,
            "status": "pending",
            "created_at": created_str,
        }

def get_all_applications_sqlite() -> list:
    """Bütün müraciətləri gətir"""
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM applications ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_application_by_id_sqlite(app_id: int) -> dict | None:
    """ID ilə tək müraciəti gətir"""
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM applications WHERE id=?", (app_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def export_to_json(output_file: str = "data/applications_export.json"):
    """SQLite database-i JSON-a export et"""
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    applications = get_all_applications_sqlite()
    
    export_data = {
        "export_time": datetime.now(BAKU_TZ).isoformat(),
        "total_count": len(applications),
        "applications": applications
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ JSON export: {output_file} ({len(applications)} müraciət)")
    return output_file

def update_application_status_sqlite(app_id: int, status: str, notes: Optional[str] = None):
    """Status yenilə"""
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        updated_at = datetime.now(BAKU_TZ).strftime('%Y-%m-%d %H:%M:%S')
        
        if notes:
            cursor.execute(
                "UPDATE applications SET status=?, notes=?, updated_at=? WHERE id=?",
                (status, notes, updated_at, app_id)
            )
        else:
            cursor.execute(
                "UPDATE applications SET status=?, updated_at=? WHERE id=?",
                (status, updated_at, app_id)
            )
        
        logger.info(f"✅ SQLite status yeniləndi: ID={app_id}, status={status}")

def count_user_rejections_sqlite(user_telegram_id: int, days: int = 30) -> int:
    from datetime import datetime, timedelta
    cutoff = (datetime.now(BAKU_TZ) - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM applications WHERE user_telegram_id=? AND status='rejected' AND created_at >= ?",
            (user_telegram_id, cutoff)
        )
        row = cursor.fetchone()
        return row["count"] if row else 0

def is_user_blacklisted_sqlite(user_telegram_id: int) -> bool:
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM blacklisted_users WHERE user_telegram_id=?", (user_telegram_id,))
        return cursor.fetchone() is not None

from typing import Optional

def add_user_to_blacklist_sqlite(user_telegram_id: int, reason: Optional[str] = None) -> None:
    from datetime import datetime
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        created = datetime.now(BAKU_TZ).strftime('%Y-%m-%d %H:%M:%S')
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO blacklisted_users (user_telegram_id, reason, created_at) VALUES (?, ?, ?)",
                (user_telegram_id, reason or "Çoxlu imtina", created)
            )
        except Exception as e:
            logger.error(f"Blacklist insert xətası: {e}")

def remove_user_from_blacklist_sqlite(user_telegram_id: int) -> None:
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM blacklisted_users WHERE user_telegram_id=?", (user_telegram_id,))
        conn.commit()

def list_blacklisted_users_sqlite(limit: int = 100) -> list:
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM blacklisted_users ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def search_applications_sqlite(fin: Optional[str] = None, phone: Optional[str] = None) -> list:
    """FIN və ya telefon ilə axtarış"""
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        
        if fin:
            cursor.execute("SELECT * FROM applications WHERE fin=? ORDER BY created_at DESC", (fin.upper(),))
        elif phone:
            cursor.execute("SELECT * FROM applications WHERE phone=? ORDER BY created_at DESC", (phone,))
        else:
            return []
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_statistics_sqlite() -> dict:
    """Statistika"""
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM applications")
        total = cursor.fetchone()["total"]
        
        cursor.execute("SELECT status, COUNT(*) as count FROM applications GROUP BY status")
        by_status = {row["status"]: row["count"] for row in cursor.fetchall()}
        
        cursor.execute("SELECT form_type, COUNT(*) as count FROM applications GROUP BY form_type")
        by_type = {row["form_type"]: row["count"] for row in cursor.fetchall()}
        
        return {
            "total": total,
            "by_status": by_status,
            "by_type": by_type
        }

def get_overdue_applications_sqlite(days: int = 3) -> list:
    """SLA aşan müraciətləri tap (N gündən çox pending/processing)"""
    from datetime import datetime, timedelta
    cutoff_date = (datetime.now(BAKU_TZ) - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM applications WHERE status IN ('pending', 'processing') AND created_at <= ? ORDER BY created_at",
            (cutoff_date,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def count_user_recent_applications_sqlite(user_telegram_id: int, hours: int = 24) -> int:
    """Son N saat içində istifadəçinin müraciət sayını say"""
    from datetime import datetime, timedelta
    cutoff_time = (datetime.now(BAKU_TZ) - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM applications WHERE user_telegram_id=? AND created_at >= ?",
            (user_telegram_id, cutoff_time)
        )
        result = cursor.fetchone()
        return result["count"] if result else 0

def delete_all_applications_sqlite() -> int:
    """Bütün müraciətləri silinə billər (test məlumatları üçün)"""
    with get_sqlite_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM applications")
        conn.commit()
        deleted = cursor.rowcount
        logger.info(f"✅ {deleted} müraciət silindi")
        return deleted
