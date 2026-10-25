from fastapi import APIRouter, Request, Response

from src.auth.dependencies import CurrentAccount, Database, get_token
from src.world import catalog, chat, commands
from src.world.presence import server_snapshot
from src.world.schemas import ChatMessage

router = APIRouter(prefix="/api/world", tags=["world"])


@router.get("/me")
async def me(account: CurrentAccount, request: Request):
    player = request.app.state.world_players.get(account.id)
    return {
        "entered": player is not None,
        "room": catalog.BY_ID[player.room_id]["key"] if player else None,
        "x": player.x if player else None,
        "y": player.y if player else None,
        "username": account.username,
        "color_id": account.color_id,
    }


@router.post("/reconnect", status_code=204)
async def reconnect(account: CurrentAccount, request: Request):
    request.app.state.world.prepare_reconnect(account.id, get_token(request))
    return Response(status_code=204)


@router.get("/servers")
async def servers(account: CurrentAccount, db: Database, request: Request):
    return {"servers": [await server_snapshot(db, account.id, request.app.state.world)]}


@router.get("/rooms")
async def rooms(account: CurrentAccount):
    return {
        "rooms": [
            {"id": room["id"], "name": room["swf"], "title": room["title"], "key": room["key"]}
            for room in catalog.DATA["rooms"]
        ]
    }


@router.get("/commands")
async def command_help(account: CurrentAccount):
    return commands.available(account.is_admin)


@router.post("/chat", status_code=204)
async def public_chat(message: ChatMessage, account: CurrentAccount, request: Request):
    await chat.send_message(request.app.state.world, account.id, get_token(request), message.text)
    return Response(status_code=204)
