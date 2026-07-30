import base64
import json
import logging
from datetime import date
from typing import Any

import aiohttp

from app.config import settings

logger = logging.getLogger(__name__)

_GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"

def _category_field(expense_categories: list[str], income_categories: list[str]) -> dict:
    """Constrains the category to an ENUM of exactly the categories that
    exist today, instead of a freeform string. A freeform string let the
    model invent slightly-off names (typos, synonyms, translations), each
    of which silently created a brand new stray category via
    get_or_create_category - an enum makes that structurally impossible."""
    return {
        "type": "STRING",
        "enum": expense_categories + income_categories,
        "description": (
            "Berilgan ro'yxatdagi kategoriyalardan ANIQ bittasi - ro'yxatda yo'q boshqa nom yozish "
            "mumkin emas. Chiqim uchun chiqim kategoriyalaridan, kirim uchun kirim kategoriyalaridan "
            "eng mos kelganini tanla; hech biri to'g'ri kelmasa 'Boshqa xarajat' yoki 'Boshqa daromad'."
        ),
    }


def _build_transaction_item_schema(expense_categories: list[str], income_categories: list[str]) -> dict:
    return {
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
            "category": _category_field(expense_categories, income_categories),
            "description": {
                "type": "STRING",
                "description": (
                    "Aniq mahsulot yoki xizmat nomi (masalan 'Benzin', 'Go'sht xaridi', "
                    "'Sement', 'Ish haqi') - matnda/rasmda qanday aytilgan/yozilgan bo'lsa shunga "
                    "yaqin, tabiiy nom. HECH QACHON 'xarajati' so'zini oxiriga qo'shib yozma "
                    "('Benzin xarajati' EMAS, faqat 'Benzin'; 'Sement xarajati' EMAS, faqat "
                    "'Sement') - bu keraksiz va takrorlanuvchi."
                ),
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
                "description": (
                    "Miqdor birligi. ENG MUHIMI: agar manba matnda/jadvalda/rasmda birlik ALOHIDA "
                    "USTUN yoki so'z sifatida ANIQ ko'rsatilgan bo'lsa (masalan jadvalning 'Едины-измер' "
                    "yoki shunga o'xshash ustunida 'DONA', 'KUN', 'M', 'KG' kabi yozilgan bo'lsa), "
                    "O'SHA QIYMATNI AYNAN OLIB YOZ - o'zingcha boshqacha birlik bilan almashtirma yoki "
                    "'balki bu kun/xizmatga o'xshaydi' deb qayta talqin qilma, hatto nom xarajat turiga "
                    "boshqacharoq mos kelayotgandek tuyulsa ham. Faqat birlik HECH QAYERDA aniq "
                    "ko'rsatilmagan bo'lsagina, quyidagi standart birliklardan birini o'zing tanla: "
                    "'litr', 'kg', 'm' (chiziqli metr), 'm2', 'm3', 'dona', 'kun', 'qop', 'tonna' "
                    "(masalan qurilish materiallari - odatda 'dona' yoki 'qop', yoqilg'i/bo'yoq/"
                    "suyuqlik - 'litr', sement/qum kabi ommaviy materiallar - 'qop' yoki 'tonna', "
                    "ish haqi/xizmat - 'kun'). Faqat miqdorning o'zi ham noaniq/ko'rsatilmagan "
                    "bo'lsagina bo'sh qator qo'y."
                ),
            },
            "unit_price": {
                "type": "NUMBER",
                "description": (
                    "Bitta birlik narxi (so'mda). Agar matnda to'g'ridan-to'g'ri aytilgan bo'lsa shuni "
                    "ishlat. Agar aytilmagan bo'lsa-yu, miqdor va umumiy summa ma'lum bo'lsa, "
                    "umumiy summani miqdorga bo'lib hisobla. Miqdorning o'zi noma'lum bo'lsa 0 qo'y."
                ),
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


def _build_transactions_schema(expense_categories: list[str], income_categories: list[str]) -> dict:
    return {
        "type": "OBJECT",
        "properties": {
            "transactions": {
                "type": "ARRAY",
                "description": "Xabardagi/rasmdagi har bir alohida xarajat/kirim uchun bitta element",
                "items": _build_transaction_item_schema(expense_categories, income_categories),
            }
        },
        "required": ["transactions"],
    }


def _build_single_edit_schema(expense_categories: list[str], income_categories: list[str]) -> dict:
    return {
        "type": "OBJECT",
        "properties": {
            "row_index": {
                "type": "INTEGER",
                "description": "Foydalanuvchi tuzatishni so'rayotgan qatorning raqami (ro'yxatda 1 dan boshlanadi)",
            },
            "type": {"type": "STRING", "enum": ["income", "expense"]},
            "amount": {"type": "NUMBER", "description": "Qatorning (tuzatilgandan keyingi) umumiy summasi"},
            "category": _category_field(expense_categories, income_categories),
            "description": {"type": "STRING"},
            "quantity": {"type": "NUMBER"},
            "unit": {"type": "STRING"},
            "unit_price": {"type": "NUMBER"},
            "confidence": {
                "type": "STRING",
                "enum": ["high", "low"],
                "description": "Qaysi qatorni va nimani o'zgartirish kerakligi aniq bo'lmasa 'low'",
            },
        },
        "required": ["row_index", "type", "amount", "category", "description", "confidence"],
    }


def _build_edits_schema(expense_categories: list[str], income_categories: list[str]) -> dict:
    return {
        "type": "OBJECT",
        "properties": {
            "edits": {
                "type": "ARRAY",
                "description": (
                    "Foydalanuvchi ko'rsatmasida nechta qator tuzatishni so'ragan bo'lsa, shuncha "
                    "element - har bir qator uchun alohida"
                ),
                "items": _build_single_edit_schema(expense_categories, income_categories),
            }
        },
        "required": ["edits"],
    }


def _build_bank_rows_schema(expense_categories: list[str], income_categories: list[str]) -> dict:
    return {
        "type": "OBJECT",
        "properties": {
            "results": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "row_index": {"type": "INTEGER"},
                        "category": _category_field(expense_categories, income_categories),
                        "description": {"type": "STRING"},
                    },
                    "required": ["row_index", "category", "description"],
                },
            }
        },
        "required": ["results"],
    }


async def _generate_json_gemini(parts: list[dict[str, Any]], schema: dict[str, Any], model: str | None = None) -> dict:
    url = _GEMINI_API_URL.format(model=model or settings.gemini_model)
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "response_schema": schema,
            # Explicit headroom so a long multi-row table's JSON response
            # can't get silently truncated mid-array (default limits vary
            # by model and a 30+ row table can need several thousand tokens).
            "maxOutputTokens": 16384,
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


def _schema_to_prompt_hint(schema: dict[str, Any], indent: int = 0) -> str:
    """Renders a Gemini-style response_schema as a human-readable field guide,
    since OpenAI's plain JSON mode (used as a fallback) has no schema param -
    the shape has to be spelled out in the prompt text instead."""
    pad = "  " * indent
    node_type = schema["type"]
    if node_type == "OBJECT":
        required = set(schema.get("required", []))
        lines = ["{"]
        for key, sub in schema.get("properties", {}).items():
            marker = "majburiy" if key in required else "ixtiyoriy"
            desc = sub.get("description", "")
            lines.append(f'{pad}  "{key}": {_schema_to_prompt_hint(sub, indent + 1)}  // {marker}. {desc}')
        lines.append(pad + "}")
        return "\n".join(lines)
    if node_type == "ARRAY":
        return f"[{_schema_to_prompt_hint(schema['items'], indent)}, ...]"
    if node_type == "STRING":
        enum = schema.get("enum")
        return f"\"{' | '.join(enum)}\"" if enum else '"matn"'
    if node_type in ("NUMBER", "INTEGER"):
        return "raqam"
    return "aniqlanmagan"


def _parts_to_openai_content(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    content = []
    for part in parts:
        if "text" in part:
            content.append({"type": "text", "text": part["text"]})
        elif "inline_data" in part:
            mime = part["inline_data"]["mime_type"]
            b64 = part["inline_data"]["data"]
            content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
    return content


async def _generate_json_openai(parts: list[dict[str, Any]], schema: dict[str, Any]) -> dict:
    content = _parts_to_openai_content(parts)
    content.append(
        {
            "type": "text",
            "text": (
                "\n\nFaqat quyidagi ko'rinishdagi JSON obyekt qaytar, boshqa hech qanday matn, "
                "izoh yoki kod bloki yozma:\n" + _schema_to_prompt_hint(schema)
            ),
        }
    )
    payload = {
        "model": settings.openai_model,
        "messages": [{"role": "user", "content": content}],
        "response_format": {"type": "json_object"},
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(
            _OPENAI_CHAT_URL,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"OpenAI API error {resp.status}: {text}")
            data = await resp.json()

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"OpenAI javobida matn topilmadi: {data}") from e
    return json.loads(text)


async def _generate_json(parts: list[dict[str, Any]], schema: dict[str, Any], model: str | None = None) -> dict:
    """Tries Gemini first; if it fails (quota, rate-limit, network, etc.) and
    an OpenAI key is configured, transparently retries via OpenAI so a single
    provider's outage/quota doesn't take the bot down."""
    try:
        return await _generate_json_gemini(parts, schema, model)
    except Exception as gemini_error:
        if not settings.openai_api_key:
            raise
        logger.warning("Gemini failed (%s), falling back to OpenAI", gemini_error)
        try:
            return await _generate_json_openai(parts, schema)
        except Exception:
            logger.exception("OpenAI fallback also failed")
            raise


async def _generate_text_multimodal_gemini(parts: list[dict[str, Any]], model: str | None = None) -> str:
    url = _GEMINI_API_URL.format(model=model or settings.gemini_model)
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        # A dense 30+ row table transcribed verbatim (one line per row) can
        # run to a few thousand tokens - same headroom reasoning as the JSON
        # extraction path.
        "generationConfig": {"maxOutputTokens": 8192},
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
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Gemini javobida matn topilmadi: {data}") from e


async def _generate_text_multimodal_openai(parts: list[dict[str, Any]]) -> str:
    content = _parts_to_openai_content(parts)
    payload = {"model": settings.openai_model, "messages": [{"role": "user", "content": content}]}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            _OPENAI_CHAT_URL,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"OpenAI API error {resp.status}: {text}")
            data = await resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"OpenAI javobida matn topilmadi: {data}") from e


async def _generate_text_multimodal(parts: list[dict[str, Any]], model: str | None = None) -> str:
    try:
        return await _generate_text_multimodal_gemini(parts, model)
    except Exception as gemini_error:
        if not settings.openai_api_key:
            raise
        logger.warning("Gemini failed (%s), falling back to OpenAI", gemini_error)
        try:
            return await _generate_text_multimodal_openai(parts)
        except Exception:
            logger.exception("OpenAI fallback also failed")
            raise


async def _generate_text_gemini(prompt: str) -> str:
    url = _GEMINI_API_URL.format(model=settings.gemini_model)
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        # Currently only used for the group Q&A's short conversational
        # replies - capping output keeps generation (and thus response
        # time) fast, on top of the prompt already asking for brevity.
        "generationConfig": {"maxOutputTokens": 300},
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
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Gemini javobida matn topilmadi: {data}") from e


async def _generate_text_openai(prompt: str) -> str:
    payload = {"model": settings.openai_model, "messages": [{"role": "user", "content": prompt}]}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            _OPENAI_CHAT_URL,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"OpenAI API error {resp.status}: {text}")
            data = await resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"OpenAI javobida matn topilmadi: {data}") from e


async def _generate_text(prompt: str) -> str:
    """Plain free-text generation (no JSON schema) - used for the group Q&A
    feature, which answers in natural language rather than extracting
    structured data. Same Gemini-first, OpenAI-fallback behavior."""
    try:
        return await _generate_text_gemini(prompt)
    except Exception as gemini_error:
        if not settings.openai_api_key:
            raise
        logger.warning("Gemini failed (%s), falling back to OpenAI", gemini_error)
        return await _generate_text_openai(prompt)


async def answer_group_question(question: str, data_summary: str, persona_name: str) -> str:
    """Answers a message addressed to the bot (in a group, or a private
    message that didn't parse as an expense/income entry). Strictly scoped
    to the company's projects/finances: a genuine data question gets an
    answer grounded ONLY in the precomputed numbers (never invented); a
    general finance/project-management question gets brief practical
    advice; anything unrelated gets a plain "can't help with that" reply -
    no persona, no small talk."""
    prompt = (
        f"Sening isming {persona_name}. Sen qurilish kompaniyasining loyihalar va xarajat/daromadlarini "
        "kuzatuvchi yordamchi botsan. Oddiy va tabiiy yoz - sun'iy intellektga o'xshamasin. Javob "
        "1-3 gapdan oshmasin.\n\n"
        "Faqat quyidagi holatlarda javob ber:\n"
        "1. Savol kompaniyaning loyihalari yoki moliyaviy ma'lumotlariga oid bo'lsa: FAQAT quyida "
        "berilgan aniq hisoblangan ma'lumotlarga asoslanib javob ber - hech qanday raqamni o'zingdan "
        "o'ylab topma, uzun kirish/xulosa yozma, ro'yxat berma. Agar javob uchun kerakli ma'lumot "
        "quyida yo'q bo'lsa, bir gapda shuni ayt.\n"
        "2. Savol moliya yoki loyihalarni boshqarish bo'yicha umumiy maslahat so'rasa (masalan "
        "xarajatlarni qanday kamaytirish, byudjetni qanday nazorat qilish, materiallarni qanday "
        "tejash kabi): qisqa va foydali maslahat ber.\n\n"
        "Boshqa har qanday savol yoki xabar uchun (shaxsiy suhbat, aloqasi yo'q mavzular, hazil va "
        "hokazo): faqat shuni yoz - \"Kechirasiz, men faqat loyihalar va moliya bo'yicha savollarga "
        "javob bera olaman.\" - boshqa hech narsa qo'shma.\n\n"
        f"Mavjud ma'lumotlar:\n{data_summary}\n\n"
        f'Xabar: "{question}"'
    )
    return await _generate_text(prompt)


async def parse_expense_text(
    text: str,
    expense_categories: list[str],
    income_categories: list[str],
    today: date,
) -> list[dict]:
    prompt = (
        f"Bugungi sana: {today.isoformat()}\n"
        f"Chiqim kategoriyalari: {', '.join(expense_categories)}\n"
        f"Kirim kategoriyalari: {', '.join(income_categories)}\n\n"
        "ENG MUHIM QOIDA - summa miqdorga ko'paytirilmasin: xabarda miqdor (masalan \"50 tonna\", "
        "\"6 kishi\", \"20 kub\") va undan keyin bitta raqam kelsa, O'SHA RAQAM ODATDA O'SHA BUTUN "
        "MIQDOR UCHUN JAMI (umumiy) summa - bitta birlik narxi EMAS. Masalan \"sement 50 ton 500000\" "
        "degani - 50 tonna sement uchun JAMI 500000 so'm (natija: amount=500000, quantity=50, "
        "unit=\"tonna\") - HECH QACHON 500000 ni 50 ga ko'paytirma. Xuddi shunday \"ovqatlanish 300000 "
        "6 kishi\" - 6 kishi uchun JAMI 300000 (amount=300000), 6 ga ko'paytirilmaydi; \"qum 20 kub "
        "2650000\" - JAMI 2650000 (amount=2650000), 20 ga ko'paytirilmaydi.\n"
        "Miqdor va birlik narxini ko'paytirish FAQAT quyidagi holatda ruxsat etiladi: matnda ANIQ "
        "birlik narxini bildiruvchi so'z/qo'shimcha bo'lsa - \"-dan\"/\"-dan\" qo'shimchasi ikkala "
        "songa ham qo'shilgan holda (\"10 litrdan 80 mingdan\"), yoki \"donasi\", \"kub(m)i\", "
        "\"tonnasi\", \"har biriga\", \"birligi\" kabi so'zlar bilan bitta birlik narxi alohida "
        "ko'rsatilgan bo'lsa (\"5 qop, donasi 60 ming\", \"qumning kubi 130 ming, 20 kub oldim\"). "
        "Shunday aniq ko'rsatkich bo'lgandagina ikkalasini ko'paytirib umumiy summani hisobla (masalan "
        "10 x 80000 = 800000). Bunday ko'rsatkich yo'q bo'lsa, ikkinchi raqamni har doim JAMI summa deb "
        "qabul qil, hech qachon miqdorga ko'paytirma. Faqat summaning o'zi butunlay noaniq bo'lganda "
        "'low' confidence qo'y.\n\n"
        "Muhim: xabarda bir nechta alohida xarajat/kirim aytilgan bo'lishi mumkin - istalgan formatda: "
        "vergul bilan, yangi qatorda, \"va\" bilan, raqamlangan ro'yxat (\"1. ...\", \"2. ...\"), chiziqcha "
        "bilan boshlangan ro'yxat (\"- ...\") yoki ularning aralashmasi (masalan \"sement uchun 500000, "
        "benzin uchun 100000\" yoki bir nechta qatorli ro'yxat). Format qanday bo'lishidan qat'i nazar, "
        "HAR BIR alohida band uchun alohida element qaytar - birinchisini emas, hammasini - va agar "
        "ro'yxat oxirida \"JAMI\"/umumiy summa qatori bo'lsa, uni alohida element sifatida QO'SHMA (u "
        "faqat tekshirish uchun, elementlarning yig'indisi bilan solishtirib ko'r). Agar xabarda faqat "
        "bitta xarajat/kirim bo'lsa, bitta elementli ro'yxat qaytar.\n\n"
        "Miqdor va birlik haqida: har bir band uchun faqat BITTA birlik bo'lishi kerak (masalan yo "
        "\"dona\" yoki \"kg\", ikkalasi birga emas; vaqt birligini miqdor bilan aralashtirma - \"5 kun\" "
        "muddat, \"5 dona\" son). Agar matnda ikki xil birlik bir-biriga zid keladi yoki miqdor/birlik "
        "chindan ham noaniq bo'lsa, o'zingcha taxmin qilib to'qib chiqarma - shu bandni 'low' confidence "
        "bilan belgila.\n\n"
        "Miqdorni sig'im/hajm so'zi bilan aralashtirmaslik: \"12 kishilik stol\", \"6 o'rindiqli divan\" "
        "kabi \"-lik\"/\"o'rindiqli\" qo'shimchasi bitta buyumning SIG'IMINI (u nechta odamga mo'ljallangan) "
        "bildiradi, sotib olingan buyum SONINI emas - bunday holda, agar boshqa aniq son ko'rsatilmagan "
        "bo'lsa, quantity=1 deb ol (masalan \"12 kishilik stol\" - bitta stol, quantity=1, description "
        "ichida \"12 kishilik\" so'zini saqlab qol). Xuddi shunday \"2 qavat uchun\" kabi maqsad/joy "
        "izohini ham miqdor deb qabul qilma (\"2 qavat uchun divan\" - bu nechta divan ekanini "
        "bildirmaydi, qayerda ishlatilishini bildiradi) - bunday holatda ham aniq son yo'q bo'lsa "
        "quantity=1 deb ol, taxmin qilib boshqa son yozma.\n\n"
        "Valyuta haqida: agar summa oldida/keyinida \"$\" belgisi yoki \"dollar\"/\"dollarda\" so'zi "
        "bo'lsa, bu AQSH dollarida degani - bunday holda summani hech qachon xuddi so'm sifatida "
        "qabul qilma va o'zingcha kursga ko'paytirib ham hisoblama (aniq bugungi kurs senga noma'lum). "
        "Bunday holatda shu bandga 'low' confidence qo'y, description'ga aslida qancha va qaysi "
        "valyutada yozilganini ko'rsat (masalan \"2500 dollar\"), summa maydoniga esa xuddi shu sonni "
        "(2500) yoz - foydalanuvchi buni so'mga o'zi aniqlashtirib qayta yozadi.\n\n"
        f"Quyidagi xabarni tahlil qil:\n"
        f'"{text}"'
    )
    schema = _build_transactions_schema(expense_categories, income_categories)
    result = await _generate_json([{"text": prompt}], schema)
    return result["transactions"]


async def _transcribe_table_image(image_bytes: bytes, media_type: str) -> str:
    """Stage 1 of receipt parsing: a pure verbatim transcription pass, with
    no JSON schema to satisfy at the same time. Doing OCR and schema-fitting
    in a single call competes for the model's attention on dense tables
    (20-30+ rows) - it's exactly where names and amounts from adjacent rows
    get swapped or merged. Splitting "read carefully" from "structure what
    was read" into two calls made the row-misalignment failures far rarer in
    testing on large tables."""
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    prompt = (
        "Bu rasm - chek, kvitansiya, qo'lda yozilgan xarid ro'yxati yoki jadval (masalan Excel "
        "skrinshoti). Vazifang: HECH NARSANI hisoblamasdan, tuzatmasdan yoki tushunmasdan, faqat "
        "jadvaldagi HAR BIR qatorni SO'ZMA-SO'Z ko'chirib yozish.\n\n"
        "1. Avval jadvalda nechta qator borligini sanab chiq.\n"
        "2. Har bir qatorni CHAP TOMONDAN O'NGGA, yuqoridan pastga, alohida-alohida o'qi va aynan shu "
        "formatda yoz (bitta qator = bitta satr):\n"
        "<qator raqami>) <nomi> | <miqdori> <birligi> | <summasi>\n"
        "3. Har bir qatorning nomi, miqdori, birligi va summasi FAQAT O'SHA BIR QATORNING o'zidan "
        "olinishi kerak - hech qachon bitta qatorning ma'lumotini qo'shni (keyingi yoki oldingi) "
        "qatorning ma'lumoti bilan aralashtirma yoki almashtirma.\n"
        "4. Qatorni aniq o'qiy olmasang ham (xira, qiyshiq va h.k.), qo'lingdan kelganini yoz va "
        "satr oxiriga \"(aniq emas)\" deb qo'sh - qatorni tashlab ketma, lekin qolganlarini ham "
        "joyidan siljitmasdan davom ettir.\n"
        "5. Jadvalda lotin va kirill yozuvi aralash bo'lishi mumkin (masalan \"Профиль\", \"Саморез\") "
        "- ikkalasini ham bir xil diqqat bilan o'qi.\n"
        "6. Agar oxirida \"ИТОГО\"/\"JAMI\"/umumiy summa qatori bo'lsa, uni ham \"JAMI: <summa>\" deb "
        "alohida yoz.\n"
        "7. Boshqa hech qanday izoh, sarlavha yoki tushuntirish yozma - faqat jadval qatorlari."
    )
    parts = [
        {"inline_data": {"mime_type": media_type, "data": b64_image}},
        {"text": prompt},
    ]
    return await _generate_text_multimodal(parts, model=settings.gemini_vision_model)


async def parse_receipt_image(
    image_bytes: bytes,
    media_type: str,
    expense_categories: list[str],
    income_categories: list[str],
    today: date,
) -> list[dict]:
    transcript = await _transcribe_table_image(image_bytes, media_type)
    prompt = (
        f"Bugungi sana: {today.isoformat()}\n"
        f"Chiqim kategoriyalari: {', '.join(expense_categories)}\n"
        f"Kirim kategoriyalari: {', '.join(income_categories)}\n\n"
        "Quyida chek/jadval rasmidan qator-qator ko'chirilgan matn berilgan. Har bir qatorni "
        "ALOHIDA element sifatida qaytar - hech birini o'tkazib yubormasdan, birlashtirmasdan yoki "
        "qayta tartibga solmasdan, aynan shu tartibda. \"(aniq emas)\" deb belgilangan qatorlarga "
        "'low' confidence qo'y. \"JAMI:\" bilan boshlangan qatorni natijaga alohida element sifatida "
        "QO'SHMA - faqat tekshirish uchun undan foydalan (elementlar yig'indisi shu summaga mos "
        "kelishini tekshir).\n\n"
        "Miqdor haqida: matnda ko'rsatilgan summa har doim o'sha qatorning UMUMIY (jami) summasi - "
        "uni miqdorga ko'paytirma, faqat aynan shunday yoz.\n\n"
        f"Jadval matni:\n{transcript}\n\n"
        "Agar chekdagi/jadvaldagi sana ko'rsatilmagan bo'lsa, bugungi sanani ishlat."
    )
    schema = _build_transactions_schema(expense_categories, income_categories)
    result = await _generate_json([{"text": prompt}], schema)
    return result["transactions"]


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
    schema = _build_bank_rows_schema(expense_categories, income_categories)
    parsed = await _generate_json([{"text": prompt}], schema)
    return {item["row_index"]: item for item in parsed["results"]}


async def parse_daftar_edit(
    rows_text: str,
    instruction: str,
    expense_categories: list[str],
    income_categories: list[str],
) -> list[dict]:
    """Given the numbered list of a user's current unconfirmed Daftar rows and
    a free-text correction instruction (e.g. "2-qatordagi benzin summasini
    350000 qiling", or several corrections in one message, one per line),
    figures out which row(s) are meant and returns each one's full corrected
    fields - unmentioned fields are kept the same as the current value shown
    in rows_text. Always returns a list, even for a single-row correction -
    a message correcting multiple rows at once used to silently apply only
    one of them while still reporting blanket success."""
    prompt = (
        f"Chiqim kategoriyalari: {', '.join(expense_categories)}\n"
        f"Kirim kategoriyalari: {', '.join(income_categories)}\n\n"
        f"Foydalanuvchining hozirgi tasdiqlanmagan yozuvlari (Daftar) ro'yxati:\n{rows_text}\n\n"
        f"Foydalanuvchi shu ro'yxatdagi bir yoki bir nechta qatorni to'g'irlashni so'rab yozdi "
        f"(har bir tuzatish alohida qatorda/jumlada bo'lishi mumkin):\n\"{instruction}\"\n\n"
        "Ko'rsatmada nechta ALOHIDA qator tuzatilishi so'ralgan bo'lsa, natijada shuncha element "
        "qaytar - HAR BIRINI qo'ymasdan, faqat bittasini emas. Har bir element uchun: qaysi qator "
        "(row_index, ro'yxatdagi raqami) nazarda tutilganini aniqla va o'sha qatorning TO'LIQ, "
        "tuzatilgandan keyingi holatini qaytar - foydalanuvchi nima haqida yozgan bo'lsa shuni "
        "o'zgartir, boshqa barcha maydonlarni ro'yxatda ko'rsatilgan joriy qiymati bilan bir xil "
        "qoldir. Agar biror tuzatish uchun qaysi qator yoki nima o'zgarishi noaniq bo'lsa, o'sha "
        "elementga confidence='low' qo'y (lekin ro'yxatdan chiqarib tashlama)."
    )
    schema = _build_edits_schema(expense_categories, income_categories)
    result = await _generate_json([{"text": prompt}], schema)
    return result["edits"]
