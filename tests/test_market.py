from roliposter.items import parse_item_details
from roliposter.market import (Seen, deal_alert, limited_alert, lookup_username, parse_new_limiteds,
                               wanted_limited, watchlist_deals)

CATALOG_JSON = {"data": [
    {"id": 139948880941094, "itemType": "Asset", "name": "Christmas Deer Horns", "description": "Glowing antlers.",
     "price": 555, "totalQuantity": 888, "unitsAvailableForConsumption": 885, "creatorName": "Anxiogenicity",
     "creatorHasVerifiedBadge": False},
    {"id": 7, "itemType": "Bundle", "name": "Big Bundle", "description": "x" * 600, "price": 50000,
     "totalQuantity": 0, "creatorName": "Roblox", "creatorHasVerifiedBadge": True},
    {"name": "no id"},
]}
CATALOG = parse_item_details({"success": True, "items": {
    "1": ["Watched Hat", "WH", 9000, 10000, 10000, 3, 2, -1, -1, -1],
    "2": ["Joke Listed", "JL", 900, 1000, 1000, 1, 2, -1, -1, -1],
    "3": ["Barely Cheaper", "BC", 900, 1000, 1000, 1, 2, -1, -1, -1],
}})


def test_parse_new_limiteds_and_urls():
    items = parse_new_limiteds(CATALOG_JSON)
    assert [i.id for i in items] == [139948880941094, 7]
    assert items[0].copies == 888 and items[0].left == 885 and not items[0].creator_verified
    assert items[0].url == "https://www.roblox.com/catalog/139948880941094"
    assert items[1].url == "https://www.roblox.com/bundles/7"


def test_new_limited_filters():
    horns, bundle = parse_new_limiteds(CATALOG_JSON)
    assert wanted_limited(horns, verified_only=False, max_price=0, max_copies=0)
    assert not wanted_limited(horns, verified_only=True, max_price=0, max_copies=0)
    assert not wanted_limited(horns, verified_only=False, max_price=500, max_copies=0)
    assert not wanted_limited(horns, verified_only=False, max_price=0, max_copies=500)
    assert not wanted_limited(bundle, verified_only=False, max_price=0, max_copies=100)  # unknown stock


def test_limited_alert_has_price_and_description():
    horns, bundle = parse_new_limiteds(CATALOG_JSON)
    title, text = limited_alert(horns)
    assert title == "New limited: Christmas Deer Horns · 555 R$"
    assert "Anxiogenicity" in text and "888 copies" in text and "Glowing antlers." in text
    assert len(limited_alert(bundle)[1]) < 450  # long descriptions are shortened


def test_watchlist_deals():
    deals = watchlist_deals({1: 10, 2: 10, 3: 10, 99: 10}, CATALOG, {1: 8500, 2: 999_999, 3: 950})
    assert [(d.item_id, round(d.discount)) for d in deals] == [(1, 15)]  # 2 is a joke listing, 3 only 5% off
    assert [d.item_id for d in watchlist_deals({1: 10, 3: 10}, CATALOG, {1: 8500, 3: 100})] == [3, 1]  # biggest first
    assert "15% under value" in deal_alert(deals[0])[0]


def test_seen_remembers_and_expires():
    seen = Seen()
    assert seen.first_time("limiteds")
    assert seen.is_new("limiteds", "1", now=100)
    assert not seen.is_new("limiteds", "1", now=200)
    assert not seen.first_time("limiteds")
    assert seen.is_new("deals", "1", ttl=86400, now=0)
    assert not seen.is_new("deals", "1", ttl=86400, now=100)
    assert seen.is_new("deals", "1", ttl=86400, now=90000)


class _Resp:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


class _Session:
    def __init__(self, data):
        self.data, self.sent = data, None

    def post(self, url, json=None, headers=None, timeout=None):
        self.sent = json
        return _Resp(self.data)


def test_lookup_username():
    session = _Session({"data": [{"id": 156, "name": "builderman", "displayName": "builderman", "hasVerifiedBadge": True}]})
    player = lookup_username(session, " @Builderman ")
    assert (player.id, player.name, player.verified) == (156, "builderman", True)
    assert session.sent["usernames"] == ["Builderman"]
    assert lookup_username(_Session({"data": []}), "nobody") is None
    assert lookup_username(_Session({}), "  ") is None


LEADERBOARD_HTML = (
    '<div><a href="/player/1"><div><h6 class="x" title="Roblox" style="">Roblox</h6></div><img>'
    '<small>Rank</small><span class="a">#1</span><small>Value</small><span class="b">R$ 1,362,264,144</span>'
    '<small class="text-muted">RAP</small></div><div><span class="c">R$ 425,000,000</span></a></div>'
    '<div><a href="/player/80254"><div><h6 title="Stick &amp; Luke">Stick</h6></div>'
    '<span>#2</span><span>R$ 990,925,098</span><small>RAP</small><span>R$ 12</span></a></div>')
RECENT_ADS = {"success": True, "trade_ads": [
    [11, 1000, 5, "older", {"items": [1]}, {"tags": [5]}],
    [12, 2000, 6, "wantsyours", {"items": [9]}, {"items": [1], "tags": []}],
    [13, 3000, 5, "newer", {"items": [2], "robux": 500}, {"tags": [1, 4]}],
    [14, 4000, 7, "nomatch", {"items": [3]}, {"tags": [2]}],
    ["bad row"],
]}


def test_parse_leaderboard():
    from roliposter.market import parse_leaderboard
    leaders = parse_leaderboard(LEADERBOARD_HTML)
    assert [(l.id, l.name, l.rank, l.value, l.rap) for l in leaders] == [
        (1, "Roblox", 1, 1362264144, 425000000), (80254, "Stick & Luke", 2, 990925098, 12)]


def test_recent_ads_and_active_traders():
    from roliposter.market import active_traders, describe_ad, parse_recent_ads
    ads = parse_recent_ads(RECENT_ADS)
    assert [a.id for a in ads] == [14, 13, 12, 11]  # newest first, bad row skipped
    rows = active_traders(ads, owned={1}, wanted={2})
    # one row per trader (their newest ad), the ones that matter to you first
    assert [(r[0].name, r[1]) for r in rows] == [
        ("newer", "offers an item you're watching"), ("wantsyours", "wants an item you own"), ("nomatch", "")]
    assert describe_ad(ads[1], CATALOG) == "JL + 500 R$ for any, robux"
    assert describe_ad(ads[2], CATALOG).startswith("9 for WH")


def test_verified_ids_batches():
    from roliposter.market import verified_ids
    calls = []

    class S:
        def post(self, url, json=None, headers=None, timeout=None):
            calls.append(json["userIds"])
            return _Resp({"data": [{"id": i, "hasVerifiedBadge": i % 2 == 0} for i in json["userIds"]]})
    assert verified_ids(S(), list(range(1, 151))) == set(range(2, 151, 2))
    assert [len(c) for c in calls] == [100, 50]
