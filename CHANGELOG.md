# Changelog

All notable changes to this project will be documented in this file.

## [0.4.2] - 2025-11-10 (PostgreSQL CSV Export + Session Fixes + Test Data Cleanup + Polling Conflict Handling)
### Added
- **PostgreSQL CSV export**: `/export` command now generates CSV file for appeals in PostgreSQL database, with proper English column headers (ID, Full Name, Phone, FIN, Form Type, Subject, Body, Status, Created Date, Updated Date).
- **Management reporting**: CSV format enables direct Excel import for pivot tables, statistics, and trend analysis.
- **Timezone-aware timestamps**: All exported dates use dd.mm.yyyy HH:MM:SS format with Bakı timezone (Asia/Baku).
- **Test data cleanup**: `/clearall` admin command to delete all applications from database (useful for clearing test data during development).
- **Polling conflict detection**: Error handler now detects and logs Polling Conflict errors with helpful troubleshooting guidance.

### Changed
- `/export` command now returns CSV for PostgreSQL (instead of only JSON for SQLite fallback). SQLite mode still uses JSON format.
- Version bumped to 0.4.2 with PostgreSQL CSV export as primary export method.
- Removed "📝 İşləyir" button from executor group - unnecessary processing status feature.
- **CSV headers now in English** to avoid UTF-8 encoding issues in Excel/LibreOffice (ID, Full Name, Phone, FIN, Form Type, Subject, Body, Status, Created Date, Updated Date).
- **Admin User IDs now configurable via .env** - `ADMIN_USER_IDS` can be set to comma-separated list (e.g., `123456789,987654321`).

### Fixed
- **SQLAlchemy session detach**: Fixed "Instance not bound to a Session" error in all database query functions (`get_application_by_id()`, `get_applications_by_user()`, `get_applications_by_status()`, `search_applications()`) by properly detaching ORM objects before returning from session context.
- **CSV encoding issues**: English headers and form type values prevent garbled characters (Ə, Ü, etc.) in exported files.
- **Polling Conflict handling**: Error handler mutes redundant Polling Conflict errors and logs helpful troubleshooting info (Railway replica settings, token rotation guidance).
- CSV export uses SQLAlchemy session properly with `is not None` type-safe checks instead of truthy evaluation on database columns.
- Cavab mətni göndərərkən ("✉️ Cavablandır" düyməsi) artıq session xətası verməyəcəyi.

## [0.4.1] - 2025-11-09 (Railway Production Fixes)
### Fixed
- **PostgreSQL authentication**: Corrected DATABASE_URL format to use Railway's PUBLIC proxy URL (`maglev.proxy.rlwy.net:56367`) instead of internal hostname. Variable reference (`${{Postgres.DATABASE_URL}}`) now properly configured in Railway.
- **SQLAlchemy session detach**: Fixed "Instance not bound to Session" error by detaching `Application` object from session context in `save_application()` before returning (added `db.expunge(app)`).
- **Telegram API timeout**: Extended connection/read/write/pool timeouts from default 5s to 30s to handle Railway network latency. Configured in `ApplicationBuilder`.
- **Polling conflict mitigation**: Added `drop_pending_updates=True` in `run_polling()` to discard pending requests from previous instances, reducing "terminated by other getUpdates" conflicts.
- **Global error handler**: Added async error handler to catch and log PTB internal errors cleanly with user/chat context.

### Changed
- `.env.example` updated with PostgreSQL Railway template and DATABASE_URL reference syntax.
- `db_operations.py` improved for production session handling.

### Notes
- If "Conflict: terminated by other getUpdates request" persists, rotate BOT_TOKEN in BotFather and update Railway variables.
- Ensure Railway deployment has only 1 active replica and previous deployments are stopped.

## [0.4.0] - 2025-11-09
### Added
- **Processing status**: New inline button 📝 İşləyir to mark application as being actively handled.
- **SLA reminder job**: Daily 09:00 check; sends summary of appeals pending >3 days.
- **Rate limiting**: Max 3 appeals per user per 24h (admins exempt).
- **Admin exemption**: `ADMIN_USER_IDS` bypass rate limiting.
- **Auto-blacklist system**: Users with ≥5 rejections in 30 days are blacklisted (configurable). `/start` blocks blacklisted users.
- **Blacklist admin commands**: `/blacklist`, `/ban <id> [reason]`, `/unban <id>`.
- **Blacklist storage**: Unified model (PostgreSQL + SQLite table) `blacklisted_users`.

### Changed
- Welcome message improved with steps, status flow, response time expectation and privacy note.
- Added clear configuration for blacklist thresholds in `config.py`.

### Fixed
- Column truthiness checks replaced with explicit `is not None` (type-checker compliance).
- Minor safety improvements in rejection flow and message editing.

## [0.3.0] - 2025-11-09
### Added
- **Real-time status system** in group messages:
  - 🟡 **Gözləyir** (Pending) - new applications (0-9 days old)
  - 🔴 **Vaxtı keçir** (Overdue) - 10+ days old, requires urgent attention
  - 🟢 **İcra edildi** (Completed) - replied/resolved
  - ⚫ **İmtina** (Rejected) - rejected with reason
- **Status auto-update** when executor clicks Reply or Reject buttons
- **Executor username** displayed in status line after action
- **Subject and body length limits**: Subject max 150 chars, body max 1000 chars (international standards)
- **Shortened timestamp format**: ⏰ 09.11.25 19:21:10 (day.month.year hour:min:sec)
- Timestamp moved to end of message (above sender info)

### Changed
- Form type (Şikayət/Təklif) hidden from display messages (still stored in DB)
- Name line simplified: "👤 Fullname" (removed "Ad Soyad Ata adı:" prefix)
- Username fallback: shows "@user" instead of user ID when username missing
- User ID displayed separately below username
- Prompts show limits: "max 150 simvol", "max 1000 simvol"

### Fixed
- Type checker warnings for PostgreSQL Column types (added type: ignore annotations)
- None-safe checks for effective_chat and query.message attributes
- "Possibly unbound" warnings for init_sqlite_db and init_db functions

## [0.2.0] - 2025-11-09
### Added
- Executor group inline actions (Reply / Reject) with DM notifications to citizen.
- Runtime detection of supergroup migration and automatic chat ID update/retry.
- FORCE_SQLITE / DB_MODE env flags for local development without PostgreSQL.
- Dynamic fallback to SQLite if PostgreSQL init fails at runtime.
- `/ping` diagnostic command.
- `version.py` and version display on startup.
- Debug logging around group forwarding (success / failure / new ID detection).

### Changed
- ConversationHandler patterns fixed for callback data (regex correction for exec_reply / exec_reject).
- Improved robust null-safe access to messages and callback queries.

### Fixed
- Group migration error causing failure to deliver appeals; now auto-retries with new -100... ID.
- Multiple instance 409 conflicts mitigated by guidance; logging clarified.

## [0.1.0] - 2025-11-09
### Added
- Initial multi-step appeal flow: fullname, phone, FIN, ID photo, form type, subject, body, confirmation.
- Azerbaijani localization texts.
- Timezone stamping (Asia/Baku) on appeals.
- PostgreSQL persistence models + operations.
- SQLite fallback module with JSON export (`/export`).
- Commands: /start, /help, /chatid, /export.
- Deployment files (Procfile, runtime.txt, railway.json) and docs (README, DATABASE, DEPLOYMENT).

