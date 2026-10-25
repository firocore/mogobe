from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock
from xml.etree.ElementTree import fromstring

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from test_multiplayer import account, join
from test_world import receive

from src.world.chat import send_message


@pytest.mark.asyncio
async def test_chat_adapter_requires_active_same_session():
    peer = SimpleNamespace(
        room=3, user={}, session_digest=sha256(b"token").hexdigest(), handle=AsyncMock()
    )
    hub = SimpleNamespace(connections={7: peer})
    for ident, token in [(8, "token"), (7, "other"), (7, None)]:
        with pytest.raises(HTTPException) as error:
            await send_message(hub, ident, token, "Я")
        assert error.value.status_code == 409
    peer.handle.assert_not_awaited()
    await send_message(hub, 7, "token", "<&")
    xml = fromstring(peer.handle.call_args.args[0])
    assert xml.findtext("body/txt") == "speak__<&"


def test_chat_http_uses_existing_rate_limit_and_socket_broadcast(app):
    with TestClient(app) as client:
        ident, token = account(client, "ChatTest", 7)
        assert client.post("/api/world/chat", json={"text": "Я"}).status_code == 409
        with client.websocket_connect("/legacy/socket") as ws:
            join(ws, "ChatTest")
            for text in ["Я", "?", "<b> & текст"]:
                app.state.world.connections[ident].last_chat = 0
                assert client.post("/api/world/chat", json={"text": text}).status_code == 204
                reply = fromstring(receive(ws)).find("body")
                assert reply.get("action") == "pubMsg"
                assert reply.findtext("txt") == "speak__" + text
            stamp = app.state.world.connections[ident].last_chat
            response = client.post("/api/world/chat", json={"text": "слишком быстро"})
            assert response.status_code == 204
            assert app.state.world.connections[ident].last_chat == stamp
            assert app.state.world.connections[ident].outbox.empty()
            for text in ["", "x" * 241]:
                assert client.post("/api/world/chat", json={"text": text}).status_code == 422
            client.cookies.clear()
            assert client.post("/api/world/chat", json={"text": "Я"}).status_code == 401
