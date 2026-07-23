# Qurilish kompaniyasi uchun xarajat/daromad Telegram boti

Telegram bot orqali kunlik xarajatlar va bank hisobidan o'tadigan pullarni
(kirim/chiqim) kategoriyalarga bo'lib qayd qiladigan AI agent.

## Imkoniyatlar

- **Erkin matn**: xodim botga "Sement uchun 500000 so'm to'ladim" kabi xabar
  yozadi, AI (Claude) summani, turini (kirim/chiqim) va kategoriyasini o'zi
  aniqlaydi. Saqlashdan oldin tasdiqlash so'raladi.
- **Chek/kvitansiya rasmi**: rasm yuborilsa, AI undan summa va tafsilotlarni
  o'qib oladi (vision).
- **Bank ko'chirmasi**: `.xlsx`/`.csv` fayl yuborilsa, har bir qator avtomatik
  o'qiladi va AI yordamida kategoriyalarga bo'linadi, so'ng tasdiqlangandan
  keyin bazaga saqlanadi.
- **Hisobotlar**: `/report` buyrug'i bilan bugungi/haftalik/oylik hisobot
  Excel faylda (tranzaksiyalar ro'yxati + kategoriyalar bo'yicha jamlanma)
  yuboriladi.
- Botdan faqat `ALLOWED_USER_IDS` da ko'rsatilgan Telegram foydalanuvchilari
  foydalana oladi.

## O'rnatish

1. `.env.example` faylini `.env` ga nusxalab, quyidagilarni to'ldiring:
   - `BOT_TOKEN` — @BotFather dan olingan token
   - `ANTHROPIC_API_KEY` — Anthropic API kaliti
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

## Loyiha tuzilishi

```
app/
  bot.py               - bot kirish nuqtasi
  config.py            - .env sozlamalari
  db.py                - SQLAlchemy async engine/session
  models.py             - User, Category, Transaction
  access.py             - foydalanuvchilarni ruxsat bo'yicha filtrlash
  handlers/            - Telegram xabar/callback handlerlari
  services/
    ai_parser.py        - Claude orqali matn/rasm/bank qatorlarini tahlil
    bank_import.py       - bank ko'chirmasi fayllarini o'qish
    excel_export.py      - hisobot Excel fayl generatsiyasi
    categories.py        - standart kategoriyalar
    users.py              - foydalanuvchi CRUD
```

## Kategoriyalar

**Chiqim**: Qurilish materiallari, Ish haqi, Transport, Jihoz va asboblar,
Ijara, Kommunal to'lovlar, Soliq va yig'imlar, Boshqa xarajat.

**Kirim**: Mijoz to'lovi, Kredit / investitsiya, Boshqa daromad.

Yangi kategoriya kerak bo'lsa, AI mos kategoriya topilmasa avtomatik
"Boshqa xarajat"/"Boshqa daromad" ga yozadi — kerak bo'lsa
`app/services/categories.py` dagi ro'yxatga qo'shish mumkin.
