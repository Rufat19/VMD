# DSMF Vətəndaş Müraciət Botu  
**Versiya:** 0.4.3  
**Son yeniləmə:** 2025-01-10

Bu layihə vətəndaşlardan mərhələli anket ilə məlumat toplayıb icraçı qrupuna yönləndirir, qrupdakı əməkdaşların inline düymələrlə cavab / imtina etməsinə imkan verir və cavabı vətəndaşa DM ilə çatdırır. Qrup mesajlarında real-time status göstəricisi mövcuddur.

## 📁 Fayl Strukturu
```
sosial_agent/
├── .env                  # Bot konfiqurasiyası (token, chat ID)
├── .env.example          # Nümunə konfiqurasiya faylı
├── .gitignore           # Git ignore faylı
├── requirements.txt     # Python asılılıqları
├── run.py              # Botu işə salmaq üçün əsas fayl
├── README.md           # Bu fayl
└── src/
    ├── bot.py          # Bot əsas kodu
    └── config.py       # Konfiqurasiya və parametrlər
```

## ✨ Xüsusiyyətlər
- **Mərhələli anket:** Ad Soyad, Mobil nömrə, FIN, Şəxsiyyət vəsiqəsi şəkli, Növ (Şikayət/Təklif/Ərizə), Məzmun
- **Məzmun limiti:** Max 1000 simvol (beynəlxalq standartlara uyğun)
- **Qısaldılmış timestamp:** ⏰ 09.11.25 19:21:10 formatında
- **Status sistemi:** Qrup mesajlarında real-time status göstəricisi
  - 🟡 **Gözləyir** - yeni müraciət (0-9 gün)
  - 🔴 **Vaxtı keçir** - 10+ gündür cavabsız (təcili diqqət tələb edir)
  - 🟢 **İcra edildi** - cavablandırıldı
  - ⚫ **İmtina** - rədd edildi
- **İcraçı qrupunda interaktiv düymələr:** ✉️ Cavablandır / 🚫 İmtina
   - Cavab/imtina zamanı status avtomatik yenilənir
   - İcraçının adı status sətirində göstərilir
- **Vətəndaşa DM bildiriş:** Cavab və ya imtina səbəbi birbaşa göndərilir
- **Təsdiqdən sonra müraciətin icraçı superqrupuna yönləndirilməsi** (foto + mətn)
- **PostgreSQL persistensiyası** (lokalda FORCE_SQLITE=1 ilə SQLite)
- **Avtomatik supergroup ID miqrasiyası** (qədim qrup -> -100… supergroup)
- **Bakı vaxtı timezone və timestamp**
- **`/export` CSV export** (PostgreSQL: CSV fayl, SQLite: JSON)
- **Diaqnostika komandaları:** `/ping`, `/chatid`

### Yeni (0.4.3)
- **Üç form növü:** Şikayət, Təklif, və Ərizə
- **Sadələşdirilmiş anket axını:** Mövzu addımı çıxarıldı - vətəndaşlar birbaşa məzmun yazır (mövzu avtomatik məzmundan yaranır)
- **Yaxşılaşdırılmış CSV export:**
  - Azərbaycan dilində başlıqlar və statuslar
  - Bakı vaxtı timezone (UTC+4)
  - Excel üçün telefon nömrələri düzgün formatda (mətn olaraq)
  - UTF-8 BOM dəstəyi (Azərbaycan hərfləri üçün)

### Əvvəlki versiyalar (0.4.2)
- **PostgreSQL CSV Export:** `/export` komndasında PostgreSQL üçün CSV fayl export (ID, Full Name, Phone, FIN, Form Type, Subject, Body, Status, Created Date, Updated Date)
- **English CSV headers:** Excel/LibreOffice-da düzgün görünəş (UTF-8 encoding problemi həll edildi)
- **Rəhbərliyə məlumat:** Admin CSV-ni download edib Excel-də müraciətləri analiz edə bilərlər

### Yeni (0.4.0)
- **SLA xatırlatmaları:** Hər gün 09:00-da 3+ gün cavabsız müraciətlərin siyahısı icraçı qrupuna göndərilir
- **Rate limiting:** İstifadəçi 24 saatda max 3 müraciət (konfiq: `MAX_DAILY_SUBMISSIONS`), adminlər azaddır (`ADMIN_USER_IDS`)
- **Qara siyahı sistemi:** 30 gün ərzində ≥5 imtina alan istifadəçilər avtomatik qara siyahıya düşür (konfiq: `BLACKLIST_*`). `/start` onları bloklayır
- **Admin əmrləri:** `/blacklist`, `/ban <user_id> [səbəb]`, `/unban <user_id>`

## 🔧 Tələblər
- Python 3.10+
- Telegram Bot Token (`BOT_TOKEN`)
- İcraçıların kanalı/qrupu üçün ID (`EXECUTOR_CHAT_ID`)

## 🚀 Sürətli başlama (Windows PowerShell)

### 1️⃣ `.env` faylını konfiqurasiya edin:
```powershell
# .env.example faylını kopyalayın
Copy-Item .env.example .env

# .env faylını açın və konfiqurasiya edin:
# - BOT_TOKEN: BotFather-dən alın (@BotFather)
# - EXECUTOR_CHAT_ID: /chatid komandası ilə öyrənin (bax aşağı)
notepad .env
```

### 2️⃣ Lokal (yalnız SQLite) işə salma:
İstəyirsinizsə PostgreSQL olmadan sürətli test üçün:
```powershell
$env:FORCE_SQLITE="1"
.\.venv\Scripts\python.exe run.py
```

### 3️⃣ Normal işə salma (PostgreSQL varsa):
```powershell
# run.py faylı ilə (tövsiyə olunur)
.\.venv\Scripts\python.exe run.py

# və ya birbaşa
.\.venv\Scripts\python.exe .\src\bot.py
```

## 🔐 Admin Konfigürasyonu

**Admin komandalar:**
- `/blacklist` - Qara siyahıyı göstər
- `/ban <user_id> [səbəb]` - İstifadəçini qara siyahıya əlavə et
- `/unban <user_id>` - Qara siyahıdan çıxart
- `/clearall` - ⚠️ Bütün müraciətləri sil (test məlumatları üçün)
- `/export` - Müraciətləri CSV-ə export et (PostgreSQL)

**Admin istifadəçiləri qorunmuşdur:**
- Yalnız `.env` faylında `ADMIN_USER_IDS`-ə daxil olan istifadəçilər bu komandaları istifadə edə bilərlər
- Hər kəs `/clearall` yazsalar belə, ancaq admin-lər tətbiq edə bilərlər

**Admin əlavə etmə:**
1. `.env` faylını açın
2. `ADMIN_USER_IDS` dəyərini dəyişin (vergüllə ayrılmış ID-lər):
   ```bash
   ADMIN_USER_IDS=123456789,987654321
   ```
3. Botu yenidən başladın

**Istifadəçinin ID-sini necə tapmaq olar:**
1. Istifadəçini bota write et
2. Bot `/start` cavabında user ID-ni göstərəcəyi

## 🆔 Chat ID necə tapılır?

1. BotFather-dən bot yaradın və tokenini alın
2. Botu hədəf kanal/qrupa **admin** kimi əlavə edin
3. Həmin kanalda/qrupda `/chatid` yazın
4. Bot cavabda `Chat ID: -100...` qaytaracaq
5. Bu dəyəri `.env` faylında `EXECUTOR_CHAT_ID` kimi yazın

## 📝 Komandalar
- İstifadəçi:
   - `/start` - Yeni müraciət başlat
   - `/help` - Yardım məlumatı
   - `/chatid` - Cari chat ID-ni göstər
   - `/ping` - Sağlamlıq test
   - `/export` - **Müraciətləri CSV-ə export et** (PostgreSQL) / JSON (SQLite)
- Admin:
   - `/blacklist` - Qara siyahını göstər
   - `/ban <user_id> [səbəb]` - Qara siyahıya əlavə et
   - `/unban <user_id>` - Qara siyahıdan sil

Tam siyahı: baxın `COMMANDS.md`.

## ⚙️ Əlavə qeydlər
- Virtual mühit avtomatik qurulubdur (`.venv/`)
- Paketlər artıq quraşdırılıbdır
- Şəxsi məlumatların emalı yerli qanunvericiliyə uyğun olmalıdır
- Bu repo demo məqsədlidir

## 🔒 Təhlükəsizlik
- `.env` faylını heç vaxt git-ə commit etməyin
- Bot tokenini başqaları ilə paylaşmayın
- İcraçı qrupunu private saxlayın

---

## 🚂 Railway Deployment

### Railway-də deploy etmək üçün addımlar:

1. **GitHub-a push edin:**
   ```powershell
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/Rufat19/sosial_instrucctor.git
   git push -u origin main
   ```

2. **Railway-də yeni proyekt yaradın:**
   - [Railway.app](https://railway.app)-a daxil olun
   - "New Project" → "Deploy from GitHub repo" seçin
   - `sosial_instrucctor` repo-nu seçin

3. **Environment Variables təyin edin:**
   Railway dashboard-da "Variables" bölməsinə daxil olub əlavə edin:
   ```
   BOT_TOKEN=XXXXXXXX:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
   EXECUTOR_CHAT_ID=-1003112434088
   LANG=az
   ```

4. **Deploy başlayacaq:**
   - Railway avtomatik olaraq `requirements.txt`-i yükləyəcək
   - `run.py` faylını işə salacaq
   - Bot 24/7 işləyəcək

### Railway deployment faylları:
- `Procfile` - İşə salma komandası
- `runtime.txt` - Python versiyası
- `railway.json` - Railway konfiqurasiyası

### Logları yoxlamaq:
Railway dashboard → Deployments → View Logs

### Dəyişiklik etdikdə:
```powershell
git add .
git commit -m "Update bot"
git push
```
Railway avtomatik yenidən deploy edəcək.

---

## � Railway Deployment & Database Setup (v0.4.1)

### Automatic PostgreSQL Integration
When you deploy to Railway with both `sosial_agent` and `Postgres` services:

1. **Railway generates DATABASE_URL automatically**
   - Format: `postgresql://user:password@host:port/database`
   - Bot connects via Railway's public proxy (not internal hostname)

2. **Environment Variable Configuration in Railway:**
   - Go to `sosial_agent` service → **Variables** tab
   - Add/update these variables:
     - `BOT_TOKEN` - Telegram bot token from @BotFather
     - `EXECUTOR_CHAT_ID` - Group/channel ID (use `/chatid` command)
     - `LANG` - Set to `az`
     - `DATABASE_URL` - Use **Variable Reference**: `${{Postgres.DATABASE_URL}}`

3. **Fallback to SQLite**
   - If PostgreSQL is unavailable, bot automatically switches to SQLite
   - Set `FORCE_SQLITE=1` to force SQLite mode locally

### Troubleshooting Railway Deployment (v0.4.1 fixes)

#### PostgreSQL Connection Issues
**Problem:** `FATAL: password authentication failed for user "postgres"`

**Solutions:**
1. Ensure `DATABASE_URL` uses Railway's **public proxy** URL (not internal hostname)
2. Use Variable Reference in Railway (`${{Postgres.DATABASE_URL}}`) instead of manual URL
3. Check Railway → Postgres service → **Connect** tab for correct public connection string

#### Polling Conflicts
**Problem:** "Conflict: terminated by other getUpdates request"

**Solutions:**
1. **Check Railway settings:**
   - Settings → Scaling: ensure `replicas = 1`
   - Stop/remove old deployments, keep only latest

2. **Rotate bot token:**
   - Message @BotFather: `/token`
   - Generate new token and update `BOT_TOKEN` in Railway
   - Redeploy

3. **Already mitigated in 0.4.1:**
   - `drop_pending_updates=True` in polling (clears stale requests)
   - Extended timeouts (30s) for network stability
   - Global error handler for cleaner diagnostics

#### Database Issues
**Fixed in 0.4.1:**
- ✅ SQLAlchemy session detach (no more "Instance not bound to Session")
- ✅ Telegram API timeout extended to 30s
- ✅ Async error handler for better logging

---

## �🗄️ Database (PostgreSQL / SQLite Fallback)

Bot bütün müraciətləri PostgreSQL database-də saxlayır. PostgreSQL əlçatan olmadıqda avtomatik SQLite fallback aktivləşir.

### Strukturu:
- `applications` cədvəli
- Hər müraciət: ID, user məlumatları, anket cavabları, status, timestamps
- Ətraflı məlumat üçün: [DATABASE.md](DATABASE.md)

### Fallback sistemi:
1. **PostgreSQL** (əsas) – Railway / prod.
2. **SQLite** (fallback) – FORCE_SQLITE=1 və ya PostgreSQL init xətasında runtime keçid.
3. **JSON export** – SQLite modunda `/export`.

Runtime miqrasiya: supergroup-a keçid xəta mesajından yeni ID aşkar edilir və avtomatik yenilənir.

Versiyalar və dəyişiklik tarixi üçün [CHANGELOG.md](CHANGELOG.md), gələcək plan üçün [ROADMAP.md](ROADMAP.md).

### Railway-də:
1. PostgreSQL avtomatik əlavə olunur
2. `DATABASE_URL` avtomatik təyin olunur (Variable Reference ilə)
3. Bot başlayanda cədvəllər yaranır
4. Əgər PostgreSQL problemi olarsa, SQLite aktivləşir

### Müraciət statusları:
- 🟡 `pending` / **Gözləyir** - Yeni daxil olub (0-9 gün)
- 🔴 **Vaxtı keçir** - 10+ gün keçib, cavab gözləyir (təcili)
- 🟢 `completed` / **İcra edildi** - Cavablandırılıb
- ⚫ `rejected` / **İmtina** - Rədd edilib

**Status yeniləməsi:**
- Qrup mesajında inline düyməyə basıldıqda status real-time yenilənir
- İcraçının username-i status sətirində göstərilir
- Vətəndaşa avtomatik DM göndərilir

### Komandalar:
- `/export` - SQLite database-ni JSON-a export et (yalnız SQLite modunda)
