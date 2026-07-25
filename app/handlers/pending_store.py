"""In-memory store for bank-import batches awaiting user confirmation.

A single bot process is assumed (no horizontal scaling), so a module-level
dict is sufficient and avoids needing a separate cache service. Manual/voice/
receipt entries no longer go through this store - they're persisted directly
as unconfirmed Transaction rows and reviewed later via /daftar.
"""

import uuid
from dataclasses import dataclass, field


@dataclass
class PendingBankImport:
    user_db_id: int
    telegram_id: int
    project_id: int | None = None
    project_name: str | None = None
    full_name: str = ""
    rows: list[dict] = field(default_factory=list)


_pending_bank: dict[str, PendingBankImport] = {}


def add_pending_bank(data: PendingBankImport) -> str:
    key = uuid.uuid4().hex[:12]
    _pending_bank[key] = data
    return key


def get_pending_bank(key: str) -> PendingBankImport | None:
    return _pending_bank.get(key)


def pop_pending_bank(key: str) -> PendingBankImport | None:
    return _pending_bank.pop(key, None)


# Tracks the unconfirmed transaction ids behind the most recent "qabul
# qilindi" acknowledgement per user, so tapping "Tahrirlash" knows what to
# replace, and a flag for whether we're currently waiting on their
# correction text (checked by the plain-text catch-all handler first).
_last_ack_tx_ids: dict[int, list[int]] = {}
_awaiting_correction: set[int] = set()


def remember_ack(telegram_id: int, tx_ids: list[int]) -> None:
    _last_ack_tx_ids[telegram_id] = tx_ids


def get_ack_tx_ids(telegram_id: int) -> list[int] | None:
    return _last_ack_tx_ids.get(telegram_id)


def start_correction(telegram_id: int) -> None:
    _awaiting_correction.add(telegram_id)


def is_awaiting_correction(telegram_id: int) -> bool:
    return telegram_id in _awaiting_correction


def stop_correction(telegram_id: int) -> None:
    _awaiting_correction.discard(telegram_id)
