from datetime import date, datetime
from io import BytesIO

import pandas as pd

from app.models import TransactionType

_DATE_COLS = ["sana", "date", "sanasi", "operatsiya sanasi"]
_AMOUNT_COLS = ["summa", "summasi", "amount", "miqdor", "sum"]
_DEBIT_COLS = ["chiqim", "debit", "xarajat", "debet"]
_CREDIT_COLS = ["kirim", "credit", "kredit", "daromad"]
_DESC_COLS = ["tavsif", "description", "izoh", "maqsad", "назначение", "детали", "detail"]


class BankImportError(Exception):
    pass


def _find_column(columns: list[str], candidates: list[str]) -> str | None:
    lowered = {c: c.strip().lower() for c in columns}
    for col, low in lowered.items():
        for cand in candidates:
            if cand in low:
                return col
    return None


def parse_bank_statement(file_bytes: bytes, filename: str) -> list[dict]:
    """Returns list of {occurred_on: date, amount: float, type: TransactionType, raw_description: str}"""
    buffer = BytesIO(file_bytes)
    if filename.lower().endswith(".csv"):
        df = pd.read_csv(buffer)
    else:
        df = pd.read_excel(buffer)

    df = df.dropna(how="all")
    columns = list(df.columns)

    date_col = _find_column(columns, _DATE_COLS)
    desc_col = _find_column(columns, _DESC_COLS)
    debit_col = _find_column(columns, _DEBIT_COLS)
    credit_col = _find_column(columns, _CREDIT_COLS)
    amount_col = _find_column(columns, _AMOUNT_COLS) if not (debit_col and credit_col) else None

    if not date_col:
        raise BankImportError(
            "Fayldan sana ustunini aniqlab bo'lmadi. Ustun nomlari orasida 'Sana'/'Date' bo'lishi kerak."
        )
    if not (debit_col and credit_col) and not amount_col:
        raise BankImportError(
            "Fayldan summa ustunlarini aniqlab bo'lmadi. 'Kirim'/'Chiqim' yoki 'Summa' ustuni kerak."
        )

    rows: list[dict] = []
    for _, row in df.iterrows():
        raw_date = row.get(date_col)
        occurred_on = _to_date(raw_date)
        if occurred_on is None:
            continue

        description = str(row.get(desc_col, "")).strip() if desc_col else ""

        if debit_col and credit_col:
            debit_val = _to_float(row.get(debit_col))
            credit_val = _to_float(row.get(credit_col))
            if debit_val:
                amount, type_ = debit_val, TransactionType.expense
            elif credit_val:
                amount, type_ = credit_val, TransactionType.income
            else:
                continue
        else:
            value = _to_float(row.get(amount_col))
            if value is None or value == 0:
                continue
            amount = abs(value)
            type_ = TransactionType.expense if value < 0 else TransactionType.income

        rows.append(
            {
                "occurred_on": occurred_on,
                "amount": amount,
                "type": type_,
                "raw_description": description,
            }
        )

    if not rows:
        raise BankImportError("Faylda tranzaksiya qatorlari topilmadi.")

    return rows


def _to_date(value) -> date | None:
    if pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y %H:%M:%S"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def _to_float(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(" ", "").replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
