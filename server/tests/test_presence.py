from xml.etree.ElementTree import fromstring

from fastapi.testclient import TestClient
from test_multiplayer import account, auth, join
from test_social import until
from test_world import extension, receive, send

from src.profiles.models import FriendRequest, Friendship
from src.shops.models import Shop
from src.world.catalog import BY_KEY, START_ROOM


def snapshot(client, token):
    response = client.get("/api/world/servers", headers=auth(token))
    assert response.status_code == 200
    return response.json()["servers"][0]


def test_live_presence_counts_joined_players_and_not_saved_sessions(app):
    with TestClient(app) as client:
        aid, atoken = account(client, "Presence_1", 3)
        bid, btoken = account(client, "Presence_2", 7)
        cid, ctoken = account(client, "Presence_3", 5)

        async def seed():
            async with app.state.sessions() as db:
                db.add(Shop(key="presence", title="Presence", kind="clothing"))
                db.add(Friendship(first_id=aid, second_id=bid))
                db.add(FriendRequest(sender_id=cid, recipient_id=aid))
                await db.commit()

        client.portal.call(seed)
        assert snapshot(client, atoken)["online"] == 0
        with client.websocket_connect("/legacy/socket", headers=auth(atoken)) as a:
            join(a, "Presence_1")
            assert snapshot(client, btoken)["online"] == 1
            assert snapshot(client, btoken)["friends"] == 1
            with client.websocket_connect("/legacy/socket", headers=auth(btoken)) as b:
                # A transport connection waiting for login/join is not online.
                assert snapshot(client, atoken)["online"] == 1
                assert snapshot(client, atoken)["friends"] == 0
                join(b, "Presence_2")
                data, _ = until(a, "buddyList__getUserBuddies")
                row = next(row for row in data["buddies"] if row["buddyId"] == bid)
                assert row["serverName"] == START_ROOM["title"]
                state = snapshot(client, atoken)
                assert state["online"] == 2 and state["friends"] == 1 and state["percentage"] == 2
                legacy = fromstring(
                    client.get("/legacy/servers", headers=auth(atoken)).content
                ).find("Servers/S")
                assert legacy.get("currentUsers") == "2" and legacy.get("friends") == "1"
                assert legacy.get("percentage") == "2"
                # Existing friend-list windows receive room changes without
                # HTTP polling. Being in another room/shop still counts online.
                send(
                    b,
                    '<msg t="sys"><body action="pubMsg">'
                    '<txt>speak__/room infoboard</txt></body></msg>',
                )
                while 'action="joinOK"' not in receive(b):
                    pass
                data, _ = until(a, "buddyList__getUserBuddies")
                row = next(row for row in data["buddies"] if row["buddyId"] == bid)
                assert row["serverName"] == BY_KEY["infoboard"]["title"]
                send(
                    b,
                    '<msg t="sys"><body action="pubMsg">'
                    '<txt>speak__/shop presence</txt></body></msg>',
                )
                # A following round-trip fences the shop command.
                extension(b, "user__getMyMoney")
                until(b, "user__getMyMoney")
                assert client.get("/api/shops/presence", headers=auth(btoken)).status_code == 200
                assert snapshot(client, atoken)["online"] == 2
                assert snapshot(client, atoken)["friends"] == 1
            data, _ = until(a, "buddyList__getUserBuddies")
            assert (
                next(row for row in data["buddies"] if row["buddyId"] == bid)["serverName"] is None
            )
            assert snapshot(client, atoken)["online"] == 1
            assert snapshot(client, atoken)["friends"] == 0
            with client.websocket_connect("/legacy/socket", headers=auth(ctoken)) as c:
                join(c, "Presence_3")
                # Pending requests and unrelated players never light the friend icon.
                state = snapshot(client, atoken)
                assert state["online"] == 2 and state["friends"] == 0
                receive(a)  # room uER, no accepted friendship notification for c
        assert snapshot(client, btoken)["online"] == 0
        assert snapshot(client, btoken)["friends"] == 0


def test_server_presence_requires_authorization(app):
    with TestClient(app) as client:
        assert client.get("/api/world/servers").status_code == 401
        assert client.get("/legacy/servers").status_code == 401


def test_online_command_is_private_and_counts_only_joined_players(app):
    with TestClient(app) as client:
        aid, atoken = account(client, "Command_1", 3)
        bid, btoken = account(client, "Command_2", 7)
        account(client, "OnlySession_3", 5)
        with client.websocket_connect("/legacy/socket", headers=auth(atoken)) as a:
            join(a, "Command_1")
            with client.websocket_connect("/legacy/socket", headers=auth(btoken)) as b:
                join(b, "Command_2")
                receive(a)
                send(
                    b, '<msg t="sys"><body action="pubMsg"><txt>speak__ /OnLiNe </txt></body></msg>'
                )
                body = fromstring(receive(b)).find("body")
                assert body.findtext("txt") == "speak__Сейчас в игре: 2"
                assert body.find("user").get("id") == str(bid)
                extension(a, "user__getMyMoney")
                _, packets = until(a, "user__getMyMoney")
                assert not any(
                    "Сейчас в игре" in packet or "/OnLiNe" in packet for packet in packets
                )
            receive(a)  # userGone
            send(a, '<msg t="sys"><body action="pubMsg"><txt>speak__/online</txt></body></msg>')
            assert fromstring(receive(a)).find("body/txt").text == "speak__Сейчас в игре: 1"
