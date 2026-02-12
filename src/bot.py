import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Any, Dict
from datetime import datetime

import phonenumbers
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.error import Conflict
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ConversationHandler,
    filters,
    CallbackQueryHandler,
)

from config import (
    BOT_TOKEN,
    EXECUTOR_CHAT_ID,
    MESSAGES,
    MIN_NAME_LENGTH,
    MIN_SUBJECT_LENGTH,
    MAX_SUBJECT_LENGTH,
    MIN_BODY_LENGTH,
    MAX_BODY_LENGTH,
    FIN_LENGTH,
    PIN_MIN_LENGTH,
    PIN_MAX_LENGTH,
    BAKU_TZ,
    MAX_DAILY_SUBMISSIONS,
    MAX_MONTHLY_SUBMISSIONS,
    ADMIN_USER_IDS,
    setup_logging,
)
import re
from telegram.error import BadRequest

setup_logging()
logger = logging.getLogger("dsmf-bot")
EXECUTOR_CHAT_ID_RT = EXECUTOR_CHAT_ID  # Runtime-da yenilənə bilən icraçı chat ID

# Ümumi error handler – PTB daxili səhvləri daha aydın loglamaq üçün
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        u = update  # type: ignore[assignment]
        user = getattr(getattr(u, "effective_user", None), "id", None)
        chat = getattr(getattr(u, "effective_chat", None), "id", None)
    except Exception:
        user = chat = None
    
    # Polling conflict xətası üçün xüsusi idarəetmə
    error = context.error
    if error and isinstance(error, Conflict):
        logger.warning(
            "⚠️ Polling Conflict: Başqa bot instance-ı işləyir. "
            "Railway-də yalnız 1 replica olmalıdır, ya da əvvəlki deployment-ı durdurmalısınız."
        )
        return  # Bu xətaları mute edirik
    
    logger.error(
        "Unhandled error. user=%s chat=%s", user, chat, exc_info=context.error
    )

# İstifadəçi məlumatları üçün təhlükəsiz köməkçi
def _ud(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
    """Return a mutable user_data dict always (for type checker)."""
    d = getattr(context, "user_data", None)
    if d is None:
        try:
            context.user_data = {}  # type: ignore[attr-defined]
            d = context.user_data
        except Exception:
            d = {}
    if not isinstance(d, dict):  # safety
        d = {}
        context.user_data = d  # type: ignore[attr-defined]
    return d

# Database yüklənməsi (PostgreSQL əsas, SQLite fallback); lokal test üçün FORCE_SQLITE dəstəyi
DB_ENABLED = False
USE_SQLITE = False

import os as _os
_FORCE_SQLITE = _os.getenv("FORCE_SQLITE", "0").lower() in ("1", "true", "yes") or _os.getenv("DB_MODE", "").lower() == "sqlite"

if _FORCE_SQLITE:
    try:
        from db_sqlite import (
            save_application_sqlite,
            init_sqlite_db,
            export_to_json as sqlite_export_json,
        )
        DB_ENABLED = True
        USE_SQLITE = True
        logger.info("✅ FORCE_SQLITE aktivdir; SQLite istifadə olunacaq")
    except ImportError as e2:
        logger.error(f"❌ SQLite yüklənmədi: {e2}. DB deaktivdir.")
        DB_ENABLED = False
else:
    try:
        from db_operations import save_application, init_db
        DB_ENABLED = True
        logger.info("✅ PostgreSQL modulu yükləndi")
    except ImportError as e:
        logger.warning(f"⚠️ PostgreSQL yüklənmədi: {e}")
        try:
            from db_sqlite import (
                save_application_sqlite,
                init_sqlite_db,
                export_to_json as sqlite_export_json,
            )
            DB_ENABLED = True
            USE_SQLITE = True
            logger.info("✅ SQLite fallback aktivləşdi")
        except ImportError as e2:
            logger.error(f"❌ SQLite də yüklənmədi: {e2}. DB deaktivdir.")
            DB_ENABLED = False

class FormType(str, Enum):
    COMPLAINT = "Şikayət"
    SUGGESTION = "Təklif"
    APPLICATION = "Ərizə"

class States(Enum):
    FULLNAME = auto()
    PHONE = auto()
    ID_TYPE = auto()  # Şəxsiyyət vəsiqəsi vs DYİ seçimi
    FIN = auto()
    PIN = auto()  # DYİ üçün PIN (5-6 simvol)
    ID_PHOTO = auto()
    FORM_TYPE = auto()
    SUBJECT = auto()
    BODY = auto()
    CONFIRM = auto()
    EXEC_REPLY_TEXT = auto()
    EXEC_REJECT_REASON = auto()
    EXEC_EDIT_REPLY_TEXT = auto()

@dataclass
class ApplicationData:
    fullname: Optional[str] = None
    phone: Optional[str] = None
    id_type: Optional[str] = None  # "ID" (Şəxsiyyət Vəsiqəsi) və ya "DYI" (Daimi yaşayış icazəsi)
    code: Optional[str] = None  # FIN (7 simvol) və ya PIN (5-6 simvol)
    fin: Optional[str] = None  # Uyğunluq üçün (fin = code)
    id_photo_file_id: Optional[str] = None
    form_type: Optional[FormType] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    timestamp: Optional[datetime] = None
    username: Optional[str] = None  # Telegram username
    user_telegram_id: Optional[int] = None  # Telegram user ID

    def summary_text(self, include_time: bool = True) -> str:
        # ID növü etiketini dinamik göstər
        id_label = "FİN" if self.id_type == "ID" else "PİN"
        code_display = f"{id_label}: {self.code}" if self.code else ""
        
        # Tarix formatı
        time_str = ""
        if self.timestamp:
            if include_time:
                time_str = f"⏰Müraciət tarixi: {self.timestamp.strftime(' %d.%m.%Y  (%H:%M:%S)')}"
            else:
                time_str = f"⏰Müraciət tarixi: {self.timestamp.strftime('%d.%m.%Y')}"
        
        return (
            f"👤 {self.fullname}\n"
            f"📱 Mobil nömrə: {self.phone}\n"
            f"#️⃣ {code_display}\n"
            f"✍️ Müraciət mətni: {self.body}\n"
            f"\n📧 @{self.username}\n"
            f"🆔: {self.user_telegram_id}\n"
            f"{time_str}"
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ADMIN_USER_IDS
    msg = update.effective_message
    # Diaqnostika üçün loq (istifadəçi və çat məlumatları)
    uid = getattr(update.effective_user, "id", None)
    cid = getattr(update.effective_chat, "id", None)
    ctype = getattr(update.effective_chat, "type", None)
    logger.info(f"/start from user_id={uid} chat_id={cid} chat_type={ctype}")
    if not msg:
        logger.warning("/start çağırışı message obyektisiz gəldi")
        return ConversationHandler.END

    current_baku = datetime.now(BAKU_TZ)
    is_admin = uid in ADMIN_USER_IDS if uid else False
    logger.info(f"Admin check: is_admin={is_admin}")

    # Qara siyahı yoxlaması
    if uid and DB_ENABLED:
        try:
            from config import ADMIN_USER_IDS
            if uid not in ADMIN_USER_IDS:
                blacklisted = False
                if USE_SQLITE:
                    from db_sqlite import is_user_blacklisted_sqlite
                    blacklisted = is_user_blacklisted_sqlite(uid)  # type: ignore[possibly-unbound]
                else:
                    from db_operations import is_user_blacklisted
                    blacklisted = is_user_blacklisted(uid)  # type: ignore[possibly-unbound]
                if blacklisted:
                    await msg.reply_text(
                        "⚠️ Müraciətləriniz müvəqqəti qəbul edilmir. Xahiş edirik daha sonra yenidən yoxlayın.",
                        reply_markup=ReplyKeyboardRemove(),
                    )
                    return ConversationHandler.END
        except Exception as e:
            logger.error(f"Blacklist yoxlaması xətası: {e}")
    
    # Deep link parametrləri: reply_<id> və reject_<id>
    try:
        args = context.args if context.args else []
    except Exception:
        args = []
    if args:
        param = args[0]
        if isinstance(param, str) and param.startswith("reply_"):
            try:
                app_id = int(param.split("_", 1)[1])
                if context.user_data is not None:
                    context.user_data["exec_app_id"] = app_id
                # Müraciət xülasəsini DM-də göstər və cavabı istə
                app_text: Optional[str] = None
                sqlite_photo_id: Optional[str] = None
                if USE_SQLITE:
                    from db_sqlite import get_application_by_id_sqlite
                    app_data = get_application_by_id_sqlite(app_id)
                    if app_data:
                        time_str = str(app_data.get('created_at', ''))
                        app_text = (
                            "📋 Müraciət xülasəsi:\n"
                            f"👤 {app_data.get('fullname', '')}\n"
                            f"📱 Mobil nömrə: {app_data.get('phone', '')}\n"
                            f"🆔 FIN: {app_data.get('fin', '')}\n"
                            f"✍️ Məzmun: {app_data.get('body', '')}\n\n"
                            f"⏰ {time_str}\n"
                            "━━━━━━━━━━━━━━━━━━━━\n"
                            "📝 Cavab mətni yazın:"
                        )
                        raw = app_data.get('id_photo_file_id')
                        if isinstance(raw, str) and raw:
                            sqlite_photo_id = raw
                else:
                    from db_operations import get_application_by_id
                    app = get_application_by_id(app_id)
                    if app:
                        try:
                            from datetime import timezone
                            dt = app.created_at
                            if dt is not None and getattr(dt, 'tzinfo', None) is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            time_str = dt.astimezone(BAKU_TZ).strftime('%d.%m.%y %H:%M:%S') if dt is not None else ''  # type: ignore[union-attr]
                        except Exception:
                            time_str = app.created_at.strftime('%d.%m.%y %H:%M:%S') if (app.created_at is not None) else ''  # type: ignore[union-attr]
                        app_text = (
                            "📋 Müraciət xülasəsi:\n"
                            f"👤 {app.fullname}\n"
                            f"📱 Mobil nömrə: {app.phone}\n"
                            f"🆔 FIN: {app.fin}\n"
                            f"✍️ Məzmun: {app.body}\n\n"
                            f"⏰ {time_str}\n"
                            "━━━━━━━━━━━━━━━━━━━━\n"
                            "📝 Cavab mətni yazın:"
                        )
                if app_text:
                    if sqlite_photo_id:
                        await msg.reply_photo(photo=sqlite_photo_id, caption=app_text)
                    else:
                        await msg.reply_text(app_text)
                # State-i əsas exec_conv_reply izləyir (per_user). Burada dialoqa keçmirik.
                return ConversationHandler.END
            except Exception:
                pass
        elif isinstance(param, str) and param.startswith("reject_"):
            try:
                app_id = int(param.split("_", 1)[1])
                if context.user_data is not None:
                    context.user_data["exec_app_id"] = app_id
                notice = "📋 Müraciət xülasəsi göndərildi.\n👇 İmtina səbəbini yazın:"
                await msg.reply_text(notice)
                # State-i əsas exec_conv_reject izləyir (per_user). Burada dialoqa keçmirik.
                return ConversationHandler.END
            except Exception:
                pass
        elif isinstance(param, str) and param.startswith("edit_"):
            try:
                app_id = int(param.split("_", 1)[1])
                if context.user_data is not None:
                    context.user_data["exec_app_id"] = app_id
                # Mövcud cavabı göstər
                existing_text = None
                if USE_SQLITE:
                    from db_sqlite import get_application_by_id_sqlite
                    app_data = get_application_by_id_sqlite(app_id)
                    if app_data:
                        existing_text = (app_data.get('reply_text') or '') if isinstance(app_data, dict) else ''
                else:
                    from db_operations import get_application_by_id
                    app = get_application_by_id(app_id)
                    if app:
                        try:
                            existing_text = app.reply_text  # type: ignore[attr-defined]
                        except Exception:
                            existing_text = None
                existing_text_str = str(existing_text) if existing_text is not None else ""
                if len(existing_text_str) > 0:
                    await msg.reply_text(f"Mövcud cavab:\n\n{existing_text_str}\n\n✏️ Yeni cavabı yazın:")
                else:
                    await msg.reply_text("✏️ Yeni cavabı yazın:")
                # State-i per-user edit conv izləyir
                return ConversationHandler.END
            except Exception:
                pass

    await msg.reply_text(
        MESSAGES["welcome"],
        reply_markup=ReplyKeyboardRemove(),
    )
    app_data = ApplicationData()
    app_data.username = update.effective_user.username if update.effective_user else None
    app_data.user_telegram_id = update.effective_user.id if update.effective_user else None
    app_data.timestamp = datetime.now(BAKU_TZ)
    _ud(context)["app"] = app_data
    return States.FULLNAME

async def collect_fullname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text or not msg.text.strip():
        return States.FULLNAME
    # Ad soyad normalizasiyası: artıq boşluqları sil və standartlaşdır
    name = " ".join(msg.text.split()).strip()
    if len(name.split()) < MIN_NAME_LENGTH:
        await msg.reply_text(MESSAGES["fullname_error"])
        return States.FULLNAME
    _ud(context).setdefault("app", ApplicationData()).fullname = name
    await msg.reply_text(MESSAGES["phone_prompt"])
    return States.PHONE

def validate_az_phone(number: str) -> bool:
    try:
        parsed = phonenumbers.parse(number, None)
        return phonenumbers.is_valid_number(parsed) and number.startswith("+994")
    except Exception:
        return False

async def collect_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return States.PHONE
    phone = msg.text.strip()
    if not validate_az_phone(phone):
        await msg.reply_text(MESSAGES["phone_error"])
        return States.PHONE
    _ud(context).setdefault("app", ApplicationData()).phone = phone
    # ID_TYPE seçiminə keç (Şəxsiyyət Vəsiqəsi vs DYİ)
    buttons = [
        [InlineKeyboardButton(" 📄 Şəxsiyyət Vəsiqəsi", callback_data="id_type_id")],
        [InlineKeyboardButton("📄 Daimi yaşayış icazəsi (DYİ)", callback_data="id_type_dyi")],
    ]
    if msg:
        await msg.reply_text(
            MESSAGES["id_type_prompt"],
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    return States.ID_TYPE

async def choose_id_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ID_TYPE seçimini işlə - Şəxsiyyət Vəsiqəsi vs DYİ"""
    query = update.callback_query
    if not query:
        logger.warning("choose_id_type: callback_query yoxdur")
        return ConversationHandler.END
    await query.answer()
    app = _ud(context).setdefault("app", ApplicationData())
    
    if query.data == "id_type_id":
        app.id_type = "ID"
        await query.edit_message_text(MESSAGES["fin_prompt"])
        return States.FIN
    elif query.data == "id_type_dyi":
        app.id_type = "DYI"
        await query.edit_message_text(MESSAGES["pin_prompt"])
        return States.PIN
    return ConversationHandler.END

async def collect_fin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return States.FIN
    fin = msg.text.strip().upper()
    if len(fin) != FIN_LENGTH or not fin.isalnum():
        await msg.reply_text(MESSAGES["fin_error"])
        return States.FIN
    app = _ud(context).setdefault("app", ApplicationData())
    app.code = fin
    app.fin = fin  # Uyğunluq üçün
    await msg.reply_text(MESSAGES["id_photo_prompt"])
    return States.ID_PHOTO

async def collect_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return States.PIN
    pin = msg.text.strip().upper()
    if len(pin) < PIN_MIN_LENGTH or len(pin) > PIN_MAX_LENGTH or not pin.isalnum():
        await msg.reply_text(MESSAGES["pin_error"])
        return States.PIN
    app = _ud(context).setdefault("app", ApplicationData())
    app.code = pin
    app.fin = pin  # Uyğunluq üçün (DB-dən geri uyğunluq)
    await msg.reply_text(MESSAGES["id_photo_prompt"])
    return States.ID_PHOTO

async def collect_id_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    photo_list = getattr(msg, "photo", None)
    if not photo_list:
        if msg:
            await msg.reply_text(MESSAGES["id_photo_error"])
        return States.ID_PHOTO
    file_id = photo_list[-1].file_id
    _ud(context).setdefault("app", ApplicationData()).id_photo_file_id = file_id
    buttons = [
        [InlineKeyboardButton(FormType.COMPLAINT.value, callback_data="type_complaint")],
        [InlineKeyboardButton(FormType.SUGGESTION.value, callback_data="type_suggestion")],
        [InlineKeyboardButton(FormType.APPLICATION.value, callback_data="type_application")],
    ]
    if msg:
        await msg.reply_text(
            MESSAGES["form_type_prompt"],
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    return States.FORM_TYPE

async def choose_form_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        logger.warning("choose_form_type: callback_query yoxdur")
        return ConversationHandler.END
    await query.answer()
    if query.data == "type_complaint":
        _ud(context)["app"].form_type = FormType.COMPLAINT  # type: ignore[index]
    elif query.data == "type_suggestion":
        _ud(context)["app"].form_type = FormType.SUGGESTION  # type: ignore[index]
    else:
        _ud(context)["app"].form_type = FormType.APPLICATION  # type: ignore[index]
    # Mövzu addımı çıxarıldı – birbaşa mətni toplayırıq
    await query.edit_message_text(MESSAGES["body_prompt"])
    return States.BODY

async def collect_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return States.SUBJECT
    subject = msg.text.strip()
    if len(subject) < MIN_SUBJECT_LENGTH or len(subject) > MAX_SUBJECT_LENGTH:
        await msg.reply_text(MESSAGES["subject_error"])
        return States.SUBJECT
    _ud(context).setdefault("app", ApplicationData()).subject = subject
    await msg.reply_text(MESSAGES["body_prompt"])
    return States.BODY

async def collect_body(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return States.BODY
    body = msg.text.strip()
    if len(body) < MIN_BODY_LENGTH or len(body) > MAX_BODY_LENGTH:
        await msg.reply_text(MESSAGES["body_error"])
        return States.BODY
    app_data = _ud(context).setdefault("app", ApplicationData())
    app_data.body = body
    # Mövzu tələb olunmur; DB üçün avtomatik qısa başlıq çıxarırıq (ilk 150 simvol)
    try:
        app_data.subject = body[:150]
    except Exception:
        app_data.subject = body
    app_data.timestamp = datetime.now(BAKU_TZ)
    app: ApplicationData = app_data
    buttons = [
        [InlineKeyboardButton("✅ Təsdiq et və göndər", callback_data="confirm")],
        [InlineKeyboardButton("✏️ Düzəliş et", callback_data="edit")],
        [InlineKeyboardButton("❌ Ləğv et", callback_data="cancel")],
    ]
    if msg:
        await msg.reply_text(app.summary_text(), reply_markup=InlineKeyboardMarkup(buttons))
    return States.CONFIRM

async def confirm_or_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        logger.warning("confirm_or_edit: callback_query yoxdur")
        return ConversationHandler.END
    await query.answer()
    app: Optional[ApplicationData] = _ud(context).get("app")  # type: ignore[index]
    if not app:
        logger.warning("confirm_or_edit: app məlumatı yoxdur")
        return ConversationHandler.END
    if query.data == "cancel":
        await query.edit_message_text(MESSAGES["cancelled"])
        return ConversationHandler.END
    if query.data == "edit":
        # Mövzu addımı ləğv olundu – birbaşa mətni yenidən yazmağı istəyirik
        await query.edit_message_text("Zəhmət olmasa müraciət mətnini yenidən yazın:")
        return States.BODY
    # confirm
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [
        [InlineKeyboardButton("📝 Yeni müraciət göndər", callback_data="start_new")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        MESSAGES["confirm_sent"],
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

    # Database-ə yaz (PostgreSQL və ya SQLite)
    if DB_ENABLED:
        try:
            # Type narrowing / boş olmamalı
            assert all([
                app.fullname,
                app.phone,
                app.fin,
                app.id_photo_file_id,
                app.form_type,
                app.subject,
                app.body,
                app.timestamp,
            ]), "Boş sahə var"
            if USE_SQLITE:
                # SQLite fallback
                db_app = save_application_sqlite(  # type: ignore[possibly-unbound]
                    user_telegram_id=query.from_user.id,
                    user_username=query.from_user.username or "",
                    fullname=app.fullname,  # type: ignore[arg-type]
                    phone=app.phone,  # type: ignore[arg-type]
                    fin=app.fin,  # type: ignore[arg-type]
                    id_photo_file_id=app.id_photo_file_id,  # type: ignore[arg-type]
                    form_type=app.form_type,  # type: ignore[arg-type]
                    subject=app.subject,  # type: ignore[arg-type]
                    body=app.body,  # type: ignore[arg-type]
                    created_at=app.timestamp,  # type: ignore[arg-type]
                )
                logger.info(f"✅ SQLite-a yazıldı: ID={db_app['id']}")
                caption_prefix = f"Sıra №: {db_app['id']}\n"
                db_id = db_app["id"]
            else:
                # PostgreSQL
                db_app = save_application(  # type: ignore[possibly-unbound]
                    user_telegram_id=query.from_user.id,
                    user_username=query.from_user.username or "",
                    fullname=app.fullname,  # type: ignore[arg-type]
                    phone=app.phone,  # type: ignore[arg-type]
                    fin=app.fin,  # type: ignore[arg-type]
                    form_type=app.form_type,  # type: ignore[arg-type]
                    body=app.body,  # type: ignore[arg-type]
                    created_at=app.timestamp,  # type: ignore[arg-type]
                )
                logger.info(f"✅ PostgreSQL-ə yazıldı: ID={db_app.id}")
                caption_prefix = f"Sıra №: {db_app.id}\n"
                db_id = db_app.id  # type: ignore[assignment]
        except Exception as e:
            logger.error(f"❌ DB error: {e}")
            caption_prefix = "⚠️ DB xətası\n"
            db_id = None
    else:
        caption_prefix = ""
        db_id = None

    # Status göstəricisi - yaradılma tarixinə görə
    # 10+ gün əvvəl yaradılıbsa, "Vaxtı keçir"
    days_old = (datetime.now(BAKU_TZ) - app.timestamp).days if app.timestamp else 0
    if days_old >= 10:
        status_line = "\n🔴 Status: Vaxtı keçir"
    else:
        status_line = "\n🟡 Status: Gözləyir"
    
    caption = (
        caption_prefix +
        app.summary_text(include_time=False) +
        status_line +
        "\n\n"
    )

    # İcraçı qrupuna mesaj + foto (yalnız EXECUTOR_CHAT_ID düzgün olduqda)
    global EXECUTOR_CHAT_ID_RT
    if EXECUTOR_CHAT_ID_RT:
        # İcraçıların cavab verməsi üçün inline düymələr
        kb = None
        if db_id is not None:  # None check for type safety
            buttons = [
                [
                    InlineKeyboardButton("✉️ Cavablandır", callback_data=f"exec_reply:{db_id}"),
                    InlineKeyboardButton("🚫 İmtina", callback_data=f"exec_reject:{db_id}"),
                ]
            ]
            kb = InlineKeyboardMarkup(buttons)
        try:
            logger.info(f"İcraçılara göndərilir: chat_id={EXECUTOR_CHAT_ID_RT}, photo_present={bool(app.id_photo_file_id)}")
            # Foto varsa foto ilə göndər, yoxdursa mətn
            if app.id_photo_file_id:
                await context.bot.send_photo(
                    chat_id=EXECUTOR_CHAT_ID_RT,
                    photo=app.id_photo_file_id,
                    caption=caption,
                    reply_markup=kb,
                )
            else:
                await context.bot.send_message(chat_id=EXECUTOR_CHAT_ID_RT, text=caption, reply_markup=kb)
            logger.info("✅ İcraçı qrupuna göndərildi")
        except Exception as send_err:
            msg = str(send_err)
            logger.error(f"❌ İcraçı qrupuna göndərmə xətası: {msg}")
            # Qrup superqrupa miqrasiya edəndə yeni chat id qaytarılır
            if isinstance(send_err, BadRequest) and "migrated" in msg.lower():
                m = re.search(r"-100\d+", msg)
                if m:
                    new_id = int(m.group(0))
                    logger.warning(f"➡️ Yeni supergroup ID aşkarlandı: {new_id} — runtime yenilənir. .env-də EXECUTOR_CHAT_ID dəyərini də buna dəyişin.")
                    EXECUTOR_CHAT_ID_RT = new_id
                    try:
                        if app.id_photo_file_id:
                            await context.bot.send_photo(
                                chat_id=EXECUTOR_CHAT_ID_RT,
                                photo=app.id_photo_file_id,
                                caption=caption,
                                reply_markup=kb,
                            )
                        else:
                            await context.bot.send_message(chat_id=EXECUTOR_CHAT_ID_RT, text=caption, reply_markup=kb)
                        logger.info("✅ Yeni ID ilə icraçı qrupuna göndərildi")
                    except Exception as retry_err:
                        logger.error(f"❌ Yeni ID ilə göndərmə də alınmadı: {retry_err}")
    else:
        logger.warning("EXECUTOR_CHAT_ID təyin edilməyib; icraçılara göndərilmədi")

    # (Previously sent a separate success DM here.) Now confirmation text
    # is shown via the edited message (`confirm_sent`) so no extra DM is needed.
    return ConversationHandler.END

# ================== Yeni müraciət düymə callback ==================
async def start_new_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Təkrar müraciət düyməsinə basıldıqda yeni anket axını başlat"""
    from config import ADMIN_USER_IDS
    
    query = update.callback_query
    user = update.effective_user
    
    if not query or not user:
        return ConversationHandler.END
    
    await query.answer()
    
    # Qara siyahı yoxlaması
    uid = user.id
    if uid and DB_ENABLED:
        try:
            if uid not in ADMIN_USER_IDS:
                blacklisted = False
                if USE_SQLITE:
                    from db_sqlite import is_user_blacklisted_sqlite
                    blacklisted = is_user_blacklisted_sqlite(uid)  # type: ignore[possibly-unbound]
                else:
                    from db_operations import is_user_blacklisted
                    blacklisted = is_user_blacklisted(uid)  # type: ignore[possibly-unbound]
                if blacklisted:
                    await query.edit_message_text(
                        "⚠️ Müraciətləriniz müvəqqəti qəbul edilmir. Xahiş edirik daha sonra yenidən yoxlayın."
                    )
                    return ConversationHandler.END
        except Exception as e:
            logger.error(f"Blacklist yoxlaması xətası: {e}")
    
    # user_data-nı sıfırla (yeni müraciət üçün)
    if context.user_data:
        context.user_data.clear()
    
    # Mesajı sil və yeni anket axınını başlat
    try:
        await query.edit_message_text(MESSAGES["welcome"], reply_markup=None)
    except Exception as e:
        logger.warning(f"Message edit xətası: {e}")
        try:
            await query.message.reply_text(MESSAGES["welcome"])
        except Exception as e2:
            logger.error(f"Reply text xətası: {e2}")
    
    # Anket başlasın: Name step-ə keç
    return States.FULLNAME

# ================== İcraçı qrup cavab axını ==================
async def exec_reply_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat = update.effective_chat
    user = update.effective_user
    user_store = _ud(context)
    if not query or not query.data or not str(query.data).startswith("exec_reply:"):
        return ConversationHandler.END
    if chat and EXECUTOR_CHAT_ID_RT and chat.id != EXECUTOR_CHAT_ID_RT:
        await query.answer("Yalnız icraçı qrupunda istifadə oluna bilər", show_alert=True)
        return ConversationHandler.END
    app_id = int(query.data.split(":", 1)[1])
    user_store["exec_app_id"] = app_id
    # Qrup mesajının ID-sini və orijinal məzmunu saxla
    if query.message:
        user_store["exec_msg_id"] = query.message.message_id
        user_store["exec_chat_id"] = query.message.chat.id
        # Mövcud məzmunu saxla
        orig_content = getattr(query.message, "caption", None) or getattr(query.message, "text", None)
        if orig_content:
            user_store["exec_original_content"] = orig_content
            user_store["exec_has_photo"] = bool(getattr(query.message, "photo", None))
            # DM üçün foto id-ni də saxla (PostgreSQL-də DB-də saxlanmadığı üçün)
            photos = getattr(query.message, "photo", None)
            if photos:
                try:
                    user_store["exec_photo_file_id"] = photos[-1].file_id
                except Exception:
                    pass
    # Callback cavabı: DM-ə keçid üçün deep link əlavə et
    url = None
    try:
        bot_username = context.bot.username
        if bot_username:
            url = f"https://t.me/{bot_username}?start=reply_{app_id}"
    except Exception:
        url = None
    await query.answer("📱 DM-ə keçilirsiniz...", show_alert=False, url=url)
    await query.edit_message_reply_markup(None)
    
    # DM-ə müraciətin tam mətnini göndər
    if user:
        try:
            app_text_var: Optional[str] = None
            app_data = None
            
            if USE_SQLITE:
                from db_sqlite import get_application_by_id_sqlite
                app_data = get_application_by_id_sqlite(app_id)
                if app_data:
                    time_str = str(app_data.get('created_at', ''))
                    app_text_var = (
                        "📋 Müraciət xülasəsi:\n"
                        f"👤 {app_data.get('fullname', '')}\n"
                        f"📱 Mobil nömrə: {app_data.get('phone', '')}\n"
                        f"🆔 FIN: {app_data.get('fin', '')}\n"
                        f"✍️ Müraciət mətni: {app_data.get('body', '')}\n\n"
                        f"⏰ {time_str}\n"
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        "Müraciət sizin tərəfinizdən qəbul edildi:"
                    )
            else:
                from db_operations import get_application_by_id
                app = get_application_by_id(app_id)
                if app:
                    # Bakı vaxtına çevir
                    try:
                        from config import BAKU_TZ
                        from datetime import timezone
                        dt = app.created_at
                        if dt is not None and getattr(dt, 'tzinfo', None) is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        time_str = dt.astimezone(BAKU_TZ).strftime('%d.%m.%y %H:%M:%S') if dt is not None else ''  # type: ignore[union-attr]
                    except Exception:
                        time_str = app.created_at.strftime('%d.%m.%y %H:%M:%S') if (app.created_at is not None) else ''  # type: ignore[union-attr]
                    app_text_var = (
                        "📋 Müraciət xülasəsi:\n"
                        f"👤 {app.fullname}\n"
                        f"📱 Mobil nömrə: {app.phone}\n"
                        f"🆔 FIN: {app.fin}\n"
                        f"✍️ Müraciət mətni: {app.body}\n\n"
                        f"⏰ {time_str}\n"
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        "Müraciət sizin tərəfinizdən qəbul edildi:"
                    )
            
            if app_text_var:
                # Foto varsa DM-də foto ilə göndər, yoxdursa mətn
                photo_id = user_store.get("exec_photo_file_id")
                if isinstance(photo_id, str) and photo_id:
                    await context.bot.send_photo(chat_id=user.id, photo=photo_id, caption=app_text_var)
                else:
                    sqlite_photo_id = None
                    if USE_SQLITE and isinstance(app_data, dict):
                        raw = app_data.get('id_photo_file_id')
                        if isinstance(raw, str) and raw:
                            sqlite_photo_id = raw
                    if sqlite_photo_id:
                        await context.bot.send_photo(chat_id=user.id, photo=sqlite_photo_id, caption=app_text_var)
                    else:
                        await context.bot.send_message(chat_id=user.id, text=app_text_var)
        except Exception as e:
            logger.warning(f"DM-ə müraciət göndərərkən xəta: {e}")
            if user:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"📝 Cavab mətni yazın (ID={app_id}):"
                )
    
    return States.EXEC_REPLY_TEXT

async def exec_reject_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat = update.effective_chat
    user = update.effective_user
    user_store = _ud(context)
    if not query or not query.data or not str(query.data).startswith("exec_reject:"):
        return ConversationHandler.END
    if chat and EXECUTOR_CHAT_ID_RT and chat.id != EXECUTOR_CHAT_ID_RT:
        await query.answer("Yalnız icraçı qrupunda istifadə oluna bilər", show_alert=True)
        return ConversationHandler.END
    app_id = int(query.data.split(":", 1)[1])
    user_store["exec_app_id"] = app_id
    # Qrup mesajının ID-sini və məzmunu saxla
    if query.message:
        user_store["exec_msg_id"] = query.message.message_id
        user_store["exec_chat_id"] = query.message.chat.id
        orig_content = getattr(query.message, "caption", None) or getattr(query.message, "text", None)
        if orig_content:
            user_store["exec_original_content"] = orig_content
            user_store["exec_has_photo"] = bool(getattr(query.message, "photo", None))
            # DM üçün foto id-ni də saxla
            photos = getattr(query.message, "photo", None)
            if photos:
                try:
                    user_store["exec_photo_file_id"] = photos[-1].file_id
                except Exception:
                    pass
    # Callback cavabı: DM-ə keçid üçün deep link əlavə et
    url = None
    try:
        bot_username = context.bot.username
        if bot_username:
            url = f"https://t.me/{bot_username}?start=reject_{app_id}"
    except Exception:
        url = None
    await query.answer("📱 DM-ə keçilirsiniz...", show_alert=False, url=url)
    await query.edit_message_reply_markup(None)
    
    # DM-ə müraciətin tam mətnini göndər
    if user:
        try:
            app_text: Optional[str] = None
            sqlite_photo_id: Optional[str] = None
            if USE_SQLITE:
                from db_sqlite import get_application_by_id_sqlite
                app_data = get_application_by_id_sqlite(app_id)
                if app_data:
                    time_str = str(app_data.get('created_at', ''))
                    app_text = (
                        "📋 Müraciət xülasəsi:\n"
                        f"👤 {app_data.get('fullname', '')}\n"
                        f"📱 Mobil nömrə: {app_data.get('phone', '')}\n"
                        f"🆔 FIN: {app_data.get('fin', '')}\n"
                        f"✍️ Müraciət mətni: {app_data.get('body', '')}\n\n"
                        f"⏰ {time_str}\n"
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        "👇 İmtina səbəbini yazın:"
                    )
                    raw = app_data.get('id_photo_file_id')
                    if isinstance(raw, str) and raw:
                        sqlite_photo_id = raw
            else:
                from db_operations import get_application_by_id
                app = get_application_by_id(app_id)
                if app:
                    # Bakı vaxtı
                    try:
                        from config import BAKU_TZ
                        from datetime import timezone
                        dt = app.created_at
                        if dt is not None and getattr(dt, 'tzinfo', None) is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        time_str = dt.astimezone(BAKU_TZ).strftime('%d.%m.%y %H:%M:%S') if dt is not None else ''  # type: ignore[union-attr]
                    except Exception:
                        time_str = app.created_at.strftime('%d.%m.%y %H:%M:%S') if (app.created_at is not None) else ''  # type: ignore[union-attr]
                    app_text = (
                        "📋 Müraciət xülasəsi:\n"
                        f"👤 {app.fullname}\n"
                        f"📱 Mobil nömrə: {app.phone}\n"
                        f"🆔 FIN: {app.fin}\n"
                        f"✍️ Müraciət mətni: {app.body}\n\n"
                        f"⏰ {time_str}\n"
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        "👇 İmtina səbəbini yazın:"
                    )
            
            if app_text:
                # Foto varsa DM-də foto ilə göndər
                photo_id = user_store.get("exec_photo_file_id")
                if isinstance(photo_id, str) and photo_id:
                    await context.bot.send_photo(chat_id=user.id, photo=photo_id, caption=app_text)
                elif sqlite_photo_id:
                    await context.bot.send_photo(chat_id=user.id, photo=sqlite_photo_id, caption=app_text)
                else:
                    await context.bot.send_message(chat_id=user.id, text=app_text)
        except Exception as e:
            logger.warning(f"DM-ə müraciət göndərərkən xəta: {e}")
            if user:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"🚫 İmtina səbəbini yazın (ID={app_id}):"
                )
    return States.EXEC_REJECT_REASON

async def exec_collect_reply_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from_user = update.effective_user
    msg = update.effective_message
    user_data = context.user_data if context.user_data else {}
    app_id = user_data.get("exec_app_id")
    exec_msg_id = user_data.get("exec_msg_id")
    exec_chat_id = user_data.get("exec_chat_id")
    if not msg or not msg.text or not app_id or not from_user:
        return States.EXEC_REPLY_TEXT
    text = msg.text.strip()
    try:
        if USE_SQLITE:
            from db_sqlite import get_application_by_id_sqlite, update_application_status_sqlite
            app = get_application_by_id_sqlite(app_id)
            if not app:
                await msg.reply_text("❌ Müraciət tapılmadı")
                return ConversationHandler.END
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("Yeni müraciət göndər", callback_data="start_new")]])
            await context.bot.send_message(chat_id=app["user_telegram_id"], text=f"✅ Müraciətinizə cavab:\n\n{text}", reply_markup=kb)
            update_application_status_sqlite(app_id, "completed", notes=f"Replied by @{from_user.username or from_user.id}")
        else:
            from db_operations import get_application_by_id, update_application_status, ApplicationStatus
            app = get_application_by_id(app_id)
            if not app:
                await msg.reply_text("❌ Müraciət tapılmadı")
                return ConversationHandler.END
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("Yeni müraciət göndər", callback_data="start_new")]])
            await context.bot.send_message(chat_id=app.user_telegram_id, text=f"✅ Müraciətinizə cavab:\n\n{text}", reply_markup=kb)  # type: ignore[arg-type]
            update_application_status(app_id, ApplicationStatus.COMPLETED, notes=f"Replied by @{from_user.username or from_user.id}", reply_text=text)
        
        # Qrup mesajında statusu yenilə və cavabı görünən et
        if exec_msg_id and exec_chat_id:
            try:
                orig_content = user_data.get("exec_original_content", "")
                has_photo = user_data.get("exec_has_photo", False)
                # Status sətirini dəyiş: 🟡 Gözləyir → 🟢 İcra edildi
                new_content = re.sub(
                    r"🟡 Status: Gözləyir",
                    f"🟢 Status: İcra edildi\nİcraçı -@{from_user.username or from_user.id}",
                    orig_content
                )
                # Cavab mətni əlavə et (caption limitlərini nəzərə al)
                CAP_LIMIT = 1000
                reply_excerpt = text if len(text) <= 300 else (text[:300] + "…")
                reply_block = "\n\n✉️ Cavab: " + reply_excerpt
                # Əvvəlcə statusu dəyişib yeni mətni formalaşdır
                if "✉️ Cavab:" in new_content:
                    new_content = re.sub(r"✉️ Cavab:.*", f"✉️ Cavab: {reply_excerpt}", new_content, flags=re.S)
                else:
                    new_content = new_content + reply_block
                # Limitdən böyükdürsə, baş hissəni qısaldıb cavabı saxla
                if len(new_content) > CAP_LIMIT:
                    head_len = max(CAP_LIMIT - len(reply_block) - 1, 0)
                    # Baş hissəni status daxil olmaqla saxla, sonuna …, sonra cavab bloku
                    base = re.sub(r"✉️ Cavab:.*", "", new_content, flags=re.S)
                    base = base[:head_len] + ("…" if head_len > 0 else "")
                    new_content = base + reply_block
                # Qrup mesajına '✏️ Cavabı düzəlt' düyməsi əlavə et
                edit_kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✏️ Cavabı düzəlt", callback_data=f"edit_reply:{app_id}")]
                ])
                if has_photo:
                    await context.bot.edit_message_caption(
                        chat_id=exec_chat_id,
                        message_id=exec_msg_id,
                        caption=new_content,
                        reply_markup=edit_kb
                    )
                else:
                    await context.bot.edit_message_text(
                        chat_id=exec_chat_id,
                        message_id=exec_msg_id,
                        text=new_content,
                        reply_markup=edit_kb
                    )
                # Yadda saxla ki, sonradan edit edəndə bu kontentdən istifadə edək
                user_data["exec_original_content"] = new_content
            except Exception as edit_err:
                logger.warning(f"Qrup mesajı yenilənmədi: {edit_err}")
        
        await msg.reply_text("✅ Cavab göndərildi")
    except Exception as e:
        logger.error(f"exec_collect_reply_text error: {e}")
        await msg.reply_text(f"❌ Xəta: {e}")
    finally:
        user_data.pop("exec_app_id", None)
        user_data.pop("exec_msg_id", None)
        user_data.pop("exec_chat_id", None)
        user_data.pop("exec_original_content", None)
        user_data.pop("exec_has_photo", None)
    return ConversationHandler.END


async def exec_edit_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Qrupdan 'Cavabı düzəlt' düyməsi basılanda DM-ə yönəlt."""
    query = update.callback_query
    chat = update.effective_chat
    user = update.effective_user
    user_store = _ud(context)
    if not query or not query.data or not str(query.data).startswith("edit_reply:"):
        return ConversationHandler.END
    if chat and EXECUTOR_CHAT_ID_RT and chat.id != EXECUTOR_CHAT_ID_RT:
        await query.answer("Yalnız icraçı qrupunda istifadə oluna bilər", show_alert=True)
        return ConversationHandler.END
    app_id = int(query.data.split(":", 1)[1])
    user_store["exec_app_id"] = app_id
    # Qrup mesaj konteksti saxla
    if query.message:
        user_store["exec_msg_id"] = query.message.message_id
        user_store["exec_chat_id"] = query.message.chat.id
        orig_content = getattr(query.message, "caption", None) or getattr(query.message, "text", None)
        if orig_content:
            user_store["exec_original_content"] = orig_content
            user_store["exec_has_photo"] = bool(getattr(query.message, "photo", None))
    # DM-ə birbaşa xəbərdarlıq və mövcud cavabla birlikdə prompt göndər
    await query.answer("✏️ DM-ə keçin: cavabı yeniləmək üçün mesaj yazın", show_alert=False)
    try:
        # Mövcud cavabı əldə et
        existing_text: Optional[str] = None
        if USE_SQLITE:
            from db_sqlite import get_application_by_id_sqlite
            app_data = get_application_by_id_sqlite(app_id)
            if app_data and isinstance(app_data, dict):
                raw = app_data.get('reply_text')
                if isinstance(raw, str):
                    existing_text = raw
        else:
            from db_operations import get_application_by_id
            app = get_application_by_id(app_id)
            if app:
                try:
                    existing_text = app.reply_text  # type: ignore[attr-defined]
                except Exception:
                    existing_text = None
        preface = "✏️ Yeni cavabı yazın:"
        if existing_text:
            preface = f"Mövcud cavab:\n\n{existing_text}\n\n✏️ Yeni cavabı yazın:"
        if user:
            await context.bot.send_message(chat_id=user.id, text=preface)
    except Exception as dm_err:
        logger.warning(f"Edit DM prompt göndərilə bilmədi: {dm_err}")
    return States.EXEC_EDIT_REPLY_TEXT


async def exec_collect_edit_reply_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """DM-də yeni cavab mətni qəbul et, DB və qrup mesajını yenilə, vətəndaşa göndər."""
    from_user = update.effective_user
    msg = update.effective_message
    user_data = context.user_data if context.user_data else {}
    app_id = user_data.get("exec_app_id")
    exec_msg_id = user_data.get("exec_msg_id")
    exec_chat_id = user_data.get("exec_chat_id")
    if not msg or not msg.text or not app_id or not from_user:
        return States.EXEC_EDIT_REPLY_TEXT
    new_text = msg.text.strip()
    try:
        if USE_SQLITE:
            from db_sqlite import get_application_by_id_sqlite, update_application_status_sqlite
            app = get_application_by_id_sqlite(app_id)
            if not app:
                await msg.reply_text("❌ Müraciət tapılmadı")
                return ConversationHandler.END
            # Vətəndaşa yenilənmiş cavab göndər
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("Yeni müraciət göndər", callback_data="start_new")]])
            await context.bot.send_message(chat_id=app["user_telegram_id"], text=f"♻️ Yenilənmiş cavab:\n\n{new_text}", reply_markup=kb)
            update_application_status_sqlite(app_id, "completed", notes=f"Edited by @{from_user.username or from_user.id}")
        else:
            from db_operations import get_application_by_id, update_application_status, ApplicationStatus
            app = get_application_by_id(app_id)
            if not app:
                await msg.reply_text("❌ Müraciət tapılmadı")
                return ConversationHandler.END
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("Yeni müraciət göndər", callback_data="start_new")]])
            await context.bot.send_message(chat_id=app.user_telegram_id, text=f"♻️ Yenilənmiş cavab:\n\n{new_text}", reply_markup=kb)  # type: ignore[arg-type]
            update_application_status(app_id, ApplicationStatus.COMPLETED, notes=f"Edited by @{from_user.username or from_user.id}", reply_text=new_text)

        # Qrup mesajında cavab mətni hissəsini yenilə
        if exec_msg_id and exec_chat_id:
            try:
                orig_content = user_data.get("exec_original_content", "")
                has_photo = user_data.get("exec_has_photo", False)
                CAP_LIMIT = 1000
                reply_excerpt = new_text if len(new_text) <= 300 else (new_text[:300] + "…")
                reply_block = "\n\n✉️ Cavab: " + reply_excerpt
                if "✉️ Cavab:" in orig_content:
                    base = re.sub(r"✉️ Cavab:.*", "", orig_content, flags=re.S)
                    new_content = base + reply_block
                else:
                    new_content = orig_content + reply_block
                if len(new_content) > CAP_LIMIT:
                    head_len = max(CAP_LIMIT - len(reply_block) - 1, 0)
                    base2 = re.sub(r"✉️ Cavab:.*", "", new_content, flags=re.S)
                    base2 = base2[:head_len] + ("…" if head_len > 0 else "")
                    new_content = base2 + reply_block
                # '✏️ Cavabı düzəlt' düyməsini saxla
                edit_kb = InlineKeyboardMarkup([[InlineKeyboardButton("✏️ Cavabı düzəlt", callback_data=f"edit_reply:{app_id}")]])
                if has_photo:
                    await context.bot.edit_message_caption(chat_id=exec_chat_id, message_id=exec_msg_id, caption=new_content, reply_markup=edit_kb)
                else:
                    await context.bot.edit_message_text(chat_id=exec_chat_id, message_id=exec_msg_id, text=new_content, reply_markup=edit_kb)
                # Yeni məzmunu gələcək düzəlişlər üçün yadda saxla
                user_data["exec_original_content"] = new_content
            except Exception as e2:
                logger.warning(f"Qrup mesajı yenilənmədi (edit): {e2}")

        await msg.reply_text("✅ Cavab yeniləndi")
    except Exception as e:
        logger.error(f"exec_collect_edit_reply_text error: {e}")
        await msg.reply_text(f"❌ Xəta: {e}")
    return ConversationHandler.END


async def exec_collect_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from_user = update.effective_user
    msg = update.effective_message
    user_data = context.user_data if context.user_data else {}
    app_id = user_data.get("exec_app_id")
    exec_msg_id = user_data.get("exec_msg_id")
    exec_chat_id = user_data.get("exec_chat_id")
    if not msg or not msg.text or not app_id or not from_user:
        return States.EXEC_REJECT_REASON
    reason = msg.text.strip()
    try:
        if USE_SQLITE:
            from db_sqlite import get_application_by_id_sqlite, update_application_status_sqlite
            app = get_application_by_id_sqlite(app_id)
            if not app:
                await msg.reply_text("❌ Müraciət tapılmadı")
                return ConversationHandler.END
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("Yeni müraciət göndər", callback_data="start_new")]])
            await context.bot.send_message(chat_id=app["user_telegram_id"], text=f"❌ Müraciət rədd edildi. Səbəb:\n\n{reason}", reply_markup=kb)
            update_application_status_sqlite(app_id, "rejected", notes=f"Rejected by @{from_user.username or from_user.id}: {reason}")
        else:
            from db_operations import get_application_by_id, update_application_status, ApplicationStatus
            app = get_application_by_id(app_id)
            if not app:
                await msg.reply_text("❌ Müraciət tapılmadı")
                return ConversationHandler.END
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("Yeni müraciət göndər", callback_data="start_new")]])
            await context.bot.send_message(chat_id=app.user_telegram_id, text=f"❌ Müraciət rədd edildi. Səbəb:\n\n{reason}", reply_markup=kb)  # type: ignore[arg-type]
            update_application_status(app_id, ApplicationStatus.REJECTED, notes=f"Rejected by @{from_user.username or from_user.id}: {reason}", reply_text=reason)
        
        # Qrup mesajında statusu yenilə (cavab mesajı göstərmə, sadəcə status dəyiş)
        if exec_msg_id and exec_chat_id:
            try:
                orig_content = user_data.get("exec_original_content", "")
                has_photo = user_data.get("exec_has_photo", False)
                # Status sətirini dəyiş: 🟡 Gözləyir → ⚫ İmtina
                new_content = re.sub(
                    r"🟡 Status: Gözləyir",
                    f"⚫ Status: İmtina\nİcraçı -@{from_user.username or from_user.id}",
                    orig_content
                )
                if has_photo:
                    await context.bot.edit_message_caption(
                        chat_id=exec_chat_id,
                        message_id=exec_msg_id,
                        caption=new_content
                    )
                else:
                    await context.bot.edit_message_text(
                        chat_id=exec_chat_id,
                        message_id=exec_msg_id,
                        text=new_content
                    )
            except Exception as edit_err:
                logger.warning(f"Qrup mesajı yenilənmədi: {edit_err}")
        
        # Auto-blacklist qaydası: eyni istifadəçi çox imtina alıbsa qara siyahıya sal
        try:
            # SQLite dict -> int, PostgreSQL ORM -> primitive int (runtime doğru tipdədir)
            raw_uid = app["user_telegram_id"] if USE_SQLITE else app.user_telegram_id  # type: ignore[index]
            target_uid: int = int(raw_uid)  # type: ignore[arg-type]
            from config import ADMIN_USER_IDS, BLACKLIST_REJECTION_THRESHOLD, BLACKLIST_WINDOW_DAYS
            if target_uid not in ADMIN_USER_IDS:
                rej_count = 0
                if USE_SQLITE:
                    from db_sqlite import count_user_rejections_sqlite, add_user_to_blacklist_sqlite, is_user_blacklisted_sqlite
                    rej_count = count_user_rejections_sqlite(target_uid, days=BLACKLIST_WINDOW_DAYS)  # type: ignore[possibly-unbound]
                    if rej_count >= BLACKLIST_REJECTION_THRESHOLD and not is_user_blacklisted_sqlite(target_uid):  # type: ignore[possibly-unbound]
                        add_user_to_blacklist_sqlite(target_uid, reason=f"{rej_count} imtina / {BLACKLIST_WINDOW_DAYS} gün")  # type: ignore[possibly-unbound]
                        try:
                            await context.bot.send_message(chat_id=target_uid, text="⚠️ Çox sayda imtina səbəbilə müraciətləriniz müvəqqəti qəbul edilmir.")  # type: ignore[arg-type]
                        except Exception:
                            pass
                else:
                    from db_operations import count_user_rejections, add_user_to_blacklist, is_user_blacklisted
                    rej_count = count_user_rejections(target_uid, days=BLACKLIST_WINDOW_DAYS)  # type: ignore[possibly-unbound]
                    if rej_count >= BLACKLIST_REJECTION_THRESHOLD and not is_user_blacklisted(target_uid):  # type: ignore[possibly-unbound]
                        add_user_to_blacklist(target_uid, reason=f"{rej_count} imtina / {BLACKLIST_WINDOW_DAYS} gün")  # type: ignore[possibly-unbound]
                        try:
                            await context.bot.send_message(chat_id=target_uid, text="⚠️ Çox sayda imtina səbəbilə müraciətləriniz müvəqqəti qəbul edilmir.")  # type: ignore[arg-type]
                        except Exception:
                            pass
        except Exception as bl_e:
            logger.error(f"Auto-blacklist xətası: {bl_e}")

        await msg.reply_text("✅ İmtina səbəbi göndərildi")
    except Exception as e:
        logger.error(f"exec_collect_reject_reason error: {e}")
        await msg.reply_text(f"❌ Xəta: {e}")
    finally:
        user_data.pop("exec_app_id", None)
        user_data.pop("exec_msg_id", None)
        user_data.pop("exec_chat_id", None)
        user_data.pop("exec_original_content", None)
        user_data.pop("exec_has_photo", None)
    return ConversationHandler.END

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message:
        await update.effective_message.reply_text(MESSAGES["help"])

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message:
        await update.effective_message.reply_text(MESSAGES["unknown"])

async def chatid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if update.effective_message and chat:
        await update.effective_message.reply_text(f"Chat ID: {chat.id}")

async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """CSV export - PostgreSQL və SQLite hər ikisində işləyir"""
    global ADMIN_USER_IDS
    user_id = getattr(update.effective_user, "id", None)
    if user_id not in ADMIN_USER_IDS:
        if update.effective_message:
            await update.effective_message.reply_text("❌ Bu komanda yalnız adminlər üçün açıqdır.")
        return
    if not DB_ENABLED:
        if update.effective_message:
            await update.effective_message.reply_text("⚠️ Database deaktiv, export mümkün deyil.")
        return
    
    try:
        csv_content = None
        
        if USE_SQLITE:
            # SQLite JSON export
            from db_sqlite import export_to_json as sqlite_export_json  # type: ignore[misc]
            output_file = sqlite_export_json()
            if update.effective_message:
                await update.effective_message.reply_text(f"✅ Export hazırdır: {output_file}")
            return
        else:
            # PostgreSQL CSV export
            from db_operations import export_to_csv  # type: ignore[misc]
            csv_content = export_to_csv()
        
        if csv_content:
            # CSV-ni fayl olaraq göndər
            import io
            csv_file = io.BytesIO(csv_content.encode('utf-8'))
            csv_file.name = "applications.csv"
            
            if update.effective_message:
                await update.effective_message.reply_document(
                    document=csv_file,
                    filename="applications.csv",
                    caption="📊 Müraciətlər CSV export (PostgreSQL)"
                )
                user_id = update.effective_user.id if update.effective_user else "unknown"
                logger.info(f"✅ CSV export göndərildi. User: {user_id}")
        else:
            if update.effective_message:
                await update.effective_message.reply_text("⚠️ Export ediləcək məlumat yoxdur.")
    except Exception as e:
        logger.error(f"Export error: {e}", exc_info=True)
        if update.effective_message:
            await update.effective_message.reply_text(f"❌ Export xətası: {e}")

async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message:
        await update.effective_message.reply_text("🏓 Pong")

# ================== SLA xatırlatma job ==================
async def sla_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    """Hər gün SLA aşan müraciətləri yoxla və xatırlatma göndər"""
    if not DB_ENABLED or not EXECUTOR_CHAT_ID_RT:
        return
    
    try:
        overdue_apps = []
        if USE_SQLITE:
            from db_sqlite import get_overdue_applications_sqlite
            overdue_apps = get_overdue_applications_sqlite(days=3)  # type: ignore[possibly-unbound]
        else:
            from db_operations import get_overdue_applications
            overdue_apps = get_overdue_applications(days=3)  # type: ignore[possibly-unbound]
        
        if not overdue_apps:
            logger.info("✅ SLA yoxlaması: Köhnə müraciət yoxdur")
            return
        
        count = len(overdue_apps)
        message = f"⚠️ SLA Xatırlatması\n\n{count} müraciət 3 gündən çoxdur cavabsızdır:\n\n"
        
        for app in overdue_apps[:10]:  # İlk 10-u göstər
            if USE_SQLITE:
                app_id = app["id"]
                title = (app.get("body") or "")
                created = app["created_at"]
            else:
                app_id = app.id
                title = app.body
                # Type ignore for PostgreSQL Column type
                created = app.created_at.strftime('%d.%m.%Y') if app.created_at is not None else "N/A"  # type: ignore[union-attr]
            
            message += f"🆔 {app_id} - {title[:30]}... ({created})\n"
        
        if count > 10:
            message += f"\n...və daha {count - 10} müraciət"
        
        await context.bot.send_message(chat_id=EXECUTOR_CHAT_ID_RT, text=message)
        logger.info(f"✅ SLA xatırlatması göndərildi: {count} köhnə müraciət")
    except Exception as e:
        logger.error(f"❌ SLA reminder job xətası: {e}")

# ================== Admin blacklist əmrləri ==================
def _is_admin(user_id: int) -> bool:
    from config import ADMIN_USER_IDS
    return user_id in ADMIN_USER_IDS

async def blacklist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    if not _is_admin(uid):
        await update.effective_message.reply_text("❌ İcazə yoxdur")
        return
    try:
        if USE_SQLITE:
            from db_sqlite import list_blacklisted_users_sqlite
            rows = list_blacklisted_users_sqlite()
            if not rows:
                await update.effective_message.reply_text("✅ Qara siyahı boşdur")
                return
            text = "🛑 Qara Siyahı:\n\n" + "\n".join([
                f"• {r['user_telegram_id']} – {r.get('reason','(səbəb yoxdur)')} – {r['created_at']}" for r in rows
            ])
        else:
            from db_operations import list_blacklisted_users
            rows = list_blacklisted_users()
            if not rows:
                await update.effective_message.reply_text("✅ Qara siyahı boşdur")
                return
            text = "🛑 Qara Siyahı:\n\n" + "\n".join([
                f"• {r.user_telegram_id} – {r.reason or '(səbəb yoxdur)'} – {r.created_at.strftime('%d.%m.%Y')}" for r in rows
            ])
        await update.effective_message.reply_text(text[:4000])
    except Exception as e:
        logger.error(f"/blacklist xətası: {e}")
        await update.effective_message.reply_text("❌ Xəta baş verdi")

async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    if not _is_admin(uid):
        await update.effective_message.reply_text("❌ İcazə yoxdur")
        return
    if not context.args:
        await update.effective_message.reply_text("İstifadə: /ban <user_id> [səbəb]")
        return
    target = context.args[0]
    reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Admin ban"
    try:
        target_id = int(target)
    except ValueError:
        await update.effective_message.reply_text("user_id rəqəm olmalıdır")
        return
    try:
        if USE_SQLITE:
            from db_sqlite import add_user_to_blacklist_sqlite, is_user_blacklisted_sqlite
            if is_user_blacklisted_sqlite(target_id):
                await update.effective_message.reply_text("Artıq qara siyahıdadır")
                return
            add_user_to_blacklist_sqlite(target_id, reason)
        else:
            from db_operations import add_user_to_blacklist, is_user_blacklisted
            if is_user_blacklisted(target_id):
                await update.effective_message.reply_text("Artıq qara siyahıdadır")
                return
            add_user_to_blacklist(target_id, reason)
        await update.effective_message.reply_text(f"✅ {target_id} qara siyahıya əlavə olundu")
    except Exception as e:
        logger.error(f"/ban xətası: {e}")
        await update.effective_message.reply_text("❌ Xəta baş verdi")

async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    if not _is_admin(uid):
        await update.effective_message.reply_text("❌ İcazə yoxdur")
        return
    if not context.args:
        await update.effective_message.reply_text("İstifadə: /unban <user_id>")
        return
    target = context.args[0]
    try:
        target_id = int(target)
    except ValueError:
        await update.effective_message.reply_text("user_id rəqəm olmalıdır")
        return
    try:
        if USE_SQLITE:
            from db_sqlite import remove_user_from_blacklist_sqlite, is_user_blacklisted_sqlite
            if not is_user_blacklisted_sqlite(target_id):
                await update.effective_message.reply_text("Qara siyahıda deyil")
                return
            remove_user_from_blacklist_sqlite(target_id)
        else:
            from db_operations import remove_user_from_blacklist, is_user_blacklisted
            if not is_user_blacklisted(target_id):
                await update.effective_message.reply_text("Qara siyahıda deyil")
                return
            remove_user_from_blacklist(target_id)
        await update.effective_message.reply_text(f"✅ {target_id} qara siyahıdan silindi")
    except Exception as e:
        logger.error(f"/unban xətası: {e}")
        await update.effective_message.reply_text("❌ Xəta baş verdi")

async def clearall_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """⚠️ Bütün müraciətləri sil (test məlumatları üçün)"""
    if not update.effective_user or not update.effective_message:
        return
    uid = update.effective_user.id
    if not _is_admin(uid):
        await update.effective_message.reply_text("❌ İcazə yoxdur")
        return
    try:
        # Təsdiq xahişi
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Bəli, sil", callback_data="confirm_clearall"),
                InlineKeyboardButton("❌ Xeyr", callback_data="cancel_clearall")
            ]
        ])
        await update.effective_message.reply_text(
            "⚠️ **Xəbərdarlıq:** Bütün müraciətlər SİLİNƏCƏK!\n\n"
            "Bu əməliyyat geri çevrilə bilməz. Dəvam etmək istəyirsiniz?",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"/clearall xətası: {e}")
        await update.effective_message.reply_text("❌ Xəta baş verdi")

async def confirm_clearall_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Müraciətlərin silinməsini təsdiq et"""
    query = update.callback_query
    if not query:
        return
    if not query.from_user or not _is_admin(query.from_user.id):
        await query.answer("❌ İcazə yoxdur", show_alert=True)
        return
    try:
        if USE_SQLITE:
            from db_sqlite import delete_all_applications_sqlite
            count = delete_all_applications_sqlite()
        else:
            from db_operations import delete_all_applications
            count = delete_all_applications()
        await query.answer()
        await query.edit_message_text(f"✅ {count} müraciət silindi!")
    except Exception as e:
        logger.error(f"Clearall xətası: {e}")
        await query.answer("❌ Xəta baş verdi", show_alert=True)

async def cancel_clearall_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Silinməni ləğv et"""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("❌ Ləğv edildi")

def build_app() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN təyin edilməyib. .env faylını yoxlayın.")
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(start_new_callback, pattern=r"^start_new$")
        ],
        states={
            States.FULLNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_fullname)],
            States.PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_phone)],
            States.ID_TYPE: [CallbackQueryHandler(choose_id_type)],
            States.FIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_fin)],
            States.PIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_pin)],
            States.ID_PHOTO: [MessageHandler(filters.PHOTO, collect_id_photo)],
            States.FORM_TYPE: [CallbackQueryHandler(choose_form_type)],
            States.SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_subject)],
            States.BODY: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_body)],
            States.CONFIRM: [CallbackQueryHandler(confirm_or_edit)],
        },
        fallbacks=[CommandHandler("help", help_cmd)],
        allow_reentry=True,
    )
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .build()
    )
    app.add_handler(conv)
    # Global error handler
    app.add_error_handler(error_handler)
    # İcraçı qrupunda cavab/imtina üçün mini dialoqlar
    exec_conv_reply = ConversationHandler(
        entry_points=[CallbackQueryHandler(exec_reply_entry, pattern=r"^exec_reply:\d+$")],
        states={
            States.EXEC_REPLY_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, exec_collect_reply_text)],
        },
        fallbacks=[],
        allow_reentry=False,
        per_chat=False,
        per_user=True,
    )
    exec_conv_reject = ConversationHandler(
        entry_points=[CallbackQueryHandler(exec_reject_entry, pattern=r"^exec_reject:\d+$")],
        states={
            States.EXEC_REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, exec_collect_reject_reason)],
        },
        fallbacks=[],
        allow_reentry=False,
        per_chat=False,
        per_user=True,
    )
    exec_conv_edit = ConversationHandler(
        entry_points=[CallbackQueryHandler(exec_edit_entry, pattern=r"^edit_reply:\d+$")],
        states={
            States.EXEC_EDIT_REPLY_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, exec_collect_edit_reply_text)],
        },
        fallbacks=[],
        allow_reentry=False,
        per_chat=False,
        per_user=True,
    )
    app.add_handler(exec_conv_reply)
    app.add_handler(exec_conv_reject)
    app.add_handler(exec_conv_edit)
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("chatid", chatid_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CommandHandler("ping", ping_cmd))
    app.add_handler(CommandHandler("blacklist", blacklist_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("clearall", clearall_cmd))
    # Clearall callback handlers
    app.add_handler(CallbackQueryHandler(confirm_clearall_callback, pattern=r"^confirm_clearall$"))
    app.add_handler(CallbackQueryHandler(cancel_clearall_callback, pattern=r"^cancel_clearall$"))
    # Kanal postu aşkarlandıqda məlumat verən sadə universal handler
    async def on_any_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.channel_post and update.effective_chat:
            try:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Zəhmət olmasa bot-a birbaşa mesaj yazın: /start")
            except Exception:
                pass
    # Qrup=1 ilə əlavə edirik ki, əsas command-lardan sonra yoxlanılsın
    app.add_handler(MessageHandler(filters.ALL, on_any_update), group=1)
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    return app

def main():
    global USE_SQLITE, DB_ENABLED  # global-lar başda elan
    # Database-i initialize et (PostgreSQL və ya SQLite)
    if DB_ENABLED:
        try:
            if USE_SQLITE:
                init_sqlite_db()  # type: ignore[possibly-unbound]
                logger.info("✅ SQLite database hazırdır (fallback mode)")
            else:
                init_db()  # type: ignore[possibly-unbound]
                logger.info("✅ PostgreSQL database hazırdır")
        except Exception as e:
            logger.error(f"❌ Database initialization error: {e}")
            # Runtime zamanı PostgreSQL alınmadısa, SQLite-a keçid et
            if not USE_SQLITE:
                try:
                    from db_sqlite import (
                        save_application_sqlite as _save_application_sqlite,
                        init_sqlite_db as _init_sqlite_db,
                        export_to_json as _sqlite_export_json,
                    )
                    # Moduldaxili adları dinamik mənimsət
                    globals()["save_application_sqlite"] = _save_application_sqlite
                    globals()["init_sqlite_db"] = _init_sqlite_db
                    globals()["sqlite_export_json"] = _sqlite_export_json
                    _init_sqlite_db()
                    USE_SQLITE = True
                    DB_ENABLED = True
                    logger.info("✅ PostgreSQL uğursuz oldu; SQLite-a keçid edildi və hazırdır")
                except Exception as e2:
                    logger.error(f"❌ SQLite fallback da alınmadı: {e2}")
                    DB_ENABLED = False
                    logger.warning("⚠️ Bot DB-siz işləyəcək")
            else:
                logger.warning("⚠️ Bot DB-siz işləyəcək")
    
    app = build_app()
    
    # SLA xatırlatma job-u qur (hər gün səhər 09:00-da)
    job_queue = app.job_queue
    if job_queue:
        from datetime import time
        job_queue.run_daily(sla_reminder_job, time=time(hour=9, minute=0, tzinfo=BAKU_TZ))
        logger.info("✅ SLA xatırlatma job-u quruldu (hər gün 09:00)")
    
    logger.info("🚀 DSMF Bot işə başlayır... (Bakı vaxtı)")
    logger.info(f"⏰ Start time: {datetime.now(BAKU_TZ).strftime('%d.%m.%Y %H:%M:%S')}")
    
    try:
        # drop_pending_updates=True – əvvəlki instansiyadan qalan uzun polling sorğularını təmizləyir
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except KeyboardInterrupt:
        logger.info("Bot dayandırıldı (KeyboardInterrupt)")
    except Exception as e:
        logger.error(f"Bot xətası: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
