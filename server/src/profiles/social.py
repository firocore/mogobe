"""Social operations are scoped to the authenticated account."""

from fastapi import HTTPException
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.sqlite import insert

from src.auth.models import Account
from src.profiles.models import FriendRequest, Friendship, SocialPreference
from src.profiles.service import find_profile
from src.world import catalog


def pair(a, b):
    return dict(zip(("first_id", "second_id"), sorted((a, b))))


async def accepted(db, owner, buddy):
    return await db.get(Friendship, tuple(sorted((owner, buddy)))) is not None


async def muted_ids(db, owner):
    return set(
        await db.scalars(
            select(SocialPreference.buddy_id).where(
                SocialPreference.owner_id == owner, SocialPreference.muted.is_(True)
            )
        )
    )


async def can_invite(db, owner, buddy):
    if owner == buddy or await accepted(db, owner, buddy):
        return False
    blocked = await db.scalar(
        select(SocialPreference.owner_id).where(
            or_(
                and_(SocialPreference.owner_id == owner, SocialPreference.buddy_id == buddy),
                and_(SocialPreference.owner_id == buddy, SocialPreference.buddy_id == owner),
            ),
            SocialPreference.muted.is_(True),
        )
    )
    requested = await db.get(FriendRequest, (owner, buddy))
    return blocked is None and requested is None


async def pending_count(db, owner):
    return await db.scalar(
        select(func.count()).select_from(FriendRequest).where(FriendRequest.recipient_id == owner)
    )


async def friend_ids(db, owner):
    relations = (
        await db.execute(
            select(Friendship.first_id, Friendship.second_id).where(
                or_(Friendship.first_id == owner, Friendship.second_id == owner)
            )
        )
    ).all()
    return {b if a == owner else a for a, b in relations}


async def presence_observers(db, buddy):
    owners = await friend_ids(db, buddy)
    owners.update(
        await db.scalars(select(FriendRequest.recipient_id).where(FriendRequest.sender_id == buddy))
    )
    owners.update(
        await db.scalars(
            select(SocialPreference.owner_id).where(
                SocialPreference.buddy_id == buddy, SocialPreference.muted.is_(True)
            )
        )
    )
    return owners


async def buddy_list(db, owner, hub):
    friends = await friend_ids(db, owner)
    requested = set(
        await db.scalars(select(FriendRequest.sender_id).where(FriendRequest.recipient_id == owner))
    )
    prefs = {
        p.buddy_id: p
        for p in await db.scalars(
            select(SocialPreference).where(SocialPreference.owner_id == owner)
        )
    }
    ids = friends | requested | {ident for ident, p in prefs.items() if p.muted}
    if not ids:
        return []
    accounts = await db.scalars(
        select(Account).where(Account.id.in_(ids)).order_by(Account.username_key)
    )
    result = []
    for account in accounts:
        pref = prefs.get(account.id)
        status = (
            3
            if pref and pref.muted
            else (4 if pref and pref.best else 2)
            if account.id in friends
            else 1
        )
        peer = hub.connections.get(account.id)
        online = peer is not None and peer.room is not None and peer.user is not None
        result.append(
            dict(
                buddyId=account.id,
                buddyName=account.username,
                status=status,
                # The original BuddyTO calls this label ServerName. Preserve the
                # wire contract (null means offline), but display the live room.
                serverName=catalog.BY_ID[peer.room]["title"] if online else None,
            )
        )
    return result


async def set_mute(db, owner, buddy, muted):
    if owner == buddy:
        raise HTTPException(400, "Нельзя выбрать самого себя")
    pref = await db.get(SocialPreference, (owner, buddy))
    if pref is None:
        pref = SocialPreference(owner_id=owner, buddy_id=buddy, muted=muted, best=False)
        db.add(pref)
    else:
        pref.muted = muted
    if muted:
        await db.execute(
            delete(FriendRequest).where(
                or_(
                    and_(FriendRequest.sender_id == buddy, FriendRequest.recipient_id == owner),
                    and_(FriendRequest.sender_id == owner, FriendRequest.recipient_id == buddy),
                )
            )
        )


async def operate(db, owner, command, params):
    target_params = {"userName": params.get("buddyName")}
    if params.get("buddyId") not in (None, -1):
        target_params["userId"] = params["buddyId"]
    buddy = await find_profile(db, target_params)
    if buddy.id == owner:
        raise HTTPException(400, "Нельзя выбрать самого себя")
    ident = buddy.id
    pref = await db.get(SocialPreference, (owner, ident))
    if command == "addBuddyRequest":
        if not await can_invite(db, owner, ident):
            return ident
        await db.execute(
            insert(FriendRequest)
            .values(sender_id=owner, recipient_id=ident)
            .on_conflict_do_nothing()
        )
    elif command == "acceptBuddyRequest":
        if await db.get(FriendRequest, (ident, owner)) is None:
            raise HTTPException(400, "Нет входящей заявки")
        if ident in await muted_ids(db, owner) or owner in await muted_ids(db, ident):
            raise HTTPException(400, "Могоби в игноре")
        await db.execute(insert(Friendship).values(**pair(owner, ident)).on_conflict_do_nothing())
        await db.execute(
            delete(FriendRequest).where(
                or_(
                    and_(FriendRequest.sender_id == ident, FriendRequest.recipient_id == owner),
                    and_(FriendRequest.sender_id == owner, FriendRequest.recipient_id == ident),
                )
            )
        )
    elif command == "rejectBuddyRequest":
        await db.execute(
            delete(FriendRequest).where(
                FriendRequest.sender_id == ident, FriendRequest.recipient_id == owner
            )
        )
    elif command == "blockBuddy":
        await set_mute(db, owner, ident, not (pref and pref.muted))
    elif command == "deleteBuddy":
        if pref and pref.muted:
            # Removing a row from the original Ignore tab means unmute.
            pref.muted = False
        else:
            await db.execute(delete(Friendship).filter_by(**pair(owner, ident)))
            await db.execute(
                update(SocialPreference)
                .where(
                    or_(
                        and_(
                            SocialPreference.owner_id == owner, SocialPreference.buddy_id == ident
                        ),
                        and_(
                            SocialPreference.owner_id == ident, SocialPreference.buddy_id == owner
                        ),
                    )
                )
                .values(best=False)
            )
    elif command in {"addToBestBuddy", "deleteFromBestBuddy"}:
        if not await accepted(db, owner, ident):
            raise HTTPException(400, "Могоби ещё не в друзьях")
        if command == "addToBestBuddy":
            count = await db.scalar(
                select(func.count())
                .select_from(SocialPreference)
                .where(SocialPreference.owner_id == owner, SocialPreference.best.is_(True))
            )
            if count >= 4 and not (pref and pref.best):
                raise HTTPException(400, "Можно выбрать до четырёх лучших друзей")
        if pref is None:
            pref = SocialPreference(owner_id=owner, buddy_id=ident, muted=False)
            db.add(pref)
        pref.best = command == "addToBestBuddy"
    else:
        raise HTTPException(400, "Неизвестное действие")
    await db.commit()
    return ident
