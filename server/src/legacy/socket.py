"""Small, local SmartFox 1.x adapter for the original Main.swf.

Ruffle tunnels the movie's null-terminated TCP stream through this WebSocket.
The protocol contracts come from the saved AS3 sources; no SWF is patched.
Room IDs are local identifiers; graphic exits use an explicit imported catalogue.
"""

import asyncio
import codecs
import json
import math
import xml.etree.ElementTree as ET
from hashlib import sha256
from time import monotonic
from urllib.parse import urlsplit
from xml.sax.saxutils import escape

from anyio import CancelScope
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from src.admin.commands import alert, give
from src.auth.dependencies import get_token
from src.auth.models import Account
from src.auth.service import find_account
from src.legacy.messages import validated_message
from src.minigames import catalog as minigames
from src.minigames import service as minigame_service
from src.profiles import progression, social
from src.profiles import service as profiles
from src.shops import service as shops
from src.shops import world_shops
from src.shops.models import Shop
from src.world import catalog, service
from src.world.hub import BUSY_MESSAGE
from src.world.presence import online_ids

router = APIRouter()

ROOMS = {room["id"]: (room["key"], room["swf"], room["title"]) for room in catalog.DATA["rooms"]}


def variables(values):
    result = []
    for name, value in values.items():
        kind = "b" if isinstance(value, bool) else "n" if isinstance(value, (int, float)) else "s"
        encoded = ("1" if value else "0") if kind == "b" else str(value)
        result.append(f'<var n="{escape(name)}" t="{kind}">{escape(encoded)}</var>')
    return "<vars>" + "".join(result) + "</vars>"


def system(action, body="", room=0):
    return f'<msg t="sys"><body action="{action}" r="{room}">{body}</body></msg>'


class LegacyConnection:
    def __init__(self, socket, account, token):
        self.socket, self.account = socket, account
        self.session_digest = sha256(token.encode()).hexdigest()
        self.user = None
        self.room = None
        self.state = {}
        self.player = None
        self.hub = socket.app.state.world
        self.outbox = asyncio.Queue(maxsize=256)
        self.writer = None
        self.quoted_shop = None
        self.quoted_prices = {}
        self.last_chat = 0.0
        self.muted_ids = set()

    def enqueue(self, message):
        try:
            self.outbox.put_nowait(message)
        except asyncio.QueueFull:
            # Cancelling only this writer makes the endpoint release its slot.
            if self.writer is not None:
                self.writer.cancel()

    async def write_packets(self):
        while True:
            message = await self.outbox.get()
            await asyncio.wait_for(
                self.socket.send_bytes(message.encode("utf-8") + b"\0"), timeout=5
            )

    async def send(self, message):
        self.enqueue(message)

    def user_xml(self):
        return (
            f'<u i="{self.account.id}" m="0" s="0" p="0">'
            f"<n>{escape(self.account.username)}</n>{variables(self.state)}</u>"
        )

    async def extension(self, command, **values):
        await self.send(
            json.dumps(
                {"t": "xt", "b": {"r": self.room or -1, "o": {"_cmd": command, **values}}},
                ensure_ascii=False,
            )
        )

    async def room_list(self):
        entries = "".join(
            f'<rm id="{ident}" maxu="100" maxs="0" temp="0" game="0" priv="0" '
            f'lmb="0" ucnt="{len(self.hub.members(ident))}" scnt="0"><n>{data[1]}</n><vars/></rm>'
            for ident, data in ROOMS.items()
        )
        await self.send(system("rmList", "<rmList>" + entries + "</rmList>"))

    async def join(self, ident, *, arrival_from=None):
        if ident not in ROOMS:
            return
        await minigame_service.cancel_connection(self.socket.app, self)
        previous = self.room
        if previous is not None and previous != ident:
            self.hub.broadcast(
                previous,
                system("userGone", f'<user id="{self.account.id}"/>', previous),
                exclude=self,
            )
        self.room = ident
        key, name, title = ROOMS[ident]
        occupied = [
            (p.player.x, p.player.y)
            for p in self.hub.members(ident)
            if p is not self and p.player is not None
        ]
        self.player = service.enter(key, arrival_from=arrival_from, occupied=occupied)
        self.socket.app.state.world_players[self.account.id] = self.player
        x, y = self.player.x, self.player.y
        self.state.update(x=x, y=y, AD=4)
        room_vars = {"roomId": ident, "roomName": title, "baseSwf": name, "items": "[]"}
        if track := catalog.ROOM_AUDIO.get(key):
            room_vars["rbs"] = track  # Original RoomTO.SFSVar_bgSound, served by the local client.
        others = [p for p in self.hub.members(ident) if p is not self]
        users = self.user_xml() + "".join(p.user_xml() for p in others)
        self.user.update(room=key, x=x, y=y)
        await self.send(
            system(
                "joinOK", '<pid id="0"/>' + variables(room_vars) + "<uLs>" + users + "</uLs>", ident
            )
        )

        if previous == ident:
            self.hub.broadcast(
                ident,
                system(
                    "uVarsUpdate", f'<user id="{self.account.id}"/>' + variables(self.state), ident
                ),
                exclude=self,
            )
        else:
            self.hub.broadcast(ident, system("uER", self.user_xml(), ident), exclude=self)
        if previous != ident:
            await self.notify_presence_observers()

    async def notify_presence_observers(self):
        async with self.socket.app.state.sessions() as db:
            owners = await social.presence_observers(db, self.account.id)
            for owner in owners:
                peer = self.hub.connections.get(owner)
                if peer is not None and peer.room is not None and peer.user is not None:
                    buddies = await social.buddy_list(db, owner, self.hub)
                    await peer.extension("buddyList__getUserBuddies", buddies=buddies)

    async def handle(self, message):
        if message.startswith("<policy-file-request"):
            await self.send(
                '<cross-domain-policy><allow-access-from domain="*" '
                'to-ports="9339"/></cross-domain-policy>'
            )
            return
        if message.startswith("{"):
            packet = json.loads(message)
            if self.user is None or packet.get("t") != "xt":
                return
            body = packet.get("b", {})
            if not isinstance(body, dict) or not isinstance(body.get("p", {}), dict):
                raise ValueError("Invalid extension envelope")
            command = body.get("c", "")
            if not isinstance(command, str) or len(command) > 100:
                raise ValueError("Invalid command")
            await self.command(command, body.get("p", {}))
            return
        root = ET.fromstring(message)
        body = root.find("body")
        if body is None:
            return
        action = body.get("action")
        if action == "verChk":
            await self.send(system("apiOK"))
        elif action == "login":
            if self.user is not None:
                raise ValueError("Already authenticated")
            username = body.findtext("login/nick", "")
            marker = body.findtext("login/pword", "")
            if (
                username.casefold() != self.account.username_key
                or marker != "__MOGOBE_CURRENT_SESSION__"
            ):
                raise ValueError("Mismatched login")
            resumed = self.hub.consume_reconnect(self.account.id, self.session_digest)
            start = catalog.BY_ID.get(resumed, catalog.START_ROOM)
            x, y = start["spawn"]
            self.user = {
                "id": self.account.id,
                "username": self.account.username,
                "legacy_color": self.account.color_id,
                "room": start["key"],
                "x": x,
                "y": y,
            }
            self.state = {
                "color": self.account.color_id,
                "items": "[]",
                "x": x,
                "y": y,
                "AD": 4,
                "mo_1": 0,
                "isMember": False,
                "appUserId": self.account.id,
                "userType": 1,
            }
            async with self.socket.app.state.sessions() as db:
                fields = await profiles.public_profile(db, self.account)
                self.muted_ids = await social.muted_ids(db, self.account.id)
                self.state["items"] = json.dumps(fields["items"], ensure_ascii=False)
            self.state.update(
                {
                    key: fields[key]
                    for key in ("age", "friends", "score", "level", "isMember", "isAdmin", "mo_1")
                }
            )
            # The extension-based login must populate roomList before SWF sends
            # any extension requests (SmartFoxClient.checkRoomList).
            await self.room_list()
            await self.extension(
                "login",
                uSFSId=self.user["id"],
                appUserId=self.user["id"],
                userName=self.user["username"],
                ageGroup=1,
                chatMode=True,
                worldAdvan=False,
                lastLogin=None,
                prevLogin=0,
                userType=1,
                lang=5,
                ld=[{"i": 0, "t": 1}],
            )
        elif self.user is not None:
            if action == "getRmList":
                await self.room_list()
            elif action == "setUvars" and self.room:
                if body.get("r") not in (None, str(self.room)):
                    return
                update = {}
                for node in body.findall("vars/var"):
                    name, value = node.get("n"), node.text or ""
                    if name in {"x", "y"}:
                        number = float(value)
                        if not math.isfinite(number) or not 0 <= number < (
                            768 if name == "x" else 480
                        ):
                            raise ValueError("Invalid position")
                        update[name] = number
                    elif name == "AD" and len(value) < 64:
                        if node.get("t") == "n":
                            number = float(value)
                            if not math.isfinite(number) or not 0 <= number <= 18:
                                raise ValueError("Invalid direction")
                            update[name] = number
                        elif value.isdecimal() and 0 <= int(value) <= 18:
                            update[name] = int(value)
                        # Custom dance sequences require clothing assets and
                        # are not relayed as arbitrary class names to peers.
                if ("x" in update) != ("y" in update):
                    raise ValueError("Incomplete position")
                if {"x", "y"} <= update.keys():
                    point = (update["x"], update["y"])
                    update["x"], update["y"] = service.move(self.player, point)
                if update:
                    self.state.update(update)
                    self.hub.broadcast(
                        self.room,
                        system(
                            "uVarsUpdate",
                            f'<user id="{self.user["id"]}"/>' + variables(update),
                            self.room,
                        ),
                    )
            elif action == "pubMsg" and self.room:
                content = validated_message(
                    body.findtext("txt", ""),
                    self.account.id,
                    {peer.account.id for peer in self.hub.members(self.room)},
                )
                if content is None or monotonic() - self.last_chat < 0.5:
                    return
                self.last_chat = monotonic()
                action, _, text = content.partition("__")
                if action in {"speak", "speakRoom", "speakServer"} and (
                    text.casefold() == "/room" or text.casefold().startswith("/room ")
                ):
                    destination = catalog.resolve(text.partition(" ")[2])
                    if destination:
                        await self.join(destination["id"])
                    else:
                        await self.send(
                            system(
                                "pubMsg",
                                f'<user id="{self.account.id}"/>'
                                "<txt>speak__Локация не найдена.</txt>",
                                self.room,
                            )
                        )
                    return
                if action in {"speak", "speakRoom", "speakServer"} and (
                    text.casefold() == "/game" or text.casefold().startswith("/game ")
                ):
                    key = text.partition(" ")[2].strip().casefold()
                    if key in minigames.GAMES:
                        await self.extension("minigame__open", key=key)
                    else:
                        await self.send(system(
                            "pubMsg", f'<user id="{self.account.id}"/>'
                            "<txt>speak__Команда: /game goldfishing</txt>", self.room,
                        ))
                    return
                if action in {"speak", "speakRoom", "speakServer"} and (
                    text.casefold() == "/shop" or text.casefold().startswith("/shop ")
                ):
                    key = text.partition(" ")[2].strip().casefold()
                    try:
                        async with self.socket.app.state.sessions() as db:
                            current = await db.get(Account, self.account.id)
                            await shops.get_shop(db, key, current)
                        await self.extension("shop__open", key=key)
                    except HTTPException:
                        await self.send(
                            system(
                                "pubMsg",
                                f'<user id="{self.account.id}"/>'
                                "<txt>speak__Магазин недоступен. Команда: /shop ключ</txt>",
                                self.room,
                            )
                        )
                    return
                if action in {"speak", "speakRoom", "speakServer"} and (
                    text.casefold() == "/give" or text.casefold().startswith("/give ")
                ):
                    try:
                        message = await give(self.socket.app, self.account.id, text)
                    except HTTPException as exc:
                        message = str(exc.detail)
                    await self.send(
                        system(
                            "pubMsg",
                            f'<user id="{self.account.id}"/><txt>speak__{escape(message)}</txt>',
                            self.room,
                        )
                    )
                    return
                if action in {"speak", "speakRoom", "speakServer"} and (
                    text.casefold() == "/alert" or text.casefold().startswith("/alert ")
                ):
                    try:
                        message = await alert(self.socket.app, self.account.id, text)
                    except HTTPException as exc:
                        message = str(exc.detail)
                    await self.send(
                        system(
                            "pubMsg",
                            f'<user id="{self.account.id}"/><txt>speak__{escape(message)}</txt>',
                            self.room,
                        )
                    )
                    return
                if action in {"speak", "speakRoom", "speakServer"} and text.casefold() == "/online":
                    count = len(online_ids(self.hub))
                    await self.send(
                        system(
                            "pubMsg",
                            f'<user id="{self.account.id}"/>'
                            f"<txt>speak__Сейчас в игре: {count}</txt>",
                            self.room,
                        )
                    )
                    return
                packet = system(
                    "pubMsg",
                    f'<user id="{self.account.id}"/><txt>{escape(content)}</txt>',
                    self.room,
                )
                for peer in self.hub.members(self.room):
                    if self.account.id not in peer.muted_ids:
                        peer.enqueue(packet)
            elif action == "loadB":
                await self.send(system("bList", "<mv/><bList/>"))

    async def command(self, command, params):
        if command == "rooms__getStaticRoomList":
            await self.extension(
                command, StaticRooms=[{"rId": k, "rN": v[1], "rT": "WR"} for k, v in ROOMS.items()]
            )
        elif command == "user__joinFirstRoom":
            ident = next(
                (k for k, v in ROOMS.items() if v[0] == self.user["room"]), catalog.START_ROOM["id"]
            )
            await self.join(ident)
        elif command == "rooms__jumpToRoom":
            destination = catalog.resolve(
                params.get("nameId", params.get("roomId", params.get("rId", params.get("id"))))
            )
            if destination:
                await self.join(destination["id"])
            else:
                await self.extension(command, errorId=69, isAllowPlayGame=-1)
        elif command == "rooms__changeRoom":
            token = params.get("grfCompunentId", params.get("gCId"))
            game = (
                minigames.at_entry(catalog.BY_ID[self.room], token, self.player.x, self.player.y)
                if self.room else None
            )
            if game:
                # The original avatar disabled walking while awaiting its room
                # reply. A game-entry acknowledgement releases that wait without
                # constructing an ordinary room-error popup or joining a room.
                await self.extension(command, isMultiGame=True, errorId=-1, isAllowPlayGame=-1)
                await self.extension("minigame__open", key=game)
                return
            destination = (
                catalog.exit_destination(
                    catalog.BY_ID[self.room], token, self.player.x, self.player.y
                )
                if self.room
                else None
            )
            if destination:
                await self.join(destination["id"], arrival_from=catalog.BY_ID[self.room])
            else:
                await self.extension(command, errorId=69, isAllowPlayGame=-1)
        elif command == "rooms__changeRoomArea":
            area = params.get("gCId", params.get("grfCompunentId"))
            available = catalog.BY_ID[self.room]["areas"] if self.room else []
            allowed = type(area) in (int, str) and (str(area) == "0" or str(area) in available)
            await self.extension(
                command, errorId=-1 if allowed else 29, gCId=int(area) if allowed else 0
            )
        elif command in {"user__getUserCard", "user__getUserDetail", "user__getUserCardInfo"}:
            async with self.socket.app.state.sessions() as db:
                try:
                    account = await profiles.find_profile(db, params)
                except HTTPException:
                    await self.extension(command, errorId=11)
                    return
                fields = await profiles.public_profile(db, account)
                allow_add = await social.can_invite(db, self.account.id, account.id)
                is_muted = account.id in await social.muted_ids(db, self.account.id)
            target = self.hub.connections.get(account.id)
            online = target is not None and target.room is not None
            if online:
                update = {
                    key: fields[key]
                    for key in ("age", "friends", "score")
                    if target.state.get(key) != fields[key]
                }
                if update:
                    target.state.update(update)
                    self.hub.broadcast(
                        target.room,
                        system(
                            "uVarsUpdate",
                            f'<user id="{account.id}"/>' + variables(update),
                            target.room,
                        ),
                    )
            if command == "user__getUserCardInfo":
                await self.extension(
                    command,
                    userId=account.id,
                    userName=account.username,
                    age=fields["age"],
                    friends=fields["friends"],
                    groups=[],
                    member=account.is_admin,
                    isRoomOpen=False,
                    newMsgs=0,
                    isAvliablChat=False,
                    isAvliablTrade=False,
                    isAvliablPresent=False,
                    isAllowToAdd=allow_add,
                    isBlock=is_muted,
                )
            else:
                await self.extension(command, **fields, online=online, isOneline=online)
        elif command == "buddyList__getUserBuddies":
            async with self.socket.app.state.sessions() as db:
                buddies = await social.buddy_list(db, self.account.id, self.hub)
            await self.extension(command, buddies=buddies)
        elif command.startswith("buddyList__"):
            async with self.hub.social_lock:
                async with self.socket.app.state.sessions() as db:
                    try:
                        buddy = await social.operate(
                            db, self.account.id, command.removeprefix("buddyList__"), params
                        )
                    except HTTPException:
                        await self.extension(command, errorId=11, msgId=11)
                        return
                    self.muted_ids = await social.muted_ids(db, self.account.id)
                    counts = {
                        ident: await social.pending_count(db, ident)
                        for ident in (self.account.id, buddy)
                    }
                    for ident in (self.account.id, buddy):
                        peer = self.hub.connections.get(ident)
                        if peer is not None and peer.room is not None:
                            account = await db.get(type(self.account), ident)
                            fields = await profiles.public_profile(db, account)
                            update = {key: fields[key] for key in ("friends", "age")}
                            peer.state.update(update)
                            self.hub.broadcast(
                                peer.room,
                                system(
                                    "uVarsUpdate",
                                    f'<user id="{ident}"/>' + variables(update),
                                    peer.room,
                                ),
                            )
            # Refresh an open native friends list in either window. The legacy
            # UserCard ignores buddy events; its mute indicator uses /social/me.
            for ident in (buddy,):
                peer = self.hub.connections.get(ident)
                if peer is not None and peer.user is not None:
                    async with self.socket.app.state.sessions() as db:
                        buddies = await social.buddy_list(db, ident, self.hub)
                    await peer.extension("buddyList__getUserBuddies", buddies=buddies)
                    if counts[ident]:
                        await peer.extension(
                            "buddyList__addBuddyRequest", msgId=-1, numRequests=counts[ident]
                        )
            if command == "buddyList__blockBuddy":
                # Original UserCard.onBuddyListData is empty. Reuse the card
                # response it already handles to refresh Add Friend availability.
                async with self.socket.app.state.sessions() as db:
                    account = await db.get(type(self.account), buddy)
                    allow = await social.can_invite(db, self.account.id, buddy)
                await self.extension(
                    "user__getUserCardInfo",
                    userId=buddy,
                    userName=account.username,
                    groups=[],
                    member=account.is_admin,
                    isRoomOpen=False,
                    newMsgs=0,
                    isAvliablChat=False,
                    isAvliablTrade=False,
                    isAvliablPresent=False,
                    isAllowToAdd=allow,
                    isBlock=buddy in self.muted_ids,
                )
            await self.extension(command, msgId=-1, numRequests=counts[self.account.id])
        elif command == "rooms__getStoreData":
            data = {"items": [], "categories": []}
            self.quoted_shop, self.quoted_prices = None, {}
            async with self.socket.app.state.sessions() as db:
                current = await db.get(Account, self.account.id)
                room_key = catalog.BY_ID[self.room]["key"] if self.room else None
                shop = (
                    await db.scalar(select(Shop).where(Shop.room_key == room_key))
                    if room_key
                    else None
                )
                assigned = (
                    await world_shops.nearby(
                        db, current, room_key, self.state.get("x"), self.state.get("y")
                    )
                    if room_key
                    else None
                )
                if assigned:
                    _, shop = assigned
                if shop:
                    try:
                        shop = await shops.get_shop(db, shop.key, current)
                        data = await shops.catalog(db, shop, current)
                        self.quoted_shop = shop.key
                        self.quoted_prices = {
                            item["typeId"]: item["price"] for item in data["items"]
                        }
                    except HTTPException:
                        pass
            await self.extension(command, items=data["items"], categories=data["categories"])
        elif command == "user__buyItem":
            ident = params.get("itemId")
            if type(ident) is not int or ident not in self.quoted_prices or not self.quoted_shop:
                await self.extension(command, status=False, msgId=2)
                return
            async with self.socket.app.state.commerce_lock:
                async with self.socket.app.state.sessions() as db:
                    try:
                        purchase = await shops.purchase(
                            db, self.account, self.quoted_shop, ident, self.quoted_prices[ident]
                        )
                    except HTTPException:
                        await self.extension(command, status=False, msgId=1)
                        return
                await shops.changed(self.socket.app)
                await progression.notify(
                    self.socket.app, self.account.id, purchase["experience_awarded"]
                )
            await self.extension(command, status=True)
        elif command == "user__getInventoryItems":
            # Inventory belongs to the authenticated mogobe, never a supplied ID.
            ident = params.get("userId", self.account.id)
            if type(ident) is not int or ident != self.account.id:
                await self.extension(command, items=[], errorId=11)
                return
            async with self.socket.app.state.sessions() as db:
                from src.inventory import service as wardrobe

                items = await wardrobe.available(
                    db, self.account.id, params.get("mainType"), params.get("placeCategorys")
                )
            await self.extension(command, items=items, userId=self.account.id)
        elif command in ("user__setInUseItem", "user__setNotInUseItem"):
            from src.inventory import service as wardrobe

            requested = params.get("items")
            ids = (
                [row.get("id") if isinstance(row, dict) else None for row in requested]
                if isinstance(requested, list)
                else None
            )
            async with self.socket.app.state.commerce_lock:
                async with self.socket.app.state.sessions() as db:
                    try:
                        items = await wardrobe.change(
                            db, self.account.id, ids, wear=command == "user__setInUseItem"
                        )
                    except HTTPException as error:
                        await self.send(
                            system(
                                "pubMsg",
                                f'<user id="{self.account.id}"/>'
                                + f"<txt>speak__{escape(str(error.detail))}</txt>",
                                self.room,
                            )
                        )
                        return
                await wardrobe.notify(self.socket.app, self.account.id, items)
                await self.extension(command, items=items, userId=self.account.id)
        elif command == "user__getGiftsItemList":
            await self.extension(command, items=[])
        elif command == "tipOfDay__getUserTips":
            await self.extension(command, userTips=[])
        elif command == "user__getMyMoney":
            async with self.socket.app.state.sessions() as db:
                coins = await shops.balance(db, self.account.id)
            await self.extension(command, userId=self.user["id"], money=coins, coins=coins)
        # Unsupported gameplay is not acknowledged as a successful purchase,
        # quest, trade or reward. Room traversal is handled above.


@router.websocket("/legacy/socket")
async def socket(ws: WebSocket):
    # Only the native gateway supplies this session. No credentials in URLs.
    origin = ws.headers.get("origin")
    if origin and urlsplit(origin).netloc != ws.headers.get("host"):
        await ws.close(code=1008)
        return
    token = get_token(ws)
    try:
        async with ws.app.state.sessions() as db:
            account = await find_account(db, token)
    except HTTPException:
        await ws.close(code=1008)
        return
    connection = LegacyConnection(ws, account, token)
    try:
        await ws.app.state.world.claim(connection)
    except HTTPException:
        # A WebSocket close code lets the native bridge show a precise error
        # even if two clients raced after successfully loading the server list.
        await ws.accept()
        await ws.close(code=4009, reason=BUSY_MESSAGE[:50])
        return
    reader = None
    try:
        await ws.accept()
        connection.writer = asyncio.create_task(connection.write_packets())
        reader = asyncio.create_task(read_packets(ws, connection, token))
        done, _ = await asyncio.wait(
            [reader, connection.writer], return_when=asyncio.FIRST_COMPLETED
        )
        for task in done:
            if not task.cancelled():
                task.result()
    except (
        WebSocketDisconnect,
        HTTPException,
        UnicodeError,
        ET.ParseError,
        ValueError,
        TypeError,
        AttributeError,
        TimeoutError,
        OSError,
        RuntimeError,
    ):
        pass
    except asyncio.CancelledError:
        pass
    finally:
        ws.app.state.world.release(connection)
        tasks = [task for task in (reader, connection.writer) if task is not None]
        for task in tasks:
            task.cancel()
        # ASGI may cancel this endpoint as the browser closes its socket.
        # Finish releasing the writer/reader before reporting closure.
        with CancelScope(shield=True):
            await asyncio.gather(*tasks, return_exceptions=True)
            await minigame_service.cancel_connection(ws.app, connection)
            if connection.room is not None:
                await connection.notify_presence_observers()
            try:
                await ws.close(code=1000)
            except (RuntimeError, OSError, WebSocketDisconnect):
                pass


async def read_packets(ws, connection, token):
    decoder = codecs.getincrementaldecoder("utf-8")()
    buffer = ""
    while True:
        try:
            frame = await asyncio.wait_for(ws.receive(), timeout=30 if connection.user else 10)
        except TimeoutError:
            if connection.user is None:
                return
            async with ws.app.state.sessions() as db:
                await find_account(db, token)
            continue
        if frame["type"] == "websocket.disconnect":
            return
        buffer += decoder.decode(frame.get("bytes") or (frame.get("text") or "").encode())
        if len(buffer) > 65536:
            await ws.close(code=1009)
            return
        while "\0" in buffer:
            message, buffer = buffer.split("\0", 1)
            if message.strip():
                async with ws.app.state.sessions() as db:
                    await find_account(db, token)
                await connection.handle(message.strip())
