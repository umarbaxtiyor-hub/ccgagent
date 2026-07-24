# Qurilish kompaniyasi uchun xarajat/daromad Telegram boti

Telegram bot orqali kunlik xarajatlar va bank hisobidan o'tadigan pullarni
(kirim/chiqim) kategoriyalarga bo'lib qayd qiladigan AI agent.

## Imkoniyatlar

- **Erkin matn**: xodim botga "Sement uchun 500000 so'm to'ladim" kabi xabar
  yozadi, AI (Gemini) summani, turini (kirim/chiqim) va kategoriyasini o'zi
  aniqlaydi. Saqlashdan oldin tasdiqlash so'raladi.
- **Chek/kvitansiya rasmi**: rasm yuborilsa, AI undan summa va tafsilotlarni
  o'qib oladi (vision).
- **Ovozli xabar**: Groq (Whisper) orqali matnga o'giriladi, keyin xuddi
  yozma xabar kabi tahlil qilinadi.
- **Bank ko'chirmasi**: `.xlsx`/`.csv` fayl yuborilsa, har bir qator avtomatik
  o'qiladi va AI yordamida kategoriyalarga bo'linadi, so'ng tasdiqlangandan
  keyin bazaga saqlanadi.
- **Loyihalar (obyektlar)**: har bir xodim `/loyiha` orqali joriy loyihasini
  tanlaydi (yoki `/loyiha_yarat <nomi>` bilan yangisini qo'shadi); shu loyiha
  tanlanmagan bo'lsa, bot yozuvni qabul qilishdan oldin tanlashni so'raydi.
  Barcha tranzaksiyalar va hisobotlar loyiha bo'yicha ham ajratiladi.
- **Hisobotlar**: `/report` buyrug'i bilan bugungi/haftalik/oylik hisobot
  Excel faylda (tranzaksiyalar ro'yxati + loyiha/kategoriya bo'yicha
  jamlanma) yuboriladi.
- Botdan faqat `ALLOWED_USER_IDS` da ko'rsatilgan Telegram foydalanuvchilari
  foydalana oladi.

## O'rnatish

1. `.env.example` faylini `.env` ga nusxalab, quyidagilarni to'ldiring:
   - `BOT_TOKEN` — @BotFather dan olingan token
   - `GEMINI_API_KEY` — Google AI Studio (aistudio.google.com) dan olingan kalit
   - `GROQ_API_KEY` — ovozli xabarlarni matnga o'girish uchun (ixtiyoriy,
     bo'sh qoldirilsa ovoz funksiyasi ishlamaydi)
   - `DATABASE_URL` — Postgres ulanish satri
   - `ALLOWED_USER_IDS` — botdan foydalanishi mumkin bo'lgan Telegram
     user ID lar, vergul bilan ajratilgan

2. Docker bilan ishga tushirish:

   ```bash
   docker compose up --build
   ```

   Yoki mahalliy Python muhitida:

   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   python -m app.bot
   ```

Bot birinchi ishga tushganda kerakli jadvallarni va standart kategoriyalarni
(`app/services/categories.py`) o'zi yaratadi.

## Railway'ga joylash

**Muhim**: agar bazangiz allaqachon boshqa joyda (masalan, Supabase) mavjud
bo'lsa va u yerda ma'lumotlar bor bo'lsa, Railway'da **yangi Postgres
yaratmang** — bitta bot ikkita alohida bazaga bo'linib qolmasligi uchun,
shunchaki mavjud bazaning connection-string'ini `DATABASE_URL` sifatida
bering (quyida 2-band).

1. [railway.app](https://railway.app) da yangi loyiha yarating va shu GitHub
   repo (`claude/ai-agent-telegram-expenses-dcaqit` branch yoki uni `main`ga
   birlashtirgandan keyin) bilan bog'lang. Railway `Dockerfile`ni avtomatik
   aniqlab, konteynerni quradi.
2. `DATABASE_URL` uchun ikki variant:
   - **Mavjud bazadan foydalanish (tavsiya etiladi, agar u allaqachon bor
     bo'lsa)**: bazangizning to'liq connection-string'ini qo'lda kiriting
     (masalan Supabase'ning Session Pooler qatori:
     `postgresql://<rol>.<project-ref>:<parol>@aws-0-<region>.pooler.supabase.com:5432/postgres`).
   - **Yangi baza kerak bo'lsa**: loyihaga Railway **Postgres** pluginini
     qo'shing (New → Database → PostgreSQL) va `${{Postgres.DATABASE_URL}}`
     reference'idan foydalaning. Bu holatda Railway `postgres://` ko'rinishida
     beradi — kod uni o'zi `postgresql+asyncpg://` ga o'giradi.
3. Bot xizmatining "Variables" bo'limida qo'shing:
   - `BOT_TOKEN`
   - `GEMINI_API_KEY`
   - `GEMINI_MODEL` (ixtiyoriy, standart: `gemini-flash-latest`)
   - `GROQ_API_KEY` (ovozli xabarlar uchun)
   - `ALLOWED_USER_IDS`
   - `DATABASE_URL` (yuqoridagi 2-band)
4. Bot uzluksiz ishlaydigan background process (long polling), tashqi HTTP
   portini talab qilmaydi — Railway'da xizmat turini "Worker" qilib
   qo'yishingiz mumkin (health-check/portni o'chirib qo'ying, aks holda
   Railway HTTP javob kutib xizmatni "unhealthy" deb belgilashi mumkin).
5. Deploy tugagach, botni Telegram'da `/start` bilan sinab ko'ring.

## Loyiha tuzilishi

```
app/
  bot.py               - bot kirish nuqtasi
  config.py            - .env sozlamalari
  db.py                - SQLAlchemy async engine/session
  models.py             - User, Category, Transaction, Project
  access.py             - foydalanuvchilarni ruxsat bo'yicha filtrlash
  handlers/
    common.py            - loyiha talab qilish + matn tahlilini navbatga qo'yish (umumiy)
    start.py, text_entry.py, receipt.py, voice.py, bank_import.py,
    projects.py, reports.py - har bir kiritish turi uchun handlerlar
  services/
    ai_parser.py        - Gemini orqali matn/rasm/bank qatorlarini tahlil
    stt.py                - Groq (Whisper) orqali ovozni matnga o'girish
    bank_import.py       - bank ko'chirmasi fayllarini o'qish
    excel_export.py      - hisobot Excel fayl generatsiyasi
    categories.py        - standart kategoriyalar
    projects.py           - loyiha (obyekt) CRUD
    users.py              - foydalanuvchi CRUD
```

## Kategoriyalar

**Chiqim**: Qurilish materiallari, Ish haqi, Transport, Jihoz va asboblar,
Ijara, Kommunal to'lovlar, Soliq va yig'imlar, Boshqa xarajat.

**Kirim**: Mijoz to'lovi, Kredit / investitsiya, Boshqa daromad.

Yangi kategoriya kerak bo'lsa, AI mos kategoriya topilmasa avtomatik
"Boshqa xarajat"/"Boshqa daromad" ga yozadi — kerak bo'lsa
`app/services/categories.py` dagi ro'yxatga qo'shish mumkin.
