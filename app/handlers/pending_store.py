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


# Maps a user's own text message (chat_id, message_id) to the unconfirmed
# transaction ids it produced and the bot's ack message id. When the user
# edits that original message in Telegram, we look it up here to know what
# to replace and which bot message to update in place.
_editable_messages: dict[tuple[int, int], dict] = {}


def remember_editable(chat_id: int, message_id: int, tx_ids: list[int], bot_message_id: int) -> None:
    _editable_messages[(chat_id, message_id)] = {"tx_ids": tx_ids, "bot_message_id": bot_message_id}


def get_editable(chat_id: int, message_id: int) -> dict | None:
    return _editable_messages.get((chat_id, message_id))
