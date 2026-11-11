from roliposter.ad_match import find_matches, match_ad, match_alert
from roliposter.config import AdAlertSettings, Config, validate_config
from roliposter.inventory import Inventory
from roliposter.items import parse_item_details
from roliposter.market import TradeAd

# [name, acronym, rap, value, default_value, demand, trend, projected, hyped, rare]
CATALOG = parse_item_details({"success": True, "items": {
    "1": ["Big", "B", 10000, 10000, 10000, 3, 2, -1, -1, -1],
    "2": ["Mid", "M", 6000, 6000, 6000, 3, 2, -1, -1, -1],
    "3": ["Mid2", "M2", 5000, 5000, 5000, 2, 2, -1, -1, -1],
    "4": ["Small", "S", 1000, 1000, 1000, 1, 2, -1, -1, -1],
    "5": ["Projected", "P", 12000, 12000, 12000, 3, 2, 1, -1, -1],
    "6": ["Low demand", "L", 12000, 12000, 12000, 0, 2, -1, -1, -1],
}})
INV = Inventory(counts={2: 1, 3: 1, 4: 2})


def ad(offer, request=(), tags=(), robux=0, user=50, ad_id=1):
    return TradeAd(ad_id, 0.0, user, "trader", list(offer), robux, list(request), list(tags))


def test_overpay_for_items_you_own():
    m = match_ad(ad([1], request=[2]), INV, CATALOG, AdAlertSettings(min_gain=5))
    assert m and m.give == [2] and m.give_value == 6000 and round(m.gain) == 67 and not m.picked
    assert m.trade_url == "https://www.roblox.com/users/50/trade"
    title, text = match_alert(m, CATALOG)
    assert "+67%" in title and "you send it yourself" in text


def test_conditions():
    rules = AdAlertSettings(min_gain=5)
    assert match_ad(ad([2], request=[1]), INV, CATALOG, rules) is None            # you don't own it
    assert match_ad(ad([4], request=[2]), INV, CATALOG, rules) is None            # a loss for you
    assert match_ad(ad([5], request=[2]), INV, CATALOG, rules) is None            # projected offered
    assert match_ad(ad([6], request=[2]), INV, CATALOG, AdAlertSettings(min_demand=2)) is None
    assert match_ad(ad([1], request=[2]), INV, CATALOG, AdAlertSettings(never_give=[2])) is None
    held = Inventory(counts={2: 1}, on_hold={2: 1})
    assert match_ad(ad([1], request=[2]), held, CATALOG, rules) is None           # on trade hold
    assert match_ad(ad([1], request=[2]), INV, CATALOG, AdAlertSettings(max_value=5000)) is None
    assert match_ad(ad([1], request=[4, 4]), INV, CATALOG, AdAlertSettings(kind="downgrade")) is None
    assert match_ad(ad([1], request=[4, 4]), INV, CATALOG, AdAlertSettings(kind="upgrade")) is not None


def test_tag_only_ads_pick_your_items():
    inv = Inventory(counts={2: 1, 4: 3})
    m = match_ad(ad([1], tags=[1]), inv, CATALOG, AdAlertSettings(min_gain=5))     # "any"
    assert m and m.picked and m.give_value == 9000 and 5 <= m.gain <= 17
    assert match_ad(ad([1], tags=[4]), inv, CATALOG, AdAlertSettings()) is None    # wants robux
    assert match_ad(ad([1], tags=[1]), inv, CATALOG, AdAlertSettings(tag_ads=False)) is None
    m = match_ad(ad([1], tags=[6]), inv, CATALOG, AdAlertSettings())               # they want a downgrade
    assert m and len(m.give) > 1
    small = Inventory(counts={4: 2})                                                # far too little to offer
    assert match_ad(ad([1], tags=[1]), small, CATALOG, AdAlertSettings()) is None


def test_find_matches_skips_you_and_repeats():
    ads = [ad([1], request=[2], ad_id=1), ad([1], request=[3], ad_id=2), ad([1], request=[3], user=7, ad_id=3)]
    found = find_matches(ads, INV, CATALOG, AdAlertSettings(), me=7)
    assert [m.ad.id for m in found] == [1]


def test_settings_validation():
    cfg = Config()
    cfg.ad_alerts.kind = "sideways"
    cfg.ad_alerts.max_value, cfg.ad_alerts.min_value = 10, 20
    errors = " ".join(validate_config(cfg))
    assert "kind must be" in errors and "minimum and maximum value" in errors
