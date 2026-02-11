"""
Konfiqurasiya parametrləri və log qurğuları
"""
import os
import logging
from datetime import datetime
import pytz
from dotenv import load_dotenv
import warnings
from typing import Optional
try:
    # PTB 21.x xüsusi xəbərdarlıq tipi
    from telegram.warnings import PTBUserWarning  # type: ignore
except Exception:
    PTBUserWarning = Warning  # fallback

load_dotenv()

logger = logging.getLogger("dsmf-config")

def setup_logging(level: Optional[str] = None):
    """Mərkəzi log konfiqurasiyası.

    Ətraf mühit dəyişənləri:
      - LOG_LEVEL: DEBUG|INFO|WARNING|ERROR (default: INFO)
      - LOG_HTTP: 0/1 (httpx və Telegram HTTP sorğularını göstər) (default: 0)
      - SUPPRESS_PTB_WARN: 0/1 (PTBUserWarning xəbərdarlıqlarını gizlət) (default: 1)
    """
    lvl = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(
        level=getattr(logging, lvl, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )

    # Səs-küylü logları susdur
    show_http = os.getenv("LOG_HTTP", "0").lower() in ("1", "true", "yes")
    if not show_http:
        for noisy in ("httpx", "telegram.request", "telegram.bot", "telegram.ext._application"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
    # PTB per_message xəbərdarlıqlarını gizlət (istəyə bağlı)
    if os.getenv("SUPPRESS_PTB_WARN", "1").lower() in ("1", "true", "yes"):
        try:
            warnings.filterwarnings("ignore", category=PTBUserWarning)  # type: ignore[arg-type]
        except Exception:
            pass

# Timezone - Bakı vaxtı
BAKU_TZ = pytz.timezone('Asia/Baku')

# Bot parametrləri
BOT_TOKEN = os.getenv("BOT_TOKEN")
EXECUTOR_CHAT_ID = int(os.getenv("EXECUTOR_CHAT_ID", "0"))
LANG = os.getenv("LANG", "az")

# Admin istifadəçiləri (vergüllə ayrılmış ID-lər)
# Nümunə: ADMIN_USER_IDS=123456789,987654321
admin_ids_str = os.getenv("ADMIN_USER_IDS", "6520873307")
ADMIN_USER_IDS = {int(uid.strip()) for uid in admin_ids_str.split(",") if uid.strip()}

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/dsmf_bot")

# Validasiya
if not BOT_TOKEN or BOT_TOKEN == "your_bot_token_here":
    raise ValueError(
        "BOT_TOKEN təyin edilməyib. .env faylında BotFather-dən aldığınız tokeni yazın."
    )

if EXECUTOR_CHAT_ID == 0 or EXECUTOR_CHAT_ID == -1001234567890:
    logger.warning("EXECUTOR_CHAT_ID default dəyərdədir. Real chat ID yazın.")

# Anket məhdudiyyətləri
MIN_NAME_LENGTH = 2
MIN_SUBJECT_LENGTH = 5
MAX_SUBJECT_LENGTH = 150  # Beynəlxalq standart (email subject kimi)
MIN_BODY_LENGTH = 10
MAX_BODY_LENGTH = 350     # Daha yığcam müraciət üçün yeni limit
FIN_LENGTH = 7  # Şəxsiyyət Vəsiqəsi FIN kodu uzunluğu
PIN_MIN_LENGTH = 5  # DYİ PIN uzunluğu (minimum)
PIN_MAX_LENGTH = 6  # DYİ PIN uzunluğu (maksimum)

# Rate limiting - Spam qarşısı
MAX_DAILY_SUBMISSIONS = 3  # İstifadəçi 24 saatda max 3 müraciət göndərə bilər
MAX_MONTHLY_SUBMISSIONS = 3  # İstifadəçi 30 gün ərzində max 3 müraciət göndərə bilər

# Blacklist qaydası - çox sayda imtina olunan müraciətlər
BLACKLIST_REJECTION_THRESHOLD = 5  # Son pəncərədə bu qədər imtina olarsa
BLACKLIST_WINDOW_DAYS = 30         # bu qədər gün ərzində

# Mətnlər (Azərbaycan dili)
MESSAGES = {
    "welcome": (
        "Soyad, ad və ata adınızı yazın \n"
        "(məsələn: Babayev Rüfət Rəsul oğlu).\n"
    ),
    "fullname_error": "Xahiş edirik soyad və adı düzgün daxil edin (ata adı əlavə oluna bilər).",
    "phone_prompt": "📱 Mobil nömrənizi daxil edin (məs.: +994501234567)",
    "phone_error": "Nömrə düzgün formatda deyil (məs.: +994501234567)",
    "id_type_prompt": "🆔 Vəsiqə növünü seçin:",
    "fin_prompt": "🆔 Şəxsiyyət vəsiqənizin FIN kodunu daxil edin (7 simvol)",
    "fin_error": "FIN 7 simvoldan ibarət olmalıdır (latın hərf və rəqəm)",
    "pin_prompt": "🆔 Daimi yaşayış icazəsinizin PİN kodunu daxil edin (5-6 simvol)",
    "pin_error": "PİN 5-6 simvoldan ibarət olmalıdır (latın hərf və rəqəm)",
    "id_photo_prompt": "📸 Şəxsiyyət vəsiqəsinin və ya Daimi yaşayış icazəsi ön tərəfinin şəklini foto kimi göndərin",
    "id_photo_error": "Zəhmət olmasa foto göndərin",
    "form_type_prompt": "📋 Müraciət növünü seçin:",
    "body_prompt": "✍️ Müraciətinizi aydın və qısa şəkildə yazın (max 350 simvol)",
    "body_error": "Mətn çox qısa (min 10) və ya çox uzundur (max 350). Xahiş edirik yenidən göndərin.",
    "confirm_sent": (
        "✅ <b>Müraciətiniz uğurla qeydə alındı</b>\n\n"
        "Sizin müraciətiniz icraçı qrupuna yönləndirilmişdir və ən qısa zamanda cavablandırılacaqdır. "
        "Cavab verildikdə, siz birbaşa bu kanalda bildiriş alacaqsınız.\n\n"
        "<i>Zəhmət olmasa gözləyin. Cavab müddəti 5-7 iş günü arasında ola bilər.</i>"
    ),
    "success": "",
    "cancelled": "❌ Müraciət ləğv edildi",
    "help": "ℹ️ /start ilə yeni müraciət göndərə bilərsiniz. /chatid ilə bu qrup/kanalın ID-sini görə bilərsiniz.",
    "unknown": "⚠️ Anlaşılmadı. Zəhmət olmasa /start yazın.",
    "monthly_limit_exceeded": (
        "⚠️ Bu ay artıq {limit} müraciət göndərmisiniz. "
        "Daha çox müraciət etmək üçün bir az gözləyin və ya əvvəlki cavabları yoxlayın."
    ),
    "weekend_notice": (
        "⚠️ Bu gün Bakı vaxtı ilə şənbə və ya bazar günü olduğu üçün müraciətinizi qəbul edə bilmirik. "
        "Zəhmət olmasa müraciətinizi növbəti iş günündə, Bakı vaxtı ilə saat {start}–{end} aralığında göndərin."
    ),
    "offhours_notice": (
        "⚠️ Bakı vaxtı ilə iş saatlarımız {start}–{end} aralığındadır. "
        "Bu vaxtdan kənarda müraciət qəbul edilmir. Zəhmət olmasa iş vaxtında yenidən müraciət edin."
    ),
}

logger.info(f"Konfiqurasiya yükləndi: {LANG.upper()}")
