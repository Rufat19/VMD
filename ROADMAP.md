# Roadmap

High-level plan for future evolution of the DSMF Citizen Appeal Bot.

## Vision
Provide a reliable, auditable, multilingual platform for collecting citizen appeals, routing them to appropriate staff, tracking lifecycle state, and closing the feedback loop with timely responses.

## Current Release (0.4.3) - UX & Data Quality Improvements ✅
### Completed Features (2025-01-10)
- ✅ Simplified intake flow: removed subject step (auto-generated from body)
- ✅ Three form types: Şikayət (Complaint), Təklif (Suggestion), Ərizə (Application)
- ✅ Enhanced CSV export:
  - Azerbaijani column headers and status labels
  - Baku timezone (UTC+4) for all timestamps
  - Excel-compatible phone number formatting (text format with apostrophe prefix)
  - UTF-8 BOM for proper Azerbaijani character display
- ✅ Database optimization: removed unused columns (subject, id_photo_file_id from PostgreSQL)
- ✅ Photo display maintained in Telegram (not stored in PostgreSQL, available in SQLite)
- ✅ Welcome message streamlined (removed redundant step descriptions)

## Previous Release (0.4.2) - CSV Export & Admin Tools ✅
### Completed Features (2025-11-10)
- ✅ PostgreSQL CSV export with `/export` command
- ✅ Admin commands: `/blacklist`, `/ban`, `/unban`, `/clearall`
- ✅ Rate limiting: max 3 submissions per 24 hours
- ✅ Automatic blacklist for users with 5+ rejections in 30 days
- ✅ SLA reminders: daily notifications for 3+ day pending appeals

## Previous Release (0.4.1) - Railway Production Fixes ✅
### Completed Features (2025-11-09)
- ✅ PostgreSQL authentication via Railway PUBLIC proxy URL (maglev.proxy.rlwy.net)
- ✅ SQLAlchemy session detach fix for production stability
- ✅ Telegram API timeout extensions (30s) for Railway latency
- ✅ Polling conflict mitigation with drop_pending_updates
- ✅ Global async error handler for cleaner logging
- ✅ `.env.example` updated with PostgreSQL Railway template

### Known Issues / Workarounds
- Polling "Conflict" errors may persist if token is used in multiple deployments → rotate BOT_TOKEN in BotFather
- Ensure Railway: 1 active replica, stopped old deployments

## Near-Term (Planned for 0.5.0)
### Priority Features
- ⏳ **Webhook mode** (alternative to polling for zero-conflict guarantee)
- ⏳ **Connection pooling** (PostgreSQL production hardening, retry backoff)
- ⏳ Admin statistics `/stats` (total, by status, avg response time, overdue count)
- ⏳ Search `/search` (FIN, phone, ID, keyword in body)
- ⏳ Application editing before final confirmation
- ⏳ Phone normalization & duplicate detection
- ⏳ Unit test coverage for conversation + executor flows
- ⏳ Health check endpoint `/health` for monitoring

## Mid-Term (0.6.0 and Beyond)
### Advanced Features
- [ ] Multi-language support (AZ / EN / RU) via dynamic language switch command.
- [ ] File storage abstraction (optionally S3 or Railway volume) for ID photos.
- [ ] Web dashboard (FastAPI + simple admin UI) for browsing and exporting appeals.
- [ ] Automatic FIN format heuristics and cross-field consistency checks.
- [ ] Appeal threading: allow staff to send follow-up questions before resolving.
- [ ] SLA timers: automatic reminders for pending > X hours.

## Long-Term / Stretch
### Vision Features
- [ ] Analytics module: trends by form_type, response times, rejection reasons.
- [ ] AI-assisted categorisation of complaints vs suggestions.
- [ ] Integration with external CRM / ticketing system.
- [ ] Encrypted at-rest storage of sensitive PII (phone, FIN) with key rotation.
- [ ] OAuth-based staff identity mapping for multi-system audit trails.
- [ ] Load balancing & auto-scaling for high volume deployments

## Quality & Operations
### Infrastructure Improvements
- Add test suite (pytest) for conversation flow state transitions.
- CI pipeline (GitHub Actions) for linting, tests, Docker image build.
- Security review: secret scanning, dependency vulnerability audit.
- Monitoring dashboards (CPU, memory, database latency)
- Observability: structured logs, metrics counters (appeals_created, replies_sent).

## Versioning Strategy
- **Patch (x.y.Z)**: Bug fixes / small internal improvements.
- **Minor (x.Y.0)**: New features (e.g. reply workflow, dashboard, multi-language).
- **Major (X.0.0)**: Architectural shifts (e.g. move to microservices, encryption layer).

---
Last updated: 2025-01-10 (v0.4.3 release)
