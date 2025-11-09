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
    BAKU_TZ,
    setup_logging,
)
import re
from telegram.error import BadRequest

setup_logging()
logger = logging.getLogger("dsmf-bot")
EXECUTOR_CHAT_ID_RT = EXECUTOR_CHAT_ID  # Runtime-da yenilənə bilən icraçı chat ID

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

class States(Enum):
    FULLNAME = auto()
    PHONE = auto()
    FIN = auto()
    ID_PHOTO = auto()
    FORM_TYPE = auto()
    SUBJECT = auto()
    BODY = auto()
    CONFIRM = auto()
    EXEC_REPLY_TEXT = auto()
    EXEC_REJECT_REASON = auto()

@dataclass
class ApplicationData:
    fullname: Optional[str] = None
    phone: Optional[str] = None
    fin: Optional[str] = None
    id_photo_file_id: Optional[str] = None
    form_type: Optional[FormType] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    timestamp: Optional[datetime] = None

    def summary_text(self) -> str:
        # Tarix qısa formatda və sonunda
        time_str = ""
        if self.timestamp:
            time_str = f"⏰ {self.timestamp.strftime('%d.%m.%y %H:%M:%S')}\n"
        return (
            "📋 Müraciət xülasəsi:\n"
            # Ad xətti sadələşdirildi (uzun başlıq silindi)
            f"👤 {self.fullname}\n"
            f"📱 Mobil nömrə: {self.phone}\n"
            f"🆔 FIN: {self.fin}\n"
            # Form növü gizlədilib (istifadəçi və qrup mesajlarında göstərilmir)
            f"📝 Mövzu: {self.subject}\n"
            f"✍️ Məzmun: {self.body}\n\n"
            f"{time_str}"
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    # Diaqnostika üçün loq (istifadəçi və çat məlumatları)
    uid = getattr(update.effective_user, "id", None)
    cid = getattr(update.effective_chat, "id", None)
    ctype = getattr(update.effective_chat, "type", None)
    logger.info(f"/start from user_id={uid} chat_id={cid} chat_type={ctype}")
    if not msg:
        logger.warning("/start çağırışı message obyektisiz gəldi")
        return ConversationHandler.END

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
    
    # Rate limiting yoxlaması (spam qarşısı) — adminlər azaddır
    from config import ADMIN_USER_IDS
    # Admin istifadəçiləri üçün limit tətbiq olunmur
    if DB_ENABLED and uid and uid not in ADMIN_USER_IDS:
        try:
            recent_count = 0
            if USE_SQLITE:
                from db_sqlite import count_user_recent_applications_sqlite
                recent_count = count_user_recent_applications_sqlite(uid, hours=24)  # type: ignore[possibly-unbound]
            else:
                from db_operations import count_user_recent_applications
                recent_count = count_user_recent_applications(uid, hours=24)  # type: ignore[possibly-unbound]
            
            from config import MAX_DAILY_SUBMISSIONS
            if recent_count >= MAX_DAILY_SUBMISSIONS:
                await msg.reply_text(
                    f"⚠️ Siz artıq son 24 saatda {MAX_DAILY_SUBMISSIONS} müraciət göndərmisiniz.\n"
                    "Zəhmət olmasa bir az gözləyin və ya əvvəlki müraciətlərinizin cavabını gözləyin.",
                    reply_markup=ReplyKeyboardRemove(),
                )
                logger.warning(f"Rate limit: user_id={uid} artıq {recent_count} müraciət göndərib")
                return ConversationHandler.END
        except Exception as e:
            logger.error(f"Rate limiting yoxlaması xətası: {e}")
            # Xəta olarsa, istifadəçini bloklamırıq
    
    await msg.reply_text(
        MESSAGES["welcome"],
        reply_markup=ReplyKeyboardRemove(),
    )
    _ud(context).setdefault("app", ApplicationData())
    return States.FULLNAME

async def collect_fullname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return States.FULLNAME
    name = msg.text.strip()
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
    await msg.reply_text(MESSAGES["fin_prompt"])
    return States.FIN

async def collect_fin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return States.FIN
    fin = msg.text.strip().upper()
    if len(fin) != FIN_LENGTH or not fin.isalnum():
        await msg.reply_text(MESSAGES["fin_error"])
        return States.FIN
    _ud(context).setdefault("app", ApplicationData()).fin = fin
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
    else:
        _ud(context)["app"].form_type = FormType.SUGGESTION  # type: ignore[index]
    await query.edit_message_text(MESSAGES["subject_prompt"])
    return States.SUBJECT

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
        await query.edit_message_text("Hansını düzəltmək istəyirsiniz? Ad/Soyad/Telefon/FIN/Mövzu/Mətn yazın.")
        return States.SUBJECT
    # confirm
    await query.edit_message_text(MESSAGES["confirm_sent"])

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
                caption_prefix = f"🆔 SQLite ID: {db_app['id']}\n"
                db_id = db_app["id"]
            else:
                # PostgreSQL
                db_app = save_application(  # type: ignore[possibly-unbound]
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
                logger.info(f"✅ PostgreSQL-ə yazıldı: ID={db_app.id}")
                caption_prefix = f"🆔 DB ID: {db_app.id}\n"
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
        status_line = "🔴 Status: Vaxtı keçir\n\n"
    else:
        status_line = "🟡 Status: Gözləyir\n\n"
    
    caption = (
        caption_prefix +
        status_line +
        "🆕 Yeni Müraciət\n\n" + app.summary_text() + 
        f"\nGöndərən: @{query.from_user.username or 'istifadəçi adı yoxdur'}\n"
        f"User ID: {query.from_user.id}"
    )

    # İcraçı qrupuna mesaj + foto (yalnız EXECUTOR_CHAT_ID düzgün olduqda)
    global EXECUTOR_CHAT_ID_RT
    if EXECUTOR_CHAT_ID_RT:
        # İcraçıların cavab verməsi üçün inline düymələr
        kb = None
        if db_id is not None:  # None check for type safety
            buttons = [
                [
                    InlineKeyboardButton("📝 İşləyir", callback_data=f"exec_processing:{db_id}"),
                ],
                [
                    InlineKeyboardButton("✉️ Cavablandır", callback_data=f"exec_reply:{db_id}"),
                    InlineKeyboardButton("🚫 İmtina", callback_data=f"exec_reject:{db_id}"),
                ]
            ]
            kb = InlineKeyboardMarkup(buttons)
        try:
            logger.info(f"İcraçılara göndərilir: chat_id={EXECUTOR_CHAT_ID_RT}, photo_present={bool(app.id_photo_file_id)}")
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

    # Vatandaşa təsdiq DM
    if query.message and query.message.chat:
        await context.bot.send_message(chat_id=query.message.chat.id, text=MESSAGES["success"])
    return ConversationHandler.END

# ================== İcraçı qrup cavab axını ==================
async def exec_mark_processing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """İcraçı 'İşləyir' statusu seçəndə."""
    query = update.callback_query
    chat = update.effective_chat
    if not query or not query.data or not str(query.data).startswith("exec_processing:"):
        return
    if chat and EXECUTOR_CHAT_ID_RT and chat.id != EXECUTOR_CHAT_ID_RT:
        await query.answer("Yalnız icraçı qrupunda istifadə oluna bilər", show_alert=True)
        return
    app_id = int(query.data.split(":", 1)[1])
    
    # Database-də statusu yenilə
    if DB_ENABLED:
        try:
            if USE_SQLITE:
                from db_sqlite import update_application_status_sqlite
                update_application_status_sqlite(app_id, "processing")  # type: ignore[possibly-unbound]
            else:
                from db_operations import update_application_status
                from database import ApplicationStatus
                update_application_status(app_id, ApplicationStatus.PROCESSING)  # type: ignore[possibly-unbound]
            logger.info(f"✅ App ID={app_id} statusu 'processing' olaraq dəyişdirildi")
        except Exception as e:
            logger.error(f"❌ Status update xətası: {e}")
            await query.answer("Xəta baş verdi", show_alert=True)
            return
    
    # Qrup mesajındakı statusu yenilə
    if query.message:
        orig_content = getattr(query.message, "caption", None) or getattr(query.message, "text", None)
        has_photo = bool(getattr(query.message, "photo", None))
        executor_username = query.from_user.username or "executor"
        
        if orig_content:
            # Status sətirini regex ilə dəyiş
            new_content = re.sub(
                r"🟡 Status: Gözləyir|🔴 Status: Vaxtı keçir",
                f"📝 Status: İşləyir (@{executor_username})",
                orig_content
            )
            try:
                if has_photo:
                    await query.edit_message_caption(caption=new_content, reply_markup=None)
                else:
                    await query.edit_message_text(text=new_content, reply_markup=None)
                await query.answer("📝 İşlənir olaraq işarələndi")
            except Exception as e:
                logger.error(f"❌ Mesaj update xətası: {e}")
                await query.answer("Status dəyişdi, amma mesaj yenilənmədi", show_alert=True)
    else:
        await query.answer("📝 İşlənir olaraq işarələndi")

async def exec_reply_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat = update.effective_chat
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
    await query.answer()
    await query.edit_message_reply_markup(None)
    if chat:
        await context.bot.send_message(chat_id=chat.id, text=f"📝 Cavab mətni yazın (ID={app_id}):")
    return States.EXEC_REPLY_TEXT

async def exec_reject_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat = update.effective_chat
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
    await query.answer()
    await query.edit_message_reply_markup(None)
    if chat:
        await context.bot.send_message(chat_id=chat.id, text=f"🚫 İmtina səbəbini yazın (ID={app_id}):")
    return States.EXEC_REJECT_REASON

async def exec_collect_reply_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from_user = update.effective_user
    msg = update.effective_message
    user_store = _ud(context)
    app_id = user_store.get("exec_app_id")
    exec_msg_id = user_store.get("exec_msg_id")
    exec_chat_id = user_store.get("exec_chat_id")
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
            await context.bot.send_message(chat_id=app["user_telegram_id"], text=f"✅ Müraciətinizə cavab:\n\n{text}")
            update_application_status_sqlite(app_id, "completed", notes=f"Replied by @{from_user.username or from_user.id}")
        else:
            from db_operations import get_application_by_id, update_application_status, ApplicationStatus
            app = get_application_by_id(app_id)
            if not app:
                await msg.reply_text("❌ Müraciət tapılmadı")
                return ConversationHandler.END
            await context.bot.send_message(chat_id=app.user_telegram_id, text=f"✅ Müraciətinizə cavab:\n\n{text}")  # type: ignore[arg-type]
            update_application_status(app_id, ApplicationStatus.COMPLETED, notes=f"Replied by @{from_user.username or from_user.id}")
        
        # Qrup mesajında statusu yenilə
        if exec_msg_id and exec_chat_id:
            try:
                orig_content = user_store.get("exec_original_content", "")
                has_photo = user_store.get("exec_has_photo", False)
                # Status sətirini dəyiş: 🟡 Gözləyir → 🟢 İcra edildi
                new_content = re.sub(
                    r"🟡 Status: Gözləyir",
                    f"🟢 Status: İcra edildi (@{from_user.username or from_user.id})",
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
        
        await msg.reply_text("✅ Cavab göndərildi")
    except Exception as e:
        logger.error(f"exec_collect_reply_text error: {e}")
        await msg.reply_text(f"❌ Xəta: {e}")
    finally:
        user_store.pop("exec_app_id", None)
        user_store.pop("exec_msg_id", None)
        user_store.pop("exec_chat_id", None)
    return ConversationHandler.END

async def exec_collect_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from_user = update.effective_user
    msg = update.effective_message
    user_store = _ud(context)
    app_id = user_store.get("exec_app_id")
    exec_msg_id = user_store.get("exec_msg_id")
    exec_chat_id = user_store.get("exec_chat_id")
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
            await context.bot.send_message(chat_id=app["user_telegram_id"], text=f"❌ Müraciət rədd edildi. Səbəb:\n\n{reason}")
            update_application_status_sqlite(app_id, "rejected", notes=f"Rejected by @{from_user.username or from_user.id}: {reason}")
        else:
            from db_operations import get_application_by_id, update_application_status, ApplicationStatus
            app = get_application_by_id(app_id)
            if not app:
                await msg.reply_text("❌ Müraciət tapılmadı")
                return ConversationHandler.END
            await context.bot.send_message(chat_id=app.user_telegram_id, text=f"❌ Müraciət rədd edildi. Səbəb:\n\n{reason}")  # type: ignore[arg-type]
            update_application_status(app_id, ApplicationStatus.REJECTED, notes=f"Rejected by @{from_user.username or from_user.id}: {reason}")
        
        # Qrup mesajında statusu yenilə
        if exec_msg_id and exec_chat_id:
            try:
                orig_content = user_store.get("exec_original_content", "")
                has_photo = user_store.get("exec_has_photo", False)
                # Status sətirini dəyiş: 🟡 Gözləyir → ⚫ İmtina
                new_content = re.sub(
                    r"🟡 Status: Gözləyir",
                    f"⚫ Status: İmtina (@{from_user.username or from_user.id})",
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
        user_store.pop("exec_app_id", None)
        user_store.pop("exec_msg_id", None)
        user_store.pop("exec_chat_id", None)
        user_store.pop("exec_original_content", None)
        user_store.pop("exec_has_photo", None)
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
    """JSON export (yalnız SQLite üçün)"""
    if not DB_ENABLED or not USE_SQLITE:
        if update.effective_message:
            await update.effective_message.reply_text("⚠️ Export yalnız SQLite modunda mövcuddur.")
        return
    
    try:
        from db_sqlite import export_to_json as sqlite_export_json  # type: ignore[misc]
        output_file = sqlite_export_json()
        if update.effective_message:
            await update.effective_message.reply_text(f"✅ Export hazırdır: {output_file}")
    except Exception as e:
        logger.error(f"Export error: {e}")
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
                subject = app["subject"]
                created = app["created_at"]
            else:
                app_id = app.id
                subject = app.subject
                # Type ignore for PostgreSQL Column type
                created = app.created_at.strftime('%d.%m.%Y') if app.created_at is not None else "N/A"  # type: ignore[union-attr]
            
            message += f"🆔 {app_id} - {subject[:30]}... ({created})\n"
        
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


def build_app() -> Application:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN təyin edilməyib. .env faylını yoxlayın.")
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            States.FULLNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_fullname)],
            States.PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_phone)],
            States.FIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, collect_fin)],
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
    # İcraçı qrupunda cavab/imtina üçün mini dialoqlar
    exec_conv_reply = ConversationHandler(
        entry_points=[CallbackQueryHandler(exec_reply_entry, pattern=r"^exec_reply:\d+$")],
        states={
            States.EXEC_REPLY_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, exec_collect_reply_text)],
        },
        fallbacks=[],
        allow_reentry=False,
    )
    exec_conv_reject = ConversationHandler(
        entry_points=[CallbackQueryHandler(exec_reject_entry, pattern=r"^exec_reject:\d+$")],
        states={
            States.EXEC_REJECT_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, exec_collect_reject_reason)],
        },
        fallbacks=[],
        allow_reentry=False,
    )
    app.add_handler(exec_conv_reply)
    app.add_handler(exec_conv_reject)
    # "İşləyir" düyməsi üçün standalone callback handler
    app.add_handler(CallbackQueryHandler(exec_mark_processing, pattern=r"^exec_processing:\d+$"))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("chatid", chatid_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CommandHandler("ping", ping_cmd))
    app.add_handler(CommandHandler("blacklist", blacklist_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
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
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("Bot dayandırıldı (KeyboardInterrupt)")
    except Exception as e:
        logger.error(f"Bot xətası: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
