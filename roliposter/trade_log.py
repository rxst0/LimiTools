"""Trade tracker: a log of your completed trades, with what you gave and got and their value at the time.

Filled from the Trades tab's Completed list (with "Read my trades directly"). Values are Rolimons values when
the trade was logged: the first time the app saw it, which for older trades can be later than the trade.
"""
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

MAX_ENTRIES = 2000


@dataclass
class LoggedTrade:
    id: int
    time: float
    partner: str
    give: list[int] = field(default_factory=list)
    get: list[int] = field(default_factory=list)
    give_value: int = 0
    get_value: int = 0

    @property
    def gain(self) -> int:
        return self.get_value - self.give_value


@dataclass
class LogTotals:
    trades: int
    wins: int
    losses: int
    net: int
    given: int
    received: int


class TradeLog:
    def __init__(self, path: Path):
        self.path = path
        self.trades: dict[int, LoggedTrade] = {}
        try:
            for row in json.loads(path.read_text(encoding="utf-8")).get("trades", []):
                t = LoggedTrade(**row)
                self.trades[t.id] = t
        except (OSError, ValueError, TypeError):
            pass

    def add(self, trade_id: int, when: float, partner: str, give: list[int], get: list[int],
            give_value: int, get_value: int) -> bool:
        """Logs a completed trade once (the first sighting keeps its values). True if it's new."""
        if trade_id in self.trades:
            return False
        self.trades[trade_id] = LoggedTrade(trade_id, when, partner, list(give), list(get), give_value, get_value)
        if len(self.trades) > MAX_ENTRIES:
            for old in sorted(self.trades.values(), key=lambda t: t.time)[:len(self.trades) - MAX_ENTRIES]:
                del self.trades[old.id]
        return True

    def add_details(self, summary, details) -> bool:
        """From roliposter.roblox_trades: a TradeSummary and its TradeDetails."""
        return self.add(summary.id, summary.created or 0.0, summary.partner_name,
                        [i.asset_id for i in details.give.items], [i.asset_id for i in details.get.items],
                        details.give_value, details.get_value)

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"trades": [asdict(t) for t in self.trades.values()]}), encoding="utf-8")
        tmp.replace(self.path)

    def newest_first(self) -> list[LoggedTrade]:
        return sorted(self.trades.values(), key=lambda t: -t.time)

    def totals(self) -> LogTotals:
        trades = list(self.trades.values())
        return LogTotals(trades=len(trades), wins=sum(t.gain > 0 for t in trades),
                         losses=sum(t.gain < 0 for t in trades), net=sum(t.gain for t in trades),
                         given=sum(t.give_value for t in trades), received=sum(t.get_value for t in trades))
