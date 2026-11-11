"""Trade ad alerts: Rolimons trade ads you could take with your own items, by your conditions.

An ad matches when its owner offers more value than they ask from you (by at least your minimum gain) and the
offer passes your other conditions. Ads that ask for specific items match only if you own them (copies on
trade hold don't count). Ads that ask only with tags ("any", "upgrade", "downgrade", ...) can match too: the
app then picks which of your items to give. Either way it only notifies you: you send the trade yourself.
"""
from dataclasses import dataclass

from .config import AdAlertSettings
from .inventory import Inventory
from .items import ItemCatalog
from .market import AD_TAGS, TradeAd
from .trade_planner import MAX_SLOTS, _fill

ROBUX_RATE = 0.7   # Robux in a trade arrive after Roblox's 30% fee
TAG_FIT = 0.9      # tag-only ads: your offer is 90-100% of the value that still gives you your minimum gain
# Tag-only ads the app can answer with your items; the rest ask for robux, rares, projecteds or wishlist items.
ANSWERABLE_TAGS = {"any", "demand", "rap", "upgrade", "downgrade", "adds"}


@dataclass
class AdMatch:
    ad: TradeAd
    give: list[int]
    give_value: int
    get_value: int
    picked: bool   # True when the app chose what you give (a tag-only ad)

    @property
    def gain(self) -> float:
        return (self.get_value - self.give_value) / self.give_value * 100 if self.give_value else 0.0

    @property
    def trade_url(self) -> str:
        return f"https://www.roblox.com/users/{self.ad.user_id}/trade"


def _value(catalog: ItemCatalog, item_id: int) -> int:
    info = catalog.get(item_id)
    return info.default_value if info else 0


def _fits_kind(kind: str, give_count: int, get_count: int) -> bool:
    if kind == "upgrade":
        return get_count < give_count
    if kind == "downgrade":
        return get_count > give_count
    return True


def match_ad(ad: TradeAd, inventory: Inventory, catalog: ItemCatalog, rules: AdAlertSettings) -> AdMatch | None:
    """The trade you could make from this ad, or None if it doesn't meet your conditions."""
    if not ad.offer_items and not ad.offer_robux:
        return None
    offered = [catalog.get(i) for i in ad.offer_items]
    if any(info is None or info.default_value <= 0 for info in offered):
        return None  # something Rolimons can't value
    if rules.block_projected and any(info.projected for info in offered):
        return None
    if rules.min_demand >= 0 and any(info.demand < rules.min_demand for info in offered):
        return None
    get_value = sum(info.default_value for info in offered) + int(ad.offer_robux * ROBUX_RATE)
    blocked = set(rules.never_give)
    free = {i: n - inventory.on_hold.get(i, 0) for i, n in inventory.counts.items() if i not in blocked}
    get_count = len(ad.offer_items) + bool(ad.offer_robux)

    if ad.request_items:
        give = list(ad.request_items)
        if any(free.get(i, 0) < give.count(i) for i in set(give)):
            return None  # you don't own them (or they're on hold, or on your never-give list)
        picked = False
    else:
        tags = {AD_TAGS.get(t, "") for t in ad.request_tags}
        if not rules.tag_ads or not tags or not tags <= ANSWERABLE_TAGS:
            return None
        if "upgrade" in tags and "downgrade" in tags:
            return None
        min_demand = 2 if "demand" in tags else -1
        pool = []
        for item_id, count in free.items():
            info = catalog.get(item_id)
            if info and not info.projected and info.default_value > 0 and info.demand >= min_demand \
                    and item_id not in ad.offer_items:
                pool += [(item_id, info.default_value)] * max(0, min(count, MAX_SLOTS))
        # An offer they might take: close to (within 10% under) the most you can give and still gain your
        # minimum. Far smaller offers would never be accepted, so they don't count as a match.
        need = int(get_value / (1 + max(rules.min_gain, 0) / 100))
        give = None
        for option in _fill(need, pool, MAX_SLOTS, limit=12):
            value = sum(_value(catalog, i) for i in option)
            # They tagged "upgrade": they want fewer items back than they give; "downgrade": more.
            if "upgrade" in tags and not len(option) < get_count:
                continue
            if "downgrade" in tags and not len(option) > get_count:
                continue
            if TAG_FIT * need <= value <= need and _fits_kind(rules.kind, len(option), get_count):
                give = option
                break
        if not give:
            return None
        picked = True

    give_value = sum(_value(catalog, i) for i in give)
    if give_value <= 0 or not _fits_kind(rules.kind, len(give), get_count):
        return None
    if rules.min_value and give_value < rules.min_value:
        return None
    if rules.max_value and give_value > rules.max_value:
        return None
    match = AdMatch(ad, give, give_value, get_value, picked)
    return match if match.gain >= rules.min_gain else None


def find_matches(ads: list[TradeAd], inventory: Inventory, catalog: ItemCatalog, rules: AdAlertSettings,
                 me: int = 0) -> list[AdMatch]:
    """Matching ads, best gain first (one per poster: their newest matching ad)."""
    out, posters = [], set()
    for ad in ads:
        if ad.user_id == me or ad.user_id in posters:
            continue
        match = match_ad(ad, inventory, catalog, rules)
        if match:
            posters.add(ad.user_id)
            out.append(match)
    out.sort(key=lambda m: -m.gain)
    return out


def match_alert(match: AdMatch, catalog: ItemCatalog) -> tuple[str, str]:
    """(title, text) for the notification."""
    def names(ids):
        labels = [(catalog.get(i).acronym or catalog.get(i).name) if catalog.get(i) else str(i) for i in ids]
        return ", ".join(labels[:3]) + (f" +{len(labels) - 3}" if len(labels) > 3 else "")
    ad = match.ad
    offer = names(ad.offer_items) + (f" + {ad.offer_robux:,} R$" if ad.offer_robux else "")
    title = f"{ad.name}: +{match.gain:.0f}% for your {names(match.give)}"
    text = (f"They offer {offer or 'robux'} ({match.get_value:,}) for {names(match.give)} ({match.give_value:,})"
            + (", picked by the app from your items" if match.picked else "")
            + ". Tap to open a trade with them; you send it yourself.")
    return title, text
