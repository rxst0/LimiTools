"""Android foreground service: keeps posting while the app is closed or the screen is off.

It also runs the background checks, and keeps running for them while posting is off:
- with "Read my trades directly": new / accepted trades, auto-accept and notable-account alerts
  (org.roliposter.TradeWatcher);
- new limited alerts and watchlist deals (public data, no sign-in): market_loop below.
"""
import json
import threading
import time

import droid
import runner
from jnius import autoclass, cast  # type: ignore

PythonService = autoclass("org.kivy.android.PythonService")
Context = autoclass("android.content.Context")
PowerManager = autoclass("android.os.PowerManager")
CHECK_SECONDS = 3
LIMITEDS_EVERY = 5 * 60
DEALS_EVERY = 10 * 60
CATALOG_EVERY = 30 * 60
DEAL_REPEAT = 24 * 3600  # the same deal notifies again after a day
SEEN_FILE = "market_seen.json"
MAX_ALERTS_PER_CHECK = 3


def load_cfg():
    from roliposter.config import load_config
    from roliposter.paths import config_path
    try:
        return load_config(config_path())
    except Exception:
        return None


def trades_wanted(cfg) -> bool:
    return bool(cfg) and droid.trade_watch_wanted(cfg)


def market_wanted(cfg) -> bool:
    return bool(cfg) and droid.market_watch_wanted(cfg)


def main() -> None:
    service = PythonService.mService
    droid.prime_java()  # the background threads below use the app's Java classes
    home = droid.data_home()
    cfg = load_cfg()
    if not runner.wants_running(home) and not trades_wanted(cfg) and not market_wanted(cfg):
        # Android restarted a sticky service the user had already stopped.
        service.setAutoRestartService(False)
        service.stopSelf()
        return
    service.setAutoRestartService(True)
    # A partial wake lock keeps timers on schedule while the screen is off (the CPU otherwise sleeps).
    power = cast("android.os.PowerManager", service.getSystemService(Context.POWER_SERVICE))
    wake = power.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "LimiTools::posting")
    wake.acquire()
    done = threading.Event()

    def heartbeat():
        """Tells the app the service is running, and follows the trade-check setting (also mid-posting)."""
        shown = None
        while not done.is_set():
            runner.mark_service_alive(home)
            now_cfg = load_cfg()
            watching = trades_wanted(now_cfg)
            droid.start_trade_watcher(watching)
            if runner.wants_running(home):
                text = droid.POSTING_TEXT + (" and checking for new trades" if watching else "")
            elif watching:
                text = droid.WATCHING_TEXT
            else:
                text = droid.MARKET_TEXT
            if text != shown:
                droid.set_service_text(text)
                shown = text
            done.wait(CHECK_SECONDS)

    threads = [threading.Thread(target=heartbeat, daemon=True),
               threading.Thread(target=market_loop, args=(home, done), daemon=True)]
    for t in threads:
        t.start()

    try:
        while True:
            if runner.wants_running(home):
                runner.run(home, on_event=notify_event)
                runner.set_want_running(home, False)
                continue
            now_cfg = load_cfg()
            if not trades_wanted(now_cfg) and not market_wanted(now_cfg):
                break
            time.sleep(CHECK_SECONDS)
    finally:
        done.set()
        for t in threads:
            t.join(timeout=10)
        droid.start_trade_watcher(False)
        runner.mark_service_alive(home, False)
        if wake.isHeld():
            wake.release()
    service.setAutoRestartService(False)
    service.stopSelf()


def market_loop(home, done: threading.Event) -> None:
    """New limited alerts (every 5 min) and watchlist deals (every 10 min). Public data, no sign-in."""
    import requests

    from roliposter import market
    from roliposter.items import fetch_catalog
    from roliposter.portfolio import fetch_best_prices

    seen_path = home / SEEN_FILE
    try:
        seen = market.Seen(json.loads(seen_path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        seen = market.Seen()
    session = requests.Session()
    catalog, catalog_at, limiteds_at, deals_at = None, 0.0, 0.0, 0.0
    while not done.is_set():
        cfg = load_cfg()
        now = time.time()
        if cfg and cfg.app.notifications:
            mk = cfg.market
            try:
                if mk.new_limited_alerts and now - limiteds_at >= LIMITEDS_EVERY:
                    limiteds_at = now
                    first = seen.first_time("limiteds")  # the first check only remembers what's there
                    sent = 0
                    for item in market.fetch_new_limiteds(session):
                        if not seen.is_new("limiteds", str(item.id)) or first:
                            continue
                        if market.wanted_limited(item, mk.verified_only, mk.max_price, mk.max_copies) \
                                and sent < MAX_ALERTS_PER_CHECK:
                            title, text = market.limited_alert(item)
                            droid.notify_url(title, text, item.url, 6000 + item.id % 100000)
                            sent += 1
                if mk.watch_alerts and mk.watchlist and now - deals_at >= DEALS_EVERY:
                    deals_at = now
                    if catalog is None or now - catalog_at >= CATALOG_EVERY:
                        catalog, catalog_at = fetch_catalog(session), now
                    deals = market.watchlist_deals(mk.watchlist, catalog, fetch_best_prices(session))
                    for deal in deals[:MAX_ALERTS_PER_CHECK]:
                        if seen.is_new("deals", f"{deal.item_id}:{deal.price}", ttl=DEAL_REPEAT):
                            title, text = market.deal_alert(deal)
                            droid.notify_url(title, text, f"https://www.roblox.com/catalog/{deal.item_id}",
                                             7000 + deal.item_id % 100000)
                seen_path.write_text(json.dumps(seen.data), encoding="utf-8")
            except Exception as e:  # network trouble etc.: try again next round
                droid.log.debug("Market check failed: %s", e)
        done.wait(30)


def notify_event(event: dict) -> None:
    """Pauses, resumes and stops become a phone notification (they share one slot, so 'resumed'
    replaces 'paused'). Tapping it opens the History tab."""
    from roliposter import events as ev
    from roliposter.config import load_config
    from roliposter.paths import config_path
    info = ev.describe(event)
    if not info.notify:
        return
    try:
        if not load_config(config_path()).app.notifications:
            return
    except Exception:
        pass
    body = " ".join(part for part in (info.body, info.action) if part)
    droid.notify(info.title, body, notification_id=droid.POSTING_NOTIFICATION_ID,
                 channel=droid.CHANNEL_POSTING, tab="history")


main()
