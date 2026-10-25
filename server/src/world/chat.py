"""Send adapter input through the same active connection and chat validation."""
from hashlib import sha256
from xml.sax.saxutils import escape

from fastapi import HTTPException


async def send_message(hub, account_id: int, token: str | None, text: str) -> None:
    peer = hub.connections.get(account_id)
    digest = sha256((token or "").encode()).hexdigest()
    if peer is None or peer.room is None or peer.user is None or peer.session_digest != digest:
        raise HTTPException(409, "Нет активного подключения этой сессии")
    # The original ControlPanel rejects one-character input before reaching
    # SmartFox. Reuse the original socket handler's validation, rate limit,
    # command permissions and per-recipient mute filtering for adapter sends.
    await peer.handle(
        '<msg t="sys"><body action="pubMsg"><txt>speak__'
        + escape(text) + '</txt></body></msg>'
    )
