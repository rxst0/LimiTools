import time

from roliposter.inventory import Inventory
from roliposter.item_intel import parse_item_page
from roliposter.items import parse_item_details
from roliposter.trade_log import TradeLog
from roliposter.trade_planner import plan_downgrade, plan_upgrade

# [name, acronym, rap, value, default_value, demand, trend, projected, hyped, rare]
CATALOG = parse_item_details({"success": True, "items": {
    "1": ["Target", "T", 10000, 10000, 10000, 3, 2, -1, -1, -1],
    "2": ["Big", "B", 6000, 6000, 6000, 3, 2, -1, -1, -1],
    "3": ["Mid", "M", 4000, 4000, 4000, 2, 2, -1, -1, -1],
    "4": ["Small", "S", 1000, 1000, 1000, 1, 2, -1, -1, -1],
    "5": ["Projected", "P", 5000, 5000, 5000, 3, 2, 1, -1, -1],
    "6": ["Held", "H", 5000, 5000, 5000, 3, 2, -1, -1, -1],
    "7": ["In demand", "D", 5500, 5500, 5500, 4, 3, -1, -1, -1],
    "8": ["Low demand", "L", 5500, 5500, 5500, 0, 2, -1, -1, -1],
}})


def test_upgrade_finds_a_fair_offer_and_skips_projected_and_held():
    inv = Inventory(counts={2: 1, 3: 2, 4: 3, 5: 1, 6: 1}, on_hold={6: 1})
    best = plan_upgrade([1], inv, CATALOG, overpay=10)[0]
    assert best.get == [1] and best.give_value == 11000            # 6000 + 4000 + 1000 = 110%
    assert round(best.overpay) == 10
    assert not {5, 6} & set(best.give)                              # projected / on hold never offered
    assert len(best.give) <= 4


def test_upgrade_can_use_two_copies_and_keeps_your_picks():
    inv = Inventory(counts={3: 2, 4: 4})
    best = plan_upgrade([1], inv, CATALOG, overpay=0, keep_give=[3])[0]
    assert best.give[0] == 3 and sorted(best.give) == [3, 3, 4, 4] and best.give_value == 10000


def test_downgrade_asks_for_in_demand_items():
    best = plan_downgrade([1], CATALOG, ask=10)[0]
    assert best.give == [1] and best.get_value >= 10000
    assert 8 not in best.get and 5 not in best.get                  # low demand / projected never asked for
    assert best.overpay < 0                                         # you receive more than you give


def test_trade_log_totals_and_no_duplicates(tmp_path):
    log = TradeLog(tmp_path / "log.json")
    assert log.add(1, 100, "a", [2], [1], 6000, 10000)
    assert log.add(2, 200, "b", [1], [3], 10000, 4000)
    assert not log.add(1, 999, "a", [], [], 0, 0)                   # logged once, first values kept
    log.save()
    again = TradeLog(tmp_path / "log.json")
    t = again.totals()
    assert (t.trades, t.wins, t.losses, t.net) == (2, 1, 1, 4000 - 6000)
    assert [x.id for x in again.newest_first()] == [2, 1]


def test_item_page_intel():
    page = """<script>
var history_data = {"num_points": 3, "timestamp": [100, 200, 300], "rap": [10, 20, 30], "best_price": [11, 21, 31]};
var sales_data = {"timestamp": [%d, %d], "avg_daily_sales_price": [100, 200], "sales_volume": [1, 3]};
var value_changes = [[50, 0, null, "ACR"], [60, 1, null, 1000], [70, 2, null, "4"], [80, 1, null, 1200]];
var ownership_data = {"owners": [5, 6], "copies": [9, 10], "hoarded_copies": [1, 2], "deleted_copies": [0, 1]};
var hoards_data = {"owner_ids": ["7", "8"], "owner_names": ["x", "y"], "quantities": [2, 5]};
var all_copies_data = {"owner_ids": [7, 9, 7], "owner_names": ["x", "z", "x"], "quantities": [1, 1, 1], "updated": [1000, 3000, 5000]};
</script>""" % (time.time() - 5 * 86400, time.time() - 86400)
    intel = parse_item_page(42, page)
    assert intel.rap.values == [10, 20, 30] and intel.best_price.values[-1] == 31
    assert intel.value_changes == [(60.0, 1000), (80.0, 1200)]
    assert (intel.owners, intel.copies, intel.hoarded, intel.deleted) == (6, 10, 2, 1)
    assert [(o.name, o.copies) for o in intel.hoarders] == [("y", 5), ("x", 2)]
    assert [o.name for o in intel.recent_owners] == ["x", "z"]       # x's newest copy (5s) beats z (3s)
    assert intel.sales_summary(30) == (4, 175)                        # (1*100 + 3*200) / 4
