# Qurilish kompaniyasi uchun xarajat/daromad Telegram boti

Telegram bot orqali kunlik xarajatlar va bank hisobidan o'tadigan pullarni
(kirim/chiqim) kategoriyalarga bo'lib qayd qiladigan AI agent.

## Imkoniyatlar

- **Erkin matn**: xodim botga "Sement uchun 500000 so'm to'ladim" kabi xabar
  yozadi, AI (Gemini) summani, turini (kirim/chiqim) va kategoriyasini o'zi
  aniqlaydi. Bitta xabarda bir nechta xarajat/kirim sanab o'tilgan bo'lsa,
  har birini alohida topib oladi.
- **Chek/kvitansiya rasmi**: rasm yuborilsa, AI undan summa va tafsilotlarni
  o'qib oladi (vision), qo'lda yozilgan bir nechta bandli ro'yxatlarni ham
  qo'llab-quvvatlaydi.
- **Ovozli xabar**: Groq (Whisper) orqali matnga o'giriladi, keyin xuddi
  yozma xabar kabi tahlil qilinadi.
- **Kun davomida yig'ish, Daftar orqali tasdiqlash**: matn/ovoz/chekdan
  aniqlangan har bir yozuv darhol (alohida tasdiqlashsiz) tasdiqlanmagan
  holatda saqlanadi va pastdagi doimiy **"📒 Daftar (N)"** tugmasidagi son
  yangilanib boradi. Hech biri hisobotga yoki Sheetga tushmaydi, toki xodim
  shu tugmani (yoki `/daftar` buyrug'ini) bosib ro'yxatni ochib, bitta
  "✏️ Tahrirlash" va bitta "🗑 O'chirish" tugmasi orqali (raqamini tanlab)
  kerakli yozuvlarni to'g'irlab/olib tashlab, "✅ Hammasini tasdiqlash"ni
  bosmaguncha. Har bir xodim faqat o'zi kiritgan tasdiqlanmagan yozuvlarni
  ko'radi.
- **Bank ko'chirmasi**: `.xlsx`/`.csv` fayl yuborilsa, har bir qator avtomatik
  o'qiladi va AI yordamida kategoriyalarga bo'linadi; bu alohida, bir martalik
  ko'rib chiqish bosqichi bo'lgani uchun tasdiqlangach darhol bazaga va
  Sheetga tushadi (kun oxirini kutmaydi).
- **Loyihalar (obyektlar)**: xodimlar o'zlari loyiha tanlamaydi - buni faqat
  `ADMIN_USER_IDS` da ko'rsatilgan administrator boshqaradi, `/loyiha_biriktir
  <telegram_id> <loyiha nomi>` buyrug'i bilan (loyiha mavjud bo'lmasa avtomatik
  yaratiladi). Yangi xodim botga `/start` bosganda, agar u hali biriktirilmagan
  bo'lsa, barcha adminlarga xodim ismi/ID'si va mavjud loyihalar tugmalari
  bilan xabar boradi - bitta tugma bosish bilan biriktirish mumkin (yangi
  loyiha kerak bo'lsa, tayyor `/loyiha_biriktir` buyrug'i xabarda ko'rsatiladi,
  shuni matn qilib yuborish kifoya). Shundan keyin o'sha xodimning barcha
  xabarlari avtomatik shu loyihaga tegishli bo'ladi - u boshqa loyihaga o'zi
  o'ta olmaydi. Barcha tranzaksiyalar va hisobotlar loyiha bo'yicha ham
  ajratiladi.
- **Hisobotlar**: `/report` buyrug'i bilan bugungi/haftalik/oylik yoki
  boshidan hozirgacha (kumulyativ, kun-kunlar qatorlari uzluksiz davom
  etadigan) hisobot Excel faylda (tranzaksiyalar ro'yxati + loyiha/kategoriya
  bo'yicha jamlanma) yuboriladi.
- Botdan faqat `ALLOWED_USER_IDS` da ko'rsatilgan Telegram foydalanuvchilari
  foydalana oladi.
- **Google Sheets sinxronizatsiyasi (ixtiyoriy)**: `/daftar` orqali
  tasdiqlangan (yoki bank ko'chirmasidan tasdiqlangan) har bir tranzaksiya
  avtomatik ravishda mavjud Google Sheet jadvaliga qator bo'lib qo'shiladi
  (pastdagi "Google Sheetsga ulash" bo'limiga qarang).
- **Avtomatik kunlik hisobot (ixtiyoriy)**: `REPORT_RECIPIENT_ID` sozlansa
  (masalan CEOning Telegram ID'si), har kuni soat **21:00 (Toshkent vaqti)**
  da o'sha kuni tasdiqlangan barcha loyihalar/xodimlar bo'yicha BITTA
  umumlashtirilgan matnli hisobot avtomatik shu Telegram ID'ga yuboriladi
  (agar o'sha kuni birorta ham tasdiqlangan yozuv bo'lmasa, hisobot
  yuborilmaydi). Xodimlar kun davomida `/daftar`dan tasdiqlaganda CEOga
  alohida xabar ketmaydi - hammasi kechqurungi yagona hisobotga
  jamlanadi. Har bir foydalanuvchi o'z ID'sini `/mening_id` orqali bilib
  olishi mumkin.

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
   - `GEMINI_MODEL` (ixtiyoriy, standart: `gemini-2.0-flash-lite` — bepul kvotasi
     `gemini-flash-latest`/`gemini-2.5-flash`ga qaraganda ancha yuqori, shuning
     uchun tez-tez 429 "quota exceeded" xatosiga duch kelmaslik uchun shu
     model tanlangan). Faqat matn xabarlarni tahlil qilishda ishlatiladi.
   - `GEMINI_VISION_MODEL` (ixtiyoriy, standart: `gemini-2.5-flash`) — chek/
     jadval rasmlarini tahlil qilishda ishlatiladi. Rasmdagi ko'p qatorli
     jadvallarni aniq o'qish `flash-lite`dan ko'ra kuchliroq model talab
     qiladi, shuning uchun rasm tahlili uchun alohida, kuchliroq model
     tanlangan (matn tahlilidan farqli, chunki rasm kamroq yuboriladi).
   - `OPENAI_API_KEY` (ixtiyoriy — Gemini xato bersa (masalan kvota tugasa),
     bot avtomatik shu bilan tahlil qilishga o'tadi, shuning uchun ikkala
     xizmat ham to'xtab qolmaguncha bot ishlashda davom etadi)
   - `OPENAI_MODEL` (ixtiyoriy, standart: `gpt-4o-mini`)
   - `GROQ_API_KEY` (ovozli xabarlar uchun)
   - `ALLOWED_USER_IDS`
   - `DATABASE_URL` (yuqoridagi 2-band)
4. Bot uzluksiz ishlaydigan background process (long polling), tashqi HTTP
   portini talab qilmaydi — Railway'da xizmat turini "Worker" qilib
   qo'yishingiz mumkin (health-check/portni o'chirib qo'ying, aks holda
   Railway HTTP javob kutib xizmatni "unhealthy" deb belgilashi mumkin).
5. Deploy tugagach, botni Telegram'da `/start` bilan sinab ko'ring.

## Google Sheetsga ulash (ixtiyoriy)

Bu integratsiya Google Cloud Console / service account talab qilmaydi — faqat
mavjud Google Sheet faylingiz ichida bir necha qadam:

1. Sheet faylingizni oching → **Extensions → Apps Script**.
2. Ochilgan muharrirdagi namunaviy kodni o'chirib, shu repodagi
   `docs/google_sheets_webapp.gs` faylining butun mazmunini joylashtiring.
3. Skript boshidagi `SECRET` qiymatini o'zingiz o'ylab topgan uzun, tasodifiy
   matn bilan almashtiring (bu — botning sizning jadvalingizga yozish uchun
   "paroli"). `SHEET_NAME` qiymati jadvaldagi qatorlar yoziladigan varaq nomi
   bilan bir xil bo'lishi kerak (masalan `Xarajatlar`), va o'sha varaqda
   quyidagi tartibda sarlavha qatori bo'lishi shart:
   `Sana, Nomi / material, Miqdor, Birlik, Birim narx, Umumiy summa,
   Kategoriya, Kim yozdi, Loyiha, To'lov turi, Asl xabar, Izoh`.
4. **Deploy → New deployment** → turi **Web app**: "Execute as" = **Me**,
   "Who has access" = **Anyone**. Deploy tugmasini bosing va hosil bo'lgan
   Web App URL manzilini nusxalab oling.
5. Botning muhit o'zgaruvchilariga (Railway → Variables) qo'shing:
   - `SHEETS_WEBHOOK_URL` — 4-qadamdagi Web App URL
   - `SHEETS_WEBHOOK_SECRET` — 3-qadamda o'rnatgan SECRET qiymati

Shundan so'ng `/daftar` orqali tasdiqlangan (yoki bank ko'chirmasidan
tasdiqlangan) har bir tranzaksiya avtomatik shu jadvalga qator bo'lib
qo'shiladi. Agar bu ikki o'zgaruvchi bo'sh qoldirilsa, sinxronizatsiya
oddiygina o'chiq turadi — bot ishlashiga ta'sir qilmaydi.

## Loyiha tuzilishi

```
app/
  bot.py               - bot kirish nuqtasi
  config.py            - .env sozlamalari
  db.py                - SQLAlchemy async engine/session
  models.py             - User, Category, Transaction, Project
  access.py             - foydalanuvchilarni ruxsat bo'yicha filtrlash
  handlers/
    common.py            - loyiha talab qilish + matn tahlilini tasdiqlanmagan tranzaksiya sifatida saqlash (umumiy)
    day_review.py         - /daftar: kunlik tasdiqlanmagan yozuvlarni ko'rib chiqish/tahrirlash/tasdiqlash
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
    sheets.py              - tasdiqlangan tranzaksiyalarni Google Sheetsga yuborish
docs/
  google_sheets_webapp.gs - Google Apps Script Web App kodi (Sheetsga ulash uchun)
```

## Kategoriyalar

**Chiqim**: Qurilish materiallari, Ish haqi, Transport, Jihoz va asboblar,
Ijara, Kommunal to'lovlar, Soliq va yig'imlar, Boshqa xarajat.

**Kirim**: Mijoz to'lovi, Kredit / investitsiya, Boshqa daromad.

Yangi kategoriya kerak bo'lsa, AI mos kategoriya topilmasa avtomatik
"Boshqa xarajat"/"Boshqa daromad" ga yozadi — kerak bo'lsa
`app/services/categories.py` dagi ro'yxatga qo'shish mumkin.
