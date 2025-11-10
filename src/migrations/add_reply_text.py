"""
Migration: Add reply_text column to applications table
Məqsəd: İcraçının cavab mətnini saxlamaq üçün yeni sütun əlavə et
"""
import os
from sqlalchemy import create_engine, text
from config import logger

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/dsmf_bot")

def run_migration():
    """Add reply_text column to applications table if it doesn't exist"""
    engine = create_engine(DATABASE_URL, echo=False)
    
    try:
        with engine.connect() as conn:
            # Check if column already exists
            result = conn.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='applications' AND column_name='reply_text'
            """))
            
            if result.fetchone():
                logger.info("✅ reply_text column already exists")
                return True
            
            # Add the column
            conn.execute(text("""
                ALTER TABLE applications 
                ADD COLUMN reply_text TEXT NULL
            """))
            conn.commit()
            logger.info("✅ reply_text column added successfully")
            return True
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False
    finally:
        engine.dispose()

if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from config import setup_logging
    setup_logging()
    
    success = run_migration()
    sys.exit(0 if success else 1)
