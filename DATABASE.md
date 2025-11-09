# 🗄️ PostgreSQL Database Təlimatı

## Database Strukturu

### `applications` cədvəli

| Sahə | Tip | Qeyd |
|------|-----|------|
| `id` | INTEGER | Primary key, auto-increment |
| `user_telegram_id` | BIGINT | İstifadəçinin Telegram ID-si |
| `user_username` | VARCHAR(255) | Telegram username |
| `fullname` | VARCHAR(255) | Ad, Soyad, Ata adı |
| `phone` | VARCHAR(20) | Mobil nömrə |
| `fin` | VARCHAR(7) | Şəxsiyyət vəsiqəsi FIN kodu |
| `id_photo_file_id` | VARCHAR(255) | Telegram file_id |
| `form_type` | ENUM | complaint / suggestion |
| `subject` | VARCHAR(500) | Müraciət mövzusu |
| `body` | TEXT | Müraciət mətni |
| `status` | ENUM | pending / processing / completed / rejected |
| `notes` | TEXT | Admin qeydləri |
| `created_at` | TIMESTAMP | Yaranma tarixi (Bakı vaxtı) |
| `updated_at` | TIMESTAMP | Yenilənmə tarixi |

## Railway-də PostgreSQL Quraşdırma

### 1. PostgreSQL əlavə et

Railway dashboard-da:
1. Proyektinizi açın
2. **"+ New"** → **"Database"** → **"Add PostgreSQL"**
3. Railway avtomatik database yaradacaq

### 2. DATABASE_URL avtomatik təyin olunur

Railway `DATABASE_URL` environment variable-ı avtomatik təyin edir.

Format:
```
postgresql://user:password@host:port/database
```

**Qeyd:** Əl ilə heç nə etmək lazım deyil!

### 3. Bot deploy edildikdə

Bot işə düşəndə avtomatik olaraq:
- Cədvəllər yaradılacaq (`applications`)
- Database hazır olacaq

Logda görəcəksiniz:
```
✅ Database modulu yükləndi
✅ Database cədvəlləri yaradıldı/yoxlandı
✅ Database hazırdır
```

## Database Əməliyyatları

### Müraciət yazmaq
```python
from db_operations import save_application

app = save_application(
    user_telegram_id=123456789,
    user_username="rufat",
    fullname="Rüfət Əliyev",
    phone="+994501234567",
    fin="ABC1234",
    id_photo_file_id="file_id",
    form_type="Şikayət",
    subject="Mövzu",
    body="Mətn",
    created_at=datetime.now(BAKU_TZ)
)
```

### ID ilə tapmaq
```python
from db_operations import get_application_by_id

app = get_application_by_id(1)
```

### İstifadəçinin müraciətləri
```python
from db_operations import get_applications_by_user

apps = get_applications_by_user(user_telegram_id=123456789)
```

### Status dəyişmək
```python
from db_operations import update_application_status
from database import ApplicationStatus

update_application_status(
    app_id=1, 
    status=ApplicationStatus.COMPLETED,
    notes="Həll edildi"
)
```

### FIN ilə axtarmaq
```python
from db_operations import search_applications

apps = search_applications(fin="ABC1234")
```

## Railway Database Management

### Database-ə qoşulmaq

Railway dashboard-da PostgreSQL servisinə daxil olun:
1. **"Connect"** tab-ı
2. Psql command kopyalayın:
```bash
psql postgresql://user:pass@host:port/database
```

### SQL sorğuları

```sql
-- Bütün müraciətlər
SELECT * FROM applications ORDER BY created_at DESC;

-- Pending statuslu müraciətlər
SELECT * FROM applications WHERE status = 'pending';

-- FIN ilə axtarış
SELECT * FROM applications WHERE fin = 'ABC1234';

-- Statistika
SELECT 
    form_type, 
    status, 
    COUNT(*) as count 
FROM applications 
GROUP BY form_type, status;
```

## Lokal Test (Optional)

Lokal PostgreSQL quraşdırıbsınızsa:

```bash
# PostgreSQL başlat
# Windows: pg_ctl start

# Database yarat
createdb dsmf_bot

# .env faylında
DATABASE_URL=postgresql://localhost:5432/dsmf_bot

# Bot işə sal
python run.py
```

## Troubleshooting

### "Connection refused" xətası?
- Railway-də PostgreSQL servisi işləyir?
- `DATABASE_URL` variable təyin olunub?

### Cədvəl yaranmır?
- Logda error yoxlayın
- SQLAlchemy düzgün quraşdırılıb?

### Data görünmür?
```python
# Console-da test et:
from db_operations import get_applications_by_status
from database import ApplicationStatus

apps = get_applications_by_status(ApplicationStatus.PENDING)
print(len(apps), "müraciət tapıldı")
```

## Backup

Railway automatic backup edir, amma əlavə:

```bash
# Export
pg_dump $DATABASE_URL > backup.sql

# Import
psql $DATABASE_URL < backup.sql
```

## Migration (Gələcək)

Database strukturunu dəyişdikdə Alembic istifadə edilə bilər:
```bash
pip install alembic
alembic init migrations
# Configure alembic.ini
alembic revision --autogenerate -m "description"
alembic upgrade head
```
