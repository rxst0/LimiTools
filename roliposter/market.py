"""Market tools: new limited alerts, the watchlist (discount alerts) and player lookup.

All public data, no sign-in: Roblox's catalog search for new collectibles, Roblox's username lookup,
Rolimons' item list, deals page (current best prices) and player pages.
"""
import html
import re
import time
from dataclasses import dataclass

import requests

from .items import USER_AGENT, ItemCatalog
from .portfolio import realistic_price

NEW_LIMITEDS_URL = ("https://catalog.roblox.com/v1/search/items/details"
                    "?Category=1&SalesTypeFilter=2&SortType=3&Limit=30")
USERNAMES_URL = "https://users.roblox.com/v1/usernames/users"


# ---- new limiteds ------------------------------------------------------------------------------
@dataclass
class NewLimited:
    id: int
    item_type: str      # "Asset" or "Bundle"
    name: str
    description: str
    price: int
    copies: int         # total stock (0 when unknown)
    left: int           # copies still for sale
    creator: str
    creator_verified: bool

    @property
    def url(self) -> str:
        kind = "bundles" if self.item_type == "Bundle" else "catalog"
        return f"https://www.roblox.com/{kind}/{self.id}"


def parse_new_limiteds(data: dict) -> list[NewLimited]:
    items = []
    for row in data.get("data") or []:
        try:
            items.append(NewLimited(
                id=int(row["id"]), item_type=str(row.get("itemType") or "Asset"), name=str(row.get("name") or ""),
                description=str(row.get("description") or "").strip(), price=int(row.get("price") or 0),
                copies=int(row.get("totalQuantity") or 0), left=int(row.get("unitsAvailableForConsumption") or 0),
                creator=str(row.get("creatorName") or ""), creator_verified=bool(row.get("creatorHasVerifiedBadge"))))
        except (KeyError, TypeError, ValueError):
            continue
    return items


def fetch_new_limiteds(session: requests.Session, timeout: float = 20) -> list[NewLimited]:
    resp = session.get(NEW_LIMITEDS_URL, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return parse_new_limiteds(resp.json())


def wanted_limited(item: NewLimited, verified_only: bool, max_price: int, max_copies: int) -> bool:
    """The user's filters: 0 means no limit."""
    if verified_only and not item.creator_verified:
        return False
    if max_price and item.price > max_price:
        return False
    if max_copies and (not item.copies or item.copies > max_copies):
        return False
    return True


def limited_alert(item: NewLimited) -> tuple[str, str]:
    """(title, text) for the notification."""
    stock = f" · {item.copies:,} copies" if item.copies else ""
    title = f"New limited: {item.name} · {item.price:,} R$" if item.price else f"New limited: {item.name}"
    creator = f"By {item.creator}{' (verified)' if item.creator_verified else ''}{stock}."
    description = item.description if len(item.description) <= 400 else item.description[:397] + "..."
    return title, f"{creator}\n{description}" if description else creator


# ---- watchlist ---------------------------------------------------------------------------------
@dataclass
class Deal:
    item_id: int
    name: str
    price: int
    value: int
    discount: float     # percent below value


def watchlist_deals(watchlist: dict[int, float], catalog: ItemCatalog, prices: dict[int, int]) -> list[Deal]:
    """Watched items listed at least their chosen discount below value (joke listings ignored)."""
    deals = []
    for item_id, min_discount in watchlist.items():
        info = catalog.get(item_id)
        if not info or info.default_value <= 0:
            continue
        price = realistic_price(prices.get(item_id), info.default_value, info.rap)
        if not price:
            continue
        discount = (info.default_value - price) / info.default_value * 100
        if discount >= min_discount:
            deals.append(Deal(item_id, info.label, price, info.default_value, discount))
    deals.sort(key=lambda d: -d.discount)
    return deals


def deal_alert(deal: Deal) -> tuple[str, str]:
    return (f"{deal.name} is {deal.discount:.0f}% under value",
            f"Listed at {deal.price:,} R$ · value {deal.value:,}. Tap to open it on Roblox.")


# ---- player lookup -----------------------------------------------------------------------------
@dataclass
class Player:
    id: int
    name: str
    display_name: str
    verified: bool


def lookup_username(session: requests.Session, username: str, timeout: float = 15) -> Player | None:
    username = username.strip().lstrip("@")
    if not username:
        return None
    resp = session.post(USERNAMES_URL, json={"usernames": [username], "excludeBannedUsers": False},
                        headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    rows = resp.json().get("data") or []
    if not rows:
        return None
    row = rows[0]
    return Player(int(row["id"]), str(row.get("name") or username), str(row.get("displayName") or ""),
                  bool(row.get("hasVerifiedBadge")))


# ---- remembering what was already announced --------------------------------------------------------
class Seen:
    """IDs already announced, so each new limited / deal notifies once (deals again after a day)."""

    def __init__(self, data: dict | None = None):
        self.data = data or {}

    def first_time(self, kind: str) -> bool:
        return kind not in self.data

    def is_new(self, kind: str, key: str, ttl: float | None = None, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        seen = self.data.setdefault(kind, {})
        last = seen.get(key)
        if last is not None and (ttl is None or now - last < ttl):
            return False
        seen[key] = now
        if len(seen) > 1000:  # keep the newest
            for old in sorted(seen, key=seen.get)[:len(seen) - 1000]:
                del seen[old]
        return True


# ---- Discover: richest players, active traders, verified accounts, tracked players ------------------
LEADERBOARD_URL = "https://www.rolimons.com/leaderboard"
RECENT_ADS_URL = "https://api.rolimons.com/tradeads/v1/getrecentads"
USERS_URL = "https://users.roblox.com/v1/users"
USER_URL = "https://users.roblox.com/v1/users/{}"
_LEADER = re.compile(r'<a href="/player/(\d+)"><div><h6[^>]*title="([^"]*)".*?#([\d,]+)</span>.*?R\$ ([\d,]+)</span>'
                     r'.*?RAP</small>.*?R\$ ([\d,]+)', re.S)


@dataclass
class Leader:
    id: int
    name: str
    rank: int
    value: int
    rap: int


@dataclass
class TradeAd:
    id: int
    time: float
    user_id: int
    name: str
    offer_items: list[int]
    offer_robux: int
    request_items: list[int]
    request_tags: list[int]


def parse_leaderboard(page: str) -> list[Leader]:
    leaders = []
    for m in _LEADER.finditer(page):
        player_id, name, rank, value, rap = m.groups()
        leaders.append(Leader(int(player_id), html.unescape(name), int(rank.replace(",", "")),
                              int(value.replace(",", "")), int(rap.replace(",", ""))))
    return leaders


def fetch_leaderboard(session: requests.Session, timeout: float = 25) -> list[Leader]:
    resp = session.get(LEADERBOARD_URL, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return parse_leaderboard(resp.text)


def parse_recent_ads(data: dict) -> list[TradeAd]:
    """Rolimons' latest trade ads: [ad id, time, user id, username, {offer}, {request}], newest first."""
    ads = []
    for row in data.get("trade_ads") or []:
        try:
            ad_id, when, user_id, name, offer, request = row[:6]
            ads.append(TradeAd(int(ad_id), float(when), int(user_id), str(name),
                               [int(i) for i in offer.get("items", [])], int(offer.get("robux") or 0),
                               [int(i) for i in request.get("items", [])], [int(t) for t in request.get("tags", [])]))
        except (TypeError, ValueError, AttributeError):
            continue
    ads.sort(key=lambda a: -a.time)
    return ads


def fetch_recent_ads(session: requests.Session, timeout: float = 20) -> list[TradeAd]:
    resp = session.get(RECENT_ADS_URL, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return parse_recent_ads(resp.json())


def active_traders(ads: list[TradeAd], owned: set[int], wanted: set[int], limit: int = 50) -> list[tuple[TradeAd, str]]:
    """One row per trader (their newest ad), ads that matter to you first: they want something you own,
    or offer something on your watchlist. Returns (ad, why it matters or "")."""
    seen, rows = set(), []
    for ad in ads:
        if ad.user_id in seen:
            continue
        seen.add(ad.user_id)
        reasons = []
        if wanted & set(ad.offer_items):
            reasons.append("offers an item you're watching")
        if owned & set(ad.request_items):
            reasons.append("wants an item you own")
        rows.append((ad, " and ".join(reasons)))
    rows.sort(key=lambda r: (not r[1], -r[0].time))
    return rows[:limit]


def verified_ids(session: requests.Session, user_ids: list[int], timeout: float = 20) -> set[int]:
    """Which of these Roblox users have the verified badge (batches of 100)."""
    found = set()
    for start in range(0, len(user_ids), 100):
        resp = session.post(USERS_URL, json={"userIds": user_ids[start:start + 100], "excludeBannedUsers": True},
                            headers={"User-Agent": USER_AGENT}, timeout=timeout)
        resp.raise_for_status()
        found |= {int(u["id"]) for u in resp.json().get("data") or [] if u.get("hasVerifiedBadge")}
    return found


def lookup_user_id(session: requests.Session, user_id: int, timeout: float = 15) -> Player | None:
    resp = session.get(USER_URL.format(int(user_id)), headers={"User-Agent": USER_AGENT}, timeout=timeout)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    row = resp.json()
    return Player(int(row["id"]), str(row.get("name") or ""), str(row.get("displayName") or ""),
                  bool(row.get("hasVerifiedBadge")))


def describe_ad(ad: TradeAd, catalog: ItemCatalog | None) -> str:
    """"Dominus Empyreus + 2 more for upgrade, demand" style summary."""
    def names(ids):
        labels = [(catalog.get(i).acronym or catalog.get(i).name) if catalog and catalog.get(i) else str(i) for i in ids]
        return ", ".join(labels[:3]) + (f" +{len(labels) - 3}" if len(labels) > 3 else "")
    tags = [AD_TAGS.get(t, str(t)) for t in ad.request_tags]
    offer = names(ad.offer_items) + (f" + {ad.offer_robux:,} R$" if ad.offer_robux else "")
    want = ", ".join([names(ad.request_items)] * bool(ad.request_items) + tags) or "anything"
    return f"{offer or 'robux'} for {want}"


AD_TAGS = {1: "any", 2: "demand", 3: "rares", 4: "robux", 5: "upgrade", 6: "downgrade", 7: "rap", 8: "wishlist",
           9: "projecteds", 10: "adds"}
