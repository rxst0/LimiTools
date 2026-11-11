"""Trade planner: suggests a fair trade so you don't have to puzzle it out. A planning tool only: you send the
trade yourself on Roblox.

- Upgrade (you pick what you want): finds up to 4 of your items worth the target value plus your overpay.
- Downgrade (you pick what you give): finds up to 4 in-demand items to ask for, worth your items plus your ask.
Items you've already put in keep their place; the planner fills the remaining slots, including with small
items ("smalls") to top up the value. Projected items and items on trade hold are never suggested.
"""
from bisect import bisect_left
from dataclasses import dataclass
from itertools import combinations

from .inventory import Inventory
from .items import ItemCatalog

MAX_SLOTS = 4
MAX_CANDIDATES = 70   # items considered for the open slots (closest values first, plus smalls)


@dataclass
class Suggestion:
    give: list[int]
    get: list[int]
    give_value: int
    get_value: int

    @property
    def overpay(self) -> float:
        """% you give above what you get (negative: you receive more)."""
        return (self.give_value - self.get_value) / self.get_value * 100 if self.get_value else 0.0


def _value(catalog: ItemCatalog, item_id: int) -> int:
    info = catalog.get(item_id)
    return info.default_value if info else 0


def _fill(need: int, pool: list[tuple[int, int]], slots: int, limit: int = 3) -> list[list[int]]:
    """Up to `limit` ways to pick 1..`slots` entries from pool [(id, value)] whose total is as close to `need`
    as possible. Each copy you own is its own entry, so two copies of an item can both be picked."""
    if slots <= 0 or not pool or need <= 0:
        return []
    nearest = sorted(range(len(pool)), key=lambda i: abs(pool[i][1] - need))[:MAX_CANDIDATES - 10]
    smalls = sorted(range(len(pool)), key=lambda i: pool[i][1])[:10]  # for topping up the value
    cand = [pool[i] for i in dict.fromkeys(nearest + smalls)]
    singles = [(v, (i,)) for i, (_id, v) in enumerate(cand)]
    combos = list(singles)
    pairs = sorted((cand[a][1] + cand[b][1], (a, b)) for a, b in combinations(range(len(cand)), 2))
    sums = [total for total, _ in pairs]
    if slots >= 2:
        combos += pairs
    if slots >= 3:
        for v, (a,) in singles:  # one item + the best-fitting pair
            j = bisect_left(sums, need - v)
            for k in (j - 1, j, j + 1):
                if 0 <= k < len(pairs) and a not in pairs[k][1]:
                    combos.append((v + pairs[k][0], (a,) + pairs[k][1]))
    if slots >= 4:
        for total, p1 in pairs[::max(1, len(pairs) // 2000)]:  # pair + best-fitting pair (sampled on big pools)
            j = bisect_left(sums, need - total)
            for k in (j - 1, j, j + 1):
                if 0 <= k < len(pairs) and not set(p1) & set(pairs[k][1]):
                    combos.append((total + pairs[k][0], p1 + pairs[k][1]))
    combos.sort(key=lambda c: abs(c[0] - need))
    results, seen = [], set()
    for _total, idx in combos:
        ids = tuple(sorted(cand[i][0] for i in idx))
        if ids not in seen:
            seen.add(ids)
            results.append(list(ids))
            if len(results) >= limit:
                break
    return results


def plan_upgrade(want: list[int], inventory: Inventory, catalog: ItemCatalog, overpay: float = 10.0,
                 keep_give: list[int] | None = None) -> list[Suggestion]:
    """You get `want`; suggest what to give (keep_give stays in), aiming for want's value + overpay %."""
    keep_give = list(keep_give or [])
    get_value = sum(_value(catalog, i) for i in want)
    target = int(get_value * (1 + overpay / 100))
    fixed_value = sum(_value(catalog, i) for i in keep_give)
    used = {i: keep_give.count(i) for i in keep_give}
    pool = []
    for item_id, count in inventory.counts.items():
        info = catalog.get(item_id)
        if not info or info.projected or info.default_value <= 0 or item_id in want:
            continue
        free = count - inventory.on_hold.get(item_id, 0) - used.get(item_id, 0)
        pool += [(item_id, info.default_value)] * max(0, min(free, MAX_SLOTS))
    out = []
    for extra in _fill(target - fixed_value, pool, MAX_SLOTS - len(keep_give)) or ([[]] if keep_give else []):
        give = keep_give + extra
        out.append(Suggestion(give, list(want), sum(_value(catalog, i) for i in give), get_value))
    return out


def plan_downgrade(give: list[int], catalog: ItemCatalog, ask: float = 10.0, keep_get: list[int] | None = None,
                   min_demand: int = 2) -> list[Suggestion]:
    """You give `give`; suggest in-demand items to ask for, worth give's value + ask % (more for you)."""
    keep_get = list(keep_get or [])
    give_value = sum(_value(catalog, i) for i in give)
    target = int(give_value * (1 + ask / 100))
    fixed_value = sum(_value(catalog, i) for i in keep_get)
    pool = [(i.id, i.default_value) for i in catalog.items.values()
            if i.id not in give and not i.projected and i.demand >= min_demand and 0 < i.default_value < give_value]
    out = []
    for extra in _fill(target - fixed_value, pool, MAX_SLOTS - len(keep_get)) or ([[]] if keep_get else []):
        get = keep_get + extra
        out.append(Suggestion(list(give), get, give_value, sum(_value(catalog, i) for i in get)))
    return out
