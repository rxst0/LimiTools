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
