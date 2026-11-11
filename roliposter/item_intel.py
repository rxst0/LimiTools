"""Item intelligence from a Rolimons item page (rolimons.com/item/<id>): RAP and price history, daily sales,
value changes, owners and hoarders, and who got a copy most recently. Public data, no sign-in.

The page embeds its data as `var history_data = {...};` and similar; this module only reads those.
"""
import json
import re
import time
from dataclasses import dataclass, field

import requests

from .items import USER_AGENT
from .portfolio import Series

ITEM_PAGE_URL = "https://www.rolimons.com/item/{}"
DAY = 86400


@dataclass
class Owner:
    user_id: int
    name: str
    copies: int
    since: float | None = None   # when they got their newest copy


@dataclass
class ItemIntel:
    item_id: int
    rap: Series
    best_price: Series
    sales_price: Series            # average sale price per day
    sales_volume: Series           # sales per day
    value_changes: list = field(default_factory=list)   # [(time, value)] oldest first
    owners: int = 0
    copies: int = 0
    hoarded: int = 0
    deleted: int = 0
    hoarders: list = field(default_factory=list)        # [Owner] most copies first
    recent_owners: list = field(default_factory=list)   # [Owner] newest copy first

    def sales_summary(self, days: int = 30, now: float | None = None) -> tuple[int, int | None]:
        """(number of sales, average price) over the last `days` days."""
        part_volume = self.sales_volume.since(days * DAY, now=now)
        part_price = self.sales_price.since(days * DAY, now=now)
        start = (now or time.time()) - days * DAY
        pairs = [(v, p) for t, v, p in zip(part_volume.times, part_volume.values, part_price.values) if t >= start]
        count = sum(v for v, _p in pairs)
        if not count:
            return 0, None
        return count, int(sum(v * p for v, p in pairs) / count)


def _var(page: str, name: str):
    m = re.search(r"var\s+%s\s*=\s*(.*?);\s*\n" % re.escape(name), page, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


def _series(data: dict | None, times_key: str, values_key: str) -> Series:
    if not data:
        return Series([], [])
    points = [(float(t), int(v)) for t, v in zip(data.get(times_key) or [], data.get(values_key) or [])
              if t is not None and v is not None]
    points.sort()
    return Series([p[0] for p in points], [p[1] for p in points])


def parse_item_page(item_id: int, page: str) -> ItemIntel:
    history = _var(page, "history_data")
    if not isinstance(history, dict):
        raise ValueError("No item data on the Rolimons item page")
    sales = _var(page, "sales_data") or {}
    intel = ItemIntel(item_id, _series(history, "timestamp", "rap"), _series(history, "timestamp", "best_price"),
                      _series(sales, "timestamp", "avg_daily_sales_price"), _series(sales, "timestamp", "sales_volume"))
    # value_changes rows: [time, field, ?, new]; field 1 is the value.
    for row in _var(page, "value_changes") or []:
        if isinstance(row, list) and len(row) >= 4 and row[1] == 1 and isinstance(row[3], (int, float)):
            intel.value_changes.append((float(row[0]), int(row[3])))
    intel.value_changes.sort()
    ownership = _var(page, "ownership_data") or {}
    for attr, key in (("owners", "owners"), ("copies", "copies"), ("hoarded", "hoarded_copies"),
                      ("deleted", "deleted_copies")):
        values = ownership.get(key) or []
        setattr(intel, attr, int(values[-1] or 0) if values else 0)
    hoards = _var(page, "hoards_data") or {}
    intel.hoarders = sorted((Owner(int(i), str(n), int(q)) for i, n, q in
                             zip(hoards.get("owner_ids") or [], hoards.get("owner_names") or [], hoards.get("quantities") or [])
                             if i is not None), key=lambda o: -o.copies)
    copies = _var(page, "all_copies_data") or {}
    latest: dict[int, Owner] = {}
    for i, n, q, updated in zip(copies.get("owner_ids") or [], copies.get("owner_names") or [],
                                copies.get("quantities") or [], copies.get("updated") or []):
        if i is None or updated is None:
            continue
        when = float(updated) / 1000  # milliseconds
        known = latest.get(int(i))
        if known is None or when > (known.since or 0):
            latest[int(i)] = Owner(int(i), str(n or ""), int(q or 1), when)
    intel.recent_owners = sorted(latest.values(), key=lambda o: -(o.since or 0))[:30]
    return intel


def fetch_item_intel(session: requests.Session, item_id: int, timeout: float = 30) -> ItemIntel:
    resp = session.get(ITEM_PAGE_URL.format(int(item_id)), headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return parse_item_page(item_id, resp.text)
