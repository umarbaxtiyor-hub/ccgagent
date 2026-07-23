"""In-memory store for transactions awaiting user confirmation.

A single bot process is assumed (no horizontal scaling), so a module-level
dict is sufficient and avoids needing a separate cache service.
"""

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PendingTransaction:
    user_db_id: int
    telegram_id: int
    type: str
    amount: float
    category: str
    description: str
    counterparty: str
    occurred_on: str
    source: str


@dataclass
class PendingBankImport:
    user_db_id: int
    telegram_id: int
    rows: list[dict] = field(default_factory=list)


_pending_tx: dict[str, PendingTransaction] = {}
_pending_bank: dict[str, PendingBankImport] = {}


def add_pending_tx(data: PendingTransaction) -> str:
    key = uuid.uuid4().hex[:12]
    _pending_tx[key] = data
    return key


def get_pending_tx(key: str) -> PendingTransaction | None:
    return _pending_tx.get(key)


def pop_pending_tx(key: str) -> PendingTransaction | None:
    return _pending_tx.pop(key, None)


def add_pending_bank(data: PendingBankImport) -> str:
    key = uuid.uuid4().hex[:12]
    _pending_bank[key] = data
    return key


def get_pending_bank(key: str) -> PendingBankImport | None:
    return _pending_bank.get(key)


def pop_pending_bank(key: str) -> PendingBankImport | None:
    return _pending_bank.pop(key, None)
