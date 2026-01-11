
# sosial_agent Telegram Bot üçün Copilot Təlimatı

## Layihə icmalı
Bu Telegram botu vətəndaş müraciətlərini mərhələli anketlə toplayır və icraçı qrupa yönləndirir. Bot real vaxtda status yeniləmələri, qrup üzvləri üçün inline düymələr və istifadəçilərə birbaşa DM bildirişləri dəstəkləyir. Məlumatlar PostgreSQL-də saxlanılır (lokal/dev üçün avtomatik SQLite fallback).

## Əsas Arxitektura və Məlumat Axını
- **Başlanğıc fayl:** `run.py` (əsas işə salıcı) və ya `src/bot.py` (əsas bot məntiqi)
- **Konfiqurasiya:** Bütün gizli parametrlər `.env`-dədir (bax `.env.example`).
- **Verilənlər bazası:**
  - Əsas cədvəl: `applications` (bax `DATABASE.md`)
  - Standart olaraq PostgreSQL; lokal test üçün `FORCE_SQLITE=1` ilə SQLite
  - Bütün DB əməliyyatları `src/db_operations.py` və `src/database.py`-də abstraktlaşdırılıb
- **Bot məntiqi:**
  - İstifadəçi `/start` ilə başlayır (ad, telefon, FIN, şəxsiyyət şəkli, növ, məzmun)
  - İcraçılar qrup mesajlarında inline düymələrlə cavab/imtina edir
  - Statuslar: pending, completed, rejected, overdue (ətraflı README-də)
  - Admin komandaları: `/blacklist`, `/ban`, `/unban`, `/clearall`, `/export` (bax `COMMANDS.md`)
  - Rate limit və qara siyahı məntiqi botda tətbiq olunur

## Developer İş Axınları
- **Lokal işə salma (SQLite):**
  ```powershell
  $env:FORCE_SQLITE="1"
  .\.venv\Scripts\python.exe run.py
  ```
- **Prod işə salma (PostgreSQL):**
  ```powershell
  .\.venv\Scripts\python.exe run.py
  ```
- **Deploy:**
  - Railway: GitHub-a push edin, Railway-ə bağlayın, env dəyişənlərini təyin edin (`BOT_TOKEN`, `EXECUTOR_CHAT_ID`, `DATABASE_URL`)
  - Railway avtomatik `requirements.txt`-i yükləyir və `run.py`-ı işə salır
  - Deploy konfiqurasiyası üçün `Procfile`, `runtime.txt`, `railway.json`-a baxın

## Layihəyə Xas Konvensiyalar və Nümunələr
- **Status sistemi:**
  - Statuslar inline düymələrlə real vaxtda yenilənir
  - Status və icraçının adı qrup mesajında göstərilir
  - Status dəyişdikdə istifadəçiyə DM göndərilir
- **Export:**
  - `/export` komandası: PostgreSQL üçün CSV, SQLite üçün JSON
  - `/export` və `/clearall` yalnız adminlər üçün açıqdır
- **Admin ID-lər:**
  - `.env`-də vergüllə ayrılmış siyahı (`ADMIN_USER_IDS`)
  - Yalnız adminlər destruktiv əməliyyatlar edə bilər
- **Supergroup miqrasiyası:**
  - Bot yeni supergroup ID-lərini avtomatik aşkar edib konfiqurasiya edir
- **Rate limit və qara siyahı:**
  - Admin olmayanlar: 24 saatda max 3 müraciət
  - 30 gün ərzində 5+ imtina alanlar avtomatik qara siyahıya düşür

## İnteqrasiya Nöqtələri
- **Telegram API:**
  - `python-telegram-bot` istifadə olunur (bax `requirements.txt`)
  - Qrup üçün inline düymələr
- **Verilənlər bazası:**
  - SQLAlchemy ORM
  - Alembic (gələcəkdə migration üçün)

## Əsas Fayllar və İstinadlar
- [README.md](../README.md): Xüsusiyyətlər, qurulum, deploy, admin konfiqurasiyası
- [DATABASE.md](../DATABASE.md): DB sxemi, istifadə, troubleshooting
- [COMMANDS.md](../COMMANDS.md): Bütün komanda referansı
- [src/db_operations.py](../src/db_operations.py): DB API
- [src/database.py](../src/database.py): DB modellər/status enumları
- [src/config.py](../src/config.py): Konfiq parametrləri

---
**AI agentlər üçün:**
- Həmişə `.env`-dəki gizli parametrləri və admin ID-ləri yoxlayın
- Bütün DB əməliyyatları üçün `db_operations.py`-dəki API funksiyalarından istifadə edin
- Admin-only komandaların məhdudiyyətlərinə riayət edin
- Status və bildiriş konvensiyalarına əməl edin (istifadəçi və qrup üçün)
- Yuxarıdakı fayllara baxın, nümunə və konvensiyaları oradan gön
