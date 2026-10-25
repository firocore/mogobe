import asyncio
import logging
from datetime import timedelta
from xml.etree.ElementTree import fromstring

import httpx
import pytest
from alembic.config import Config
from sqlalchemy import MetaData, Table, func, select, update

from alembic import command
from src.auth.models import Account, RegistrationDraft, Session
from src.auth.service import PASSWORDS, now, token_hash
from src.config import ROOT, Settings
from src.main import create_app

START = {"username": "Могобик12", "password": "Pass1234", "color_id": 12}
FINISH = {
    "age": 12,
    "chat_mode": "closed",
    "accepted_terms": True,
    "newsletter": True,
    "parent_email": "parent@example.com",
}


async def test_http_logs_show_status_without_credentials(client, caplog):
    with caplog.at_level(logging.INFO, logger="mogobe.http"):
        response = await client.post(
            "/api/auth/login?password=QuerySecret",
            json={"username": "Unknown", "password": "BodySecret"},
            headers={"Authorization": "Bearer TokenSecret", "Cookie": "test=CookieSecret"},
        )
    assert response.status_code == 401
    records = [record.getMessage() for record in caplog.records if record.name == "mogobe.http"]
    assert len(records) == 1
    assert "POST '/api/auth/login' -> 401" in records[0] and " ms)" in records[0]
    for secret in ["QuerySecret", "BodySecret", "TokenSecret", "CookieSecret"]:
        assert secret not in records[0]


async def register(client, start=None):
    assert (
        await client.post("/api/auth/registration-drafts", json=start or START)
    ).status_code == 201
    response = await client.post("/api/auth/register", json=FINISH)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("age", [1, 4, 15, 42, 100])
async def test_registration_accepts_numeric_age(client, age):
    assert (await client.post("/api/auth/registration-drafts", json=START)).status_code == 201
    response = await client.post("/api/auth/register", json={**FINISH, "age": age})
    assert response.status_code == 201, response.text
    assert (await client.get("/api/auth/me")).json()["age"] == age


@pytest.mark.parametrize("age", [0, 101, -1, 1.5, True, "12", None])
async def test_registration_rejects_invalid_numeric_age(client, age):
    assert (await client.post("/api/auth/registration-drafts", json=START)).status_code == 201
    response = await client.post("/api/auth/register", json={**FINISH, "age": age})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "username",
    [
        "a bcd",
        " Nick",
        "Nick ",
        "Nick\n",
        "Ni\tck",
        "Nick!",
        "Nick-1",
        "Nick.1",
        "Nick@1",
        "Nick[1",
        "Nick\\1",
        "Nick😀",
        "Нік_1",
        "abc",
        "a" * 16,
    ],
)
async def test_nickname_rejects_spaces_and_other_characters(client, app, username):
    response = await client.post(
        "/api/auth/registration-drafts", json={**START, "username": username}
    )
    assert response.status_code == 422
    assert (
        await client.post("/api/auth/login", json={"username": username, "password": "Pass1234"})
    ).status_code == 422
    async with app.state.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(RegistrationDraft)) == 0


@pytest.mark.parametrize("username", ["AZaz_09", "АЯая_09", "Ёжик_5", "MiXeD_12"])
async def test_nickname_preserves_spelling_and_allows_underscore(client, username):
    account = await register(client, {**START, "username": username})
    assert account["username"] == username
    assert (await client.get("/api/auth/me")).json()["username"] == username


@pytest.mark.parametrize(
    "preferences",
    [
        {},
        {"accepted_terms": False, "newsletter": False},
        {"accepted_terms": True, "newsletter": False},
        {"accepted_terms": False, "newsletter": True},
    ],
)
async def test_registration_checkboxes_are_independently_optional(client, app, preferences):
    await client.post("/api/auth/registration-drafts", json=START)
    response = await client.post(
        "/api/auth/register", json={"age": 12, "chat_mode": "open", **preferences}
    )
    assert response.status_code == 201
    async with app.state.sessions() as db:
        account = await db.scalar(select(Account))
        assert bool(account.terms_accepted_at) == preferences.get("accepted_terms", False)
        assert account.newsletter == preferences.get("newsletter", False)
    assert (await client.get("/legacy/servers")).status_code == 200


async def test_optional_terms_migration_preserves_existing_account_and_session(
    tmp_path, monkeypatch
):
    url = f"sqlite+aiosqlite:///{(tmp_path / 'old.sqlite3').as_posix()}"
    monkeypatch.setenv("MOGOBE_DATABASE_URL", url)
    cfg = Config(str(ROOT / "alembic.ini"))
    await asyncio.to_thread(command.upgrade, cfg, "ec87067cfd5e")
    # Seed using the historical schema. Current ORM/API models intentionally
    # require the new head (including later administrator columns).
    from src.database import make_engine

    engine = make_engine(url)
    token = "existing-session-before-migrations"
    try:
        async with engine.begin() as connection:

            def seed(sync):
                metadata = MetaData()
                old_accounts = Table("auth_account", metadata, autoload_with=sync)
                old_sessions = Table("auth_session", metadata, autoload_with=sync)
                ident = sync.execute(
                    old_accounts.insert().values(
                        username=START["username"],
                        username_key=START["username"].casefold(),
                        password_hash=PASSWORDS.hash(START["password"]),
                        color_id=12,
                        age=12,
                        chat_mode="closed",
                        newsletter=True,
                        parent_email=FINISH["parent_email"],
                        terms_accepted_at=now(),
                        created_at=now(),
                    )
                ).inserted_primary_key[0]
                sync.execute(
                    old_sessions.insert().values(
                        token_hash=token_hash(token),
                        account_id=ident,
                        expires_at=now() + timedelta(days=1),
                    )
                )
                return {
                    "id": ident,
                    "username": START["username"],
                    "color_id": 12,
                    "age": 12,
                    "chat_mode": "closed",
                }

            account = await connection.run_sync(seed)
    finally:
        await engine.dispose()
    await asyncio.to_thread(command.upgrade, cfg, "head")
    migrated = create_app(Settings(database_url=url))
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=migrated), base_url="http://test"
        ) as api:
            response = await api.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 200 and response.json() == account
        async with migrated.state.sessions() as db:
            assert await db.scalar(select(func.count()).select_from(Session)) == 1
            original = await db.scalar(select(Account))
            assert original.terms_accepted_at is not None
            assert original.is_admin is False
    finally:
        await migrated.state.engine.dispose()


async def test_full_registration_login_logout_and_persistence(client, app):
    response = await client.post("/api/auth/registration-drafts", json=START)
    assert response.status_code == 201
    assert "HttpOnly" in response.headers["set-cookie"]
    async with app.state.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Account)) == 0
        assert await db.scalar(select(func.count()).select_from(Session)) == 0
        draft = await db.scalar(select(RegistrationDraft))
        assert draft.password_hash.startswith("$argon2id$")
        assert START["password"] not in draft.password_hash
    response = await client.post("/api/auth/register", json=FINISH)
    assert response.status_code == 201
    assert response.json()["color_id"] == 12
    assert "password" not in response.text and "parent_email" not in response.text
    assert not client.cookies.get("mogobe_registration")
    registration_token = client.cookies.get("mogobe_session")
    assert registration_token
    assert "HttpOnly" in response.headers["set-cookie"]
    assert (await client.get("/api/auth/me")).json()["username"] == START["username"]
    response = await client.post("/legacy/resume", json={"username": START["username"]})
    assert fromstring(response.content).find("Login").get("status") == "1"
    assert (await client.get("/legacy/servers")).status_code == 200
    credentials = {"username": START["username"].lower(), "password": START["password"]}
    response = await client.post("/api/auth/login", json=credentials)
    assert response.status_code == 200
    cookie = client.cookies.get("mogobe_session")
    assert cookie
    assert "HttpOnly" in response.headers["set-cookie"]
    assert (
        await client.get("/api/auth/me", headers={"Authorization": f"Bearer {registration_token}"})
    ).status_code == 401
    assert (await client.get("/api/auth/me")).json()["username"] == START["username"]
    async with app.state.sessions() as db:
        account = await db.scalar(select(Account))
        assert account.age == 12 and account.chat_mode == "closed" and account.newsletter
        assert account.parent_email == FINISH["parent_email"]
        session = await db.scalar(select(Session))
        assert session.token_hash != cookie and len(session.token_hash) == 64
    # A separately initialized app can use persisted accounts and existing sessions.
    restarted = create_app(app.state.settings)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=restarted), base_url="http://test"
        ) as other:
            assert (
                await other.get("/api/auth/me", headers={"Authorization": f"Bearer {cookie}"})
            ).status_code == 200
    finally:
        await restarted.state.engine.dispose()
    assert (await client.post("/api/auth/logout")).status_code == 204
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (
        await client.get("/api/auth/me", headers={"Authorization": f"Bearer {cookie}"})
    ).status_code == 401


async def test_validation_duplicate_name_and_failed_password(client):
    for start in [
        {**START, "color_id": 13},
        {**START, "username": "a b"},
        {**START, "password": "s3"},
    ]:
        response = await client.post("/api/auth/registration-drafts", json=start)
        assert response.status_code == 422
        assert start["password"] not in response.text
    await register(client)
    response = await client.post(
        "/api/auth/registration-drafts", json={**START, "username": START["username"].lower()}
    )
    assert response.status_code == 409
    for username in [START["username"], "Unknown12"]:
        response = await client.post(
            "/api/auth/login", json={"username": username, "password": "wrong"}
        )
        assert response.status_code == 401 and "wrong" not in response.text


async def test_all_registration_steps_required_and_draft_is_single_use(client, app):
    assert (await client.post("/api/auth/register", json=FINISH)).status_code == 401
    assert (await client.post("/api/auth/registration-drafts", json=START)).status_code == 201
    for finish in [
        {**FINISH, "age": 0},
        {**FINISH, "parent_email": "broken"},
    ]:
        assert (await client.post("/api/auth/register", json=finish)).status_code == 422
    cookies = dict(client.cookies)

    async def finish():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test", cookies=cookies
        ) as other:
            return (await other.post("/api/auth/register", json=FINISH)).status_code

    assert sorted(await asyncio.gather(finish(), finish())) == [201, 401]
    async with app.state.sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Account)) == 1
        assert await db.scalar(select(func.count()).select_from(Session)) == 1


async def test_expired_registration_and_expired_session(client, app):
    assert (await client.post("/api/auth/registration-drafts", json=START)).status_code == 201
    async with app.state.sessions() as db:
        await db.execute(update(RegistrationDraft).values(expires_at=now() - timedelta(seconds=1)))
        await db.commit()
    assert (await client.post("/api/auth/register", json=FINISH)).status_code == 401
    await register(client)
    assert (
        await client.post("/api/auth/login", json={k: START[k] for k in ["username", "password"]})
    ).status_code == 200
    async with app.state.sessions() as db:
        await db.execute(update(Session).values(expires_at=now() - timedelta(seconds=1)))
        await db.commit()
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_legacy_xml_contract_shares_auth_services(client):
    await register(client)
    assert (await client.post("/api/auth/logout")).status_code == 204
    assert (await client.get("/legacy/servers")).status_code == 401
    for password, status in [("wrong", "2"), (START["password"], "1")]:
        response = await client.post(
            "/legacy/login", json={"username": START["username"], "password": password}
        )
        assert fromstring(response.content).find("Login").get("status") == status
        assert password not in response.text
    assert (await client.get("/api/auth/me")).status_code == 200
    server = fromstring((await client.get("/legacy/servers")).content).find("Servers/S")
    assert server.get("status") == "1" and server.get("webPort") == "0"


async def test_login_attempt_limit_and_no_password_in_error(client, app):
    app.state.attempt_limiter.limit = 2
    for _ in range(2):
        assert (
            await client.post("/api/auth/login", json={"username": "Unknown", "password": "Secret"})
        ).status_code == 401
    response = await client.post(
        "/api/auth/login", json={"username": "Unknown", "password": "Secret"}
    )
    assert response.status_code == 429
    assert "Secret" not in response.text
    assert response.headers["cache-control"] == "no-store"


async def test_multiple_remembered_sessions_resume_and_individual_logout(client, app):
    first = await register(client)
    response = await client.post(
        "/legacy/login",
        json={
            "username": START["username"],
            "password": START["password"],
            "remember_me": True,
        },
    )
    first_token = client.cookies.get("mogobe_session")
    assert "Max-Age=2592000" in response.headers["set-cookie"]
    other = {**START, "username": "Другой12", "color_id": 4}
    second = await register(client, other)
    await client.post(
        "/legacy/login",
        json={
            "username": other["username"],
            "password": other["password"],
            "remember_me": True,
        },
    )
    second_token = client.cookies.get("mogobe_session")
    # Logging in as the second account leaves the first account authorized.
    assert (
        await client.get("/api/auth/me", headers={"Authorization": f"Bearer {first_token}"})
    ).json()["id"] == first["id"]
    response = await client.post(
        "/legacy/resume",
        json={"username": START["username"].lower()},
        headers={"Authorization": f"Bearer {first_token}"},
    )
    login = fromstring(response.content).find("Login")
    assert login.get("status") == "1" and login.get("colorId") == "12"
    # A session cannot be reused to select a different account.
    response = await client.post(
        "/legacy/resume",
        json={"username": other["username"]},
        headers={"Authorization": f"Bearer {first_token}"},
    )
    assert fromstring(response.content).find("Login").get("status") == "2"
    await client.post("/api/auth/logout", headers={"Authorization": f"Bearer {first_token}"})
    response = await client.post(
        "/legacy/resume",
        json={"username": START["username"]},
        headers={"Authorization": f"Bearer {first_token}"},
    )
    assert fromstring(response.content).find("Login").get("status") == "2"
    assert (
        await client.get("/api/auth/me", headers={"Authorization": f"Bearer {second_token}"})
    ).json()["id"] == second["id"]
    async with app.state.sessions() as db:
        await db.execute(update(Session).values(expires_at=now() - timedelta(seconds=1)))
        await db.commit()
    response = await client.post(
        "/legacy/resume",
        json={"username": other["username"]},
        headers={"Authorization": f"Bearer {second_token}"},
    )
    assert fromstring(response.content).find("Login").get("status") == "2"
