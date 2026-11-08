"""Market tools: new limited alerts, the watchlist (discount alerts) and player lookup.

All public data, no sign-in: Roblox's catalog search for new collectibles, Roblox's username lookup,
Rolimons' item list, deals page (current best prices) and player pages.
"""
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
