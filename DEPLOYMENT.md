# 🚂 Railway Deployment Təlimatı

## Ön Hazırlıq

### 1. GitHub Repository
Əvvəlcə kodu GitHub-a push etməlisiniz:

```bash
# Git inicializasiya (əgər edilməyibsə)
git init

# Bütün faylları əlavə et
git add .

# Commit
git commit -m "DSMF bot - initial deployment"

# Remote əlavə et
git branch -M main
git remote add origin https://github.com/Rufat19/sosial_instrucctor.git

# Push
git push -u origin main
```

## Railway-də Deploy

### 2. Railway Proyekti Yarat

1. [Railway.app](https://railway.app) saytına daxil olun
2. GitHub hesabınızla qoşulun
3. **"New Project"** düyməsinə klikləyin
4. **"Deploy from GitHub repo"** seçin
5. `Rufat19/sosial_instrucctor` repository-ni seçin
6. Railway avtomatik build başlayacaq

### 3. Environment Variables Təyin Et

Railway dashboard-da proyektinizi açın və **"Variables"** tab-ına keçin.

Aşağıdakı dəyişənləri əlavə edin:

| Variable Name | Value | Qeyd |
|--------------|-------|------|
| `BOT_TOKEN` | `8143144208:AAEU6TZEtF8At6g3jM_94vLjBJi_pVffMZM` | BotFather-dən alınan token |
| `EXECUTOR_CHAT_ID` | `-4965197205` | İcraçıların qrup ID-si |
| `LANG` | `az` | Dil (Azərbaycan) |

**Vacib:** `DATABASE_URL` Railway tərəfindən avtomatik təyin olunur (PostgreSQL əlavə etdikdə).

### 3.5. PostgreSQL Əlavə Et

1. Railway dashboard-da proyektinizə qayıdın
2. **"+ New"** düyməsinə klik edin
3. **"Database"** → **"Add PostgreSQL"** seçin
4. Railway avtomatik PostgreSQL yaradıb `DATABASE_URL` təyin edəcək
5. Bot avtomatik database cədvəllərini yaradacaq

**Qeyd:** PostgreSQL pulsuz planda 512MB yaddaş verir.

### 4. Deployment Yoxlayın

**Logs tab-ında** bot işə başladığını görəcəksiniz:
```
✅ Database modulu yükləndi
✅ Database cədvəlləri yaradıldı/yoxlandı
✅ Database hazırdır
🚀 DSMF Bot işə başlayır... (Bakı vaxtı)
⏰ Start time: 09.11.2025 15:30:45
Bot işə başlayır...
```

Müraciət gələndə:
```
✅ DB-yə yazıldı: Application ID=1
```

## Railway Konfiqurasiya Faylları

Proyektdə aşağıdakı fayllar Railway üçün hazırlanıb:

- **`Procfile`** - Railway-ə necə işə salmağı göstərir
- **`runtime.txt`** - Python 3.12.0 versiyasını təyin edir
- **`railway.json`** - Deploy konfiqurasiyası
- **`requirements.txt`** - Python paketləri

## Dəyişiklik Etdikdə

Kod dəyişikliyi etdikdə:

```bash
git add .
git commit -m "Bot yenilənməsi"
git push
```

Railway **avtomatik** yenidən deploy edəcək.

## Export Funksionallığı (v0.4.2+)

### CSV Export PostgreSQL-dən

Bot `/export` komandasında müraciətləri CSV formatında export edə bilərlər:

1. **Admin qrupda `/export` yazın**
2. Bot CSV fayl göndərəcək
3. **Excel-də açıb analiz edin:**
   - ID, Full Name, Phone, FIN
   - Form Type (Complaint/Suggestion)
   - Subject and Body
   - Status (Waiting/Overdue/Completed/Rejected)
   - Created Date and Updated Date

**Nümunə CSV:**
```
ID,Full Name,Phone,FIN,Form Type,Subject,Body,Status,Created Date,Updated Date
1,Rasul Babayev,+994773632066,538YB23,Complaint,Road damage,Pothole on gate road,Waiting,10.11.2025 20:54:34,10.11.2025 20:54:34
```

**Rəhbərliyə göstərmə:**
- CSV-ni Excel-ə import et
- Pivot table ilə status-a görə statistika yap
- Graph-larla təqdimat et

## Troubleshooting

### Bot işləmir?

1. **Logs yoxlayın:**
   - Railway dashboard → Deployments → View Logs

2. **Environment variables düzgündür?**
   - Variables tab-ında yoxlayın

3. **Token aktivdir?**
   - BotFather-də botu yoxlayın: `/mybots` → bot seç → API Token

### Polling Conflict Xətası
**Xəta:** `Conflict: terminated by other getUpdates request; make sure that only one bot instance is running`

**Səbəb:** Başqa bot instance-ı hələ işləyir (əvvəlki deployment hələ bitməmişdir)

**Həll:**
1. **Railway Replica-ı kontrol edin:**
   - Deployment settings-də `replicas = 1` olmalıdır
   - Şəkildə replicas sayını kontrol edin

2. **Əvvəlki deployment-ı durdurün:**
   - Railway dashboard → Deployments tab-ında
   - Əvvəlki active deployment-ı tapıb "Cancel" klikləyin
   - Sonra yeni deploy başlayın

3. **Token rotate edin (əgər hələ düzəlməzsə):**
   - BotFather-ə `/mybots` → Bot seç → `/setcommand` → `/newapi`
   - Yeni token-i `.env`-ə yazıb redeploy edin

4. **Restart edin:**
   - Railway dashboard-da **"Restart"** düyməsinə klikləyin

⚠️ **Qeyd:** Bot `drop_pending_updates=True` istifadə edir, bunu avtomatik idarə edir

### Restart lazımdır?

Railway dashboard-da **"Restart"** düyməsinə klikləyin.

## Bot Komandaları

Deploy-dan sonra botunuzu test edin:

- `/start` - Yeni müraciət başlat
- `/help` - Yardım
- `/chatid` - Chat ID-ni öyrən (admin üçün)

## Qiymətləndirmə

Railway **pulsuz plan** ilə:
- 500 saat/ay (24/7 üçün kifayətdir)
- Avtomatik deploy
- HTTPS dəstəyi
- Log monitoring

## Dəstək

Problemlə qarşılaşsanız:
1. Railway logs-u yoxlayın
2. GitHub issues yaradın
3. Botun BotFather-də statusunu yoxlayın
