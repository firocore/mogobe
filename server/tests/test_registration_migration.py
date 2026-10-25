"""Registration age migration preserves existing player data."""

import asyncio
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta

import pytest
from alembic.config import Config
from sqlalchemy.ext.asyncio import async_sessionmaker

from alembic import command
from src.auth.models import Account, Session
from src.config import ROOT
from src.database import make_engine
from src.inventory.models import EquippedItem
from src.minigames.models import GameRun
from src.profiles.models import FriendRequest, Friendship, SocialPreference
from src.shops.models import Item, OwnedItem, Wallet


def contents(path):
    with closing(sqlite3.connect(path)) as db:
        names = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name!='alembic_version' ORDER BY name"
        )
        return {
            name: db.execute(f'SELECT * FROM "{name}" ORDER BY 1').fetchall()
            for (name,) in names.fetchall()
        }


async def seed(url):
    engine = make_engine(url)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        now = datetime.now(UTC)
        async with factory() as db:
            accounts = [
                Account(
                    username=name,
                    username_key=name.lower(),
                    password_hash="test-hash",
                    color_id=7,
                    age=12,
                    chat_mode="open",
                    newsletter=True,
                    parent_email="test@example.invalid",
                    terms_accepted_at=now,
                    created_at=now,
                    is_admin=True,
                    experience=1500,
                )
                for name in ("MigrationA", "MigrationB")
            ]
            db.add_all(accounts)
            await db.flush()
            first, second = accounts
            db.add(Item(id=100, name="Test shirt", main_type=1, inventory_category=4, enabled=True))
            await db.flush()
            owned = OwnedItem(account_id=first.id, item_id=100)
            db.add(owned)
            await db.flush()
            db.add_all(
                [
                    Session(
                        token_hash="a" * 64, account_id=first.id, expires_at=now + timedelta(days=1)
                    ),
                    Friendship(first_id=first.id, second_id=second.id),
                    FriendRequest(sender_id=second.id, recipient_id=first.id),
                    SocialPreference(owner_id=first.id, buddy_id=second.id, muted=True, best=True),
                    Wallet(account_id=first.id, coins=777),
                    EquippedItem(account_id=first.id, slot=4, owned_item_id=owned.id),
                    GameRun(
                        id="migration-game",
                        account_id=first.id,
                        game_key="goldfishing",
                        room_id=3,
                        started_at=now,
                        finished_at=now,
                        status="finished",
                        score=25,
                        coins=9,
                        experience=3,
                    ),
                ]
            )
            await db.commit()
    finally:
        await engine.dispose()


def assert_integrity(path):
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
        assert db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]


def test_registration_age_migration_preserves_players(tmp_path, monkeypatch):
    path = tmp_path / "populated.sqlite3"
    url = "sqlite+aiosqlite:///" + path.as_posix()
    monkeypatch.setenv("MOGOBE_DATABASE_URL", url)
    monkeypatch.setenv("MOGOBE_BOOTSTRAP_DEFAULTS", "false")
    cfg = Config(str(ROOT / "alembic.ini"))
    command.upgrade(cfg, "e265minigameexp")
    asyncio.run(seed(url))
    before = contents(path)

    command.upgrade(cfg, "e266registrationage")
    assert contents(path) == before
    assert_integrity(path)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("UPDATE auth_account SET age=42 WHERE username='MigrationA'")
    after = contents(path)
    with pytest.raises(RuntimeError, match="Cannot downgrade"):
        command.downgrade(cfg, "e265minigameexp")
    assert contents(path) == after
    with closing(sqlite3.connect(path)) as db, db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone() == (
            "e266registrationage",
        )
        db.execute("UPDATE auth_account SET age=12 WHERE username='MigrationA'")

    command.downgrade(cfg, "e265minigameexp")
    assert contents(path) == before
    assert_integrity(path)
    with closing(sqlite3.connect(path)) as db, db:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE auth_account SET age=42 WHERE username='MigrationA'")
