# Roadmap

High-level plan for future evolution of the DSMF Citizen Appeal Bot.

## Vision
Provide a reliable, auditable, multilingual platform for collecting citizen appeals, routing them to appropriate staff, tracking lifecycle state, and closing the feedback loop with timely responses.

## Current Release (0.4.0) - COMPLETED ✅
### Completed Features
- ✅ (Prev) Real-time status system (🟡/🔴/🟢/⚫)
- ✅ Processing inline status (📝 İşləyir) button
- ✅ SLA reminder daily job (pending >3 days summary)
- ✅ Rate limiting (24h max 3 appeals per user; admin exempt)
- ✅ Auto-blacklist (≥5 rejections / 30 days) + admin management commands
- ✅ Blacklist admin commands: /blacklist /ban /unban
- ✅ Improved welcome message (steps, status flow, privacy, response time)
- ✅ Type safety and Column truthiness fixes

## Near-Term (Planned for 0.5.0)
### Priority Features
- ⏳ PostgreSQL prod hardening (connection pooling, retry backoff)
- ⏳ Admin statistics `/stats` (total, by status, avg response time, overdue count)
- ⏳ Search `/search` (FIN, phone, ID, keyword in subject/body)
- ⏳ Application editing before final confirmation
- ⏳ Phone normalization & duplicate detection
- ⏳ Central error handler + JSON structured logging
- ⏳ Unit test coverage for conversation + executor flows

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

## Quality & Operations
### Infrastructure Improvements
- Add test suite (pytest) for conversation flow state transitions.
- CI pipeline (GitHub Actions) for linting, tests, Docker image build.
- Security review: secret scanning, dependency vulnerability audit.
- Observability: structured logs, metrics counters (appeals_created, replies_sent).

## Versioning Strategy
- **Patch (x.y.Z)**: Bug fixes / small internal improvements.
- **Minor (x.Y.0)**: New features (e.g. reply workflow, dashboard, multi-language).
- **Major (X.0.0)**: Architectural shifts (e.g. move to microservices, encryption layer).

---
Last updated: 2025-11-09 (v0.3.0 release)

---
Last updated: 2025-11-09 (v0.3.0 release)
