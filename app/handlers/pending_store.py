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
