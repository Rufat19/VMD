# Komanda Referansı

Tam istifadəçi və admin komanda siyahısı.

## İstifadəçi Komandaları
| Komanda | Təsvir |
|---------|--------|
| /start | Yeni müraciət prosesini başlayır (anket mərhələli) |
| /help | Qısa yardım və yönləndirmə mesajı |
| /chatid | Cari chat ID-ni göstərir (qruplar/kanallar üçün) |
| /ping | Sadə sağlamlıq yoxlaması (Pong cavabı) |
| /export | **PostgreSQL: CSV fayl export** (ID, Full Name, Phone, FIN, Form Type, Subject, Body, Status, Created Date, Updated Date) / **SQLite: JSON export** |

## İcraçı Qrup İçi Inline Düymələr
| Düymə | Funksiya |
|-------|----------|
| ✉️ Cavablandır | Cavab mətnini daxil etmə dialoqunu açır; status 🟢 İcra edildi |
| 🚫 İmtina | İmtina səbəbi daxil etmə dialoqu; status ⚫ İmtina |

## Admin Komandaları
| Komanda | Təsvir |
|---------|--------|
| /blacklist | Qara siyahıda olan istifadəçilərin siyahısını göstərir |
| /ban <user_id> [səbəb] | İstifadəçini qara siyahıya əlavə edir |
| /unban <user_id> | Qara siyahıdan çıxarır |
| /clearall | ⚠️ **Bütün müraciətləri sil** (test məlumatları üçün, geri çevrilə bilməz) |

## Avtomatik Mexanizmlər
| Mexanizm | Şərh |
|----------|-------|
| SLA xatırlatma | Hər gün 09:00-da 3+ gün cavabsız müraciətlərin xülasəsi qrupda paylaşılır |
| Auto-blacklist | 30 gün ərzində ≥5 imtina alan istifadəçi qara siyahıya düşür (admin istisna) |
| Rate limit | Normal istifadəçi 24 saatda max 3 müraciət (admin istisna) |
| Supergroup ID miqrasiyası | Qrup superqrupa keçdikdə yeni -100… ID avtomatik aşkar edilir |

## Konfiqurasiya Parametrləri (config.py)
| Parametr | Default | İzah |
|----------|---------|------|
| MAX_SUBJECT_LENGTH | 150 | Mövzu maksimum uzunluğu |
| MAX_BODY_LENGTH | 1000 | Məzmun maksimum uzunluğu |
| MAX_DAILY_SUBMISSIONS | 3 | Rate limit (müraciət / 24 saat) |
| BLACKLIST_REJECTION_THRESHOLD | 5 | Blacklist üçün minimum imtina sayı |
| BLACKLIST_WINDOW_DAYS | 30 | İmtina sayılma pəncərəsi (gün) |
| ADMIN_USER_IDS | {6520873307} | Limit və blacklist exempt istifadəçilər |

## Status Axını
| Status | Şərh |
|--------|------|
| 🟡 Gözləyir | Yeni müraciət (0–9 gün) |
| 🔴 Vaxtı keçir | ≥10 gün cavabsız |
|  İcra edildi | Cavablandırılıb / tamamlanıb |
| ⚫ İmtina | Rədd edilib |

## Tövsiyə Edilən İstifadə
1. İstifadəçi `/start` ilə başlayan anketi tamamlayır.
2. Müraciət icraçı qrupuna yönləndirilir (foto + xülasə).
3. İcraçı "✉️ Cavablandır" və ya "� İmtina" seçərək cavab verir.
4. Cavablandırılarsa status 🟢, imtina olunarsa ⚫ olur və vətəndaşa DM gedir.
5. Uzun müddət cavabsız qalarsa tələsik diqqət üçün 🔴 olur.

## Qeyd
Bu sənəd sürətli başvuru üçündür; tam detallar üçün `README.md`, dəyişiklik tarixi üçün `CHANGELOG.md`, gələcək plan üçün `ROADMAP.md`.
