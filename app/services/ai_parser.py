import base64
import json
from datetime import date
from typing import Any

from anthropic import AsyncAnthropic

from app.config import settings

_client = AsyncAnthropic(api_key=settings.anthropic_api_key)

_TRANSACTION_TOOL = {
    "name": "record_transaction",
    "description": "Qurilish kompaniyasi uchun kirim yoki chiqim tranzaksiyasini tuzilgan ko'rinishda qaytaradi.",
    "input_schema": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["income", "expense"],
                "description": "income = kirim (pul kelishi), expense = chiqim (xarajat)",
            },
            "amount": {
                "type": "number",
                "description": "Summasi (faqat raqam, valyuta belgisisiz), so'mda",
            },
            "category": {
                "type": "string",
                "description": "Berilgan kategoriyalar ro'yxatidan eng mos kelgani, aks holda 'Boshqa xarajat' yoki 'Boshqa daromad'",
            },
            "description": {
                "type": "string",
                "description": "Qisqa tavsif (nima uchun to'lov/kirim)",
            },
            "counterparty": {
                "type": "string",
                "description": "To'lov qilingan/qabul qilingan tomon (agar mavjud bo'lsa), aks holda bo'sh qatr",
            },
            "occurred_on": {
                "type": "string",
                "description": "Sana YYYY-MM-DD formatida. Agar matnda sana ko'rsatilmagan bo'lsa, berilgan bugungi sanani ishlating.",
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "low"],
                "description": "Agar matn tushunarsiz yoki summa aniq bo'lmasa 'low', aks holda 'high'",
            },
        },
        "required": ["type", "amount", "category", "description", "occurred_on", "confidence"],
    },
}


def _extract_tool_input(message: Any) -> dict:
    for block in message.content:
        if block.type == "tool_use":
            return block.input
    raise ValueError("AI javobida tool_use bloki topilmadi")


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
        f"Quyidagi xabarni tahlil qil va record_transaction tool orqali natijani qaytar:\n"
        f'"{text}"'
    )
    message = await _client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        tools=[_TRANSACTION_TOOL],
        tool_choice={"type": "tool", "name": "record_transaction"},
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_tool_input(message)


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
        "aniqlab, record_transaction tool orqali natijani qaytar. Agar chekdagi sana o'qib bo'lmasa, "
        "bugungi sanani ishlat."
    )
    message = await _client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        tools=[_TRANSACTION_TOOL],
        tool_choice={"type": "tool", "name": "record_transaction"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64_image},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    return _extract_tool_input(message)


_BANK_ROW_TOOL = {
    "name": "categorize_bank_rows",
    "description": "Bank ko'chirmasidagi har bir qatorga kirim/chiqim kategoriyasini biriktiradi.",
    "input_schema": {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "row_index": {"type": "integer"},
                        "category": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["row_index", "category", "description"],
                },
            }
        },
        "required": ["results"],
    },
}


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
        "va qisqa tushunarli tavsifni tanla, keyin categorize_bank_rows tool orqali natijani qaytar:\n\n"
        f"{json.dumps(rows, ensure_ascii=False)}"
    )
    message = await _client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        tools=[_BANK_ROW_TOOL],
        tool_choice={"type": "tool", "name": "categorize_bank_rows"},
        messages=[{"role": "user", "content": prompt}],
    )
    parsed = _extract_tool_input(message)
    return {item["row_index"]: item for item in parsed["results"]}
