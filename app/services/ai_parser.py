import base64
import json
from datetime import date
from typing import Any

import aiohttp

from app.config import settings

_GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

_TRANSACTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "type": {
            "type": "STRING",
            "enum": ["income", "expense"],
            "description": "income = kirim (pul kelishi), expense = chiqim (xarajat)",
        },
        "amount": {
            "type": "NUMBER",
            "description": "Summasi (faqat raqam, valyuta belgisisiz), so'mda",
        },
        "category": {
            "type": "STRING",
            "description": "Berilgan kategoriyalar ro'yxatidan eng mos kelgani, aks holda 'Boshqa xarajat' yoki 'Boshqa daromad'",
        },
        "description": {
            "type": "STRING",
            "description": "Qisqa tavsif (nima uchun to'lov/kirim)",
        },
        "counterparty": {
            "type": "STRING",
            "description": "To'lov qilingan/qabul qilingan tomon (agar mavjud bo'lsa), aks holda bo'sh qatr",
        },
        "occurred_on": {
            "type": "STRING",
            "description": "Sana YYYY-MM-DD formatida. Agar matnda sana ko'rsatilmagan bo'lsa, berilgan bugungi sanani ishlating.",
        },
        "quantity": {
            "type": "NUMBER",
            "description": "Agar matnda miqdor (masalan '10 litr', '5 qop') ko'rsatilgan bo'lsa shu son, aks holda 0",
        },
        "unit": {
            "type": "STRING",
            "description": "Miqdor birligi (masalan 'litr', 'qop', 'tonna', 'dona'), agar ko'rsatilmagan bo'lsa bo'sh qator",
        },
        "unit_price": {
            "type": "NUMBER",
            "description": "Agar matnda birlik narxi alohida ko'rsatilgan bo'lsa shu son (so'mda), aks holda 0",
        },
        "payment_type": {
            "type": "STRING",
            "enum": ["naqd", "bank"],
            "description": "To'lov turi: naqd pul yoki bank orqali. Matnda ko'rsatilmagan bo'lsa 'naqd' deb ol.",
        },
        "confidence": {
            "type": "STRING",
            "enum": ["high", "low"],
            "description": "Agar matn tushunarsiz yoki summa aniq bo'lmasa 'low', aks holda 'high'",
        },
    },
    "required": ["type", "amount", "category", "description", "occurred_on", "confidence"],
}

_BANK_ROWS_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "results": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "row_index": {"type": "INTEGER"},
                    "category": {"type": "STRING"},
                    "description": {"type": "STRING"},
                },
                "required": ["row_index", "category", "description"],
            },
        }
    },
    "required": ["results"],
}


async def _generate_json(parts: list[dict[str, Any]], schema: dict[str, Any]) -> dict:
    url = _GEMINI_API_URL.format(model=settings.gemini_model)
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "response_schema": schema,
        },
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            params={"key": settings.gemini_api_key},
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Gemini API error {resp.status}: {text}")
            data = await resp.json()

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Gemini javobida matn topilmadi: {data}") from e
    return json.loads(text)


async def parse_expense_text(
    text: str,
    expense_categories: list[str],
    income_categories: list[str],
    today: date,
) -> dict:
    prompt = (
        f"Bugungi sana: {today.isoformat()}\n"
        f"Chiqim kategoriyalari: {', '.join(expense_categories)}\n"
        f"Kirim kategoriyalari: {', '.join(income_categories)}\n\n"
        "Eslatma: ba'zida summa to'g'ridan-to'g'ri aytilmaydi, balki miqdor va birlik narxi alohida "
        "ko'rsatiladi (masalan \"10 litrdan 80 mingdan\" yoki \"5 qop 60 ming dan\") - bunday holatda "
        "ularni ko'paytirib umumiy summani hisobla (10 x 80000 = 800000). Faqat summani ikkala tomon "
        "ham noaniq bo'lganda 'low' confidence qo'y.\n\n"
        f"Quyidagi xabarni tahlil qil:\n"
        f'"{text}"'
    )
    return await _generate_json([{"text": prompt}], _TRANSACTION_SCHEMA)


async def parse_receipt_image(
    image_bytes: bytes,
    media_type: str,
    expense_categories: list[str],
    income_categories: list[str],
    today: date,
) -> dict:
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    prompt = (
        f"Bugungi sana: {today.isoformat()}\n"
        f"Chiqim kategoriyalari: {', '.join(expense_categories)}\n"
        f"Kirim kategoriyalari: {', '.join(income_categories)}\n\n"
        "Bu rasm - chek yoki to'lov kvitansiyasi. Undan summani, sanani va nimaga sarflanganini "
        "aniqlab natijani qaytar. Agar chekdagi sana o'qib bo'lmasa, bugungi sanani ishlat."
    )
    parts = [
        {"inline_data": {"mime_type": media_type, "data": b64_image}},
        {"text": prompt},
    ]
    return await _generate_json(parts, _TRANSACTION_SCHEMA)


async def categorize_bank_rows(
    rows: list[dict],
    expense_categories: list[str],
    income_categories: list[str],
) -> dict[int, dict]:
    """rows: list of {row_index, type(income/expense), amount, raw_description}"""
    prompt = (
        f"Chiqim kategoriyalari: {', '.join(expense_categories)}\n"
        f"Kirim kategoriyalari: {', '.join(income_categories)}\n\n"
        "Quyidagi bank tranzaksiyalari ro'yxati berilgan (JSON). Har biriga eng mos kategoriyani "
        "va qisqa tushunarli tavsifni tanla:\n\n"
        f"{json.dumps(rows, ensure_ascii=False)}"
    )
    parsed = await _generate_json([{"text": prompt}], _BANK_ROWS_SCHEMA)
    return {item["row_index"]: item for item in parsed["results"]}
