"""LimiTools - Android app (Kivy). Also runs on a PC for previewing: python android/main.py"""
import copy
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if not (HERE / "roliposter").exists():
    sys.path.insert(0, str(HERE.parent))  # desktop preview: use the repo's roliposter package

import droid  # noqa: E402

HOME = droid.data_home()
HOME.mkdir(parents=True, exist_ok=True)
os.environ["ROLIPOSTER_HOME"] = str(HOME)

import requests  # noqa: E402
from kivy.app import App  # noqa: E402
from kivy.clock import Clock, mainthread  # noqa: E402
from kivy.core.window import Window  # noqa: E402
from kivy.factory import Factory  # noqa: E402
from kivy.graphics import Color, Ellipse, Line, Rectangle  # noqa: E402
from kivy.lang import Builder  # noqa: E402
from kivy.metrics import dp, sp  # noqa: E402
from kivy.properties import BooleanProperty, ColorProperty, ListProperty, NumericProperty, StringProperty  # noqa: E402
from kivy.uix.behaviors import ButtonBehavior  # noqa: E402
from kivy.uix.boxlayout import BoxLayout  # noqa: E402
from kivy.uix.label import Label  # noqa: E402
from kivy.uix.modalview import ModalView  # noqa: E402
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition  # noqa: E402
from kivy.uix.widget import Widget  # noqa: E402
from kivy.utils import get_color_from_hex  # noqa: E402

import runner  # noqa: E402
from roliposter import __version__  # noqa: E402
from roliposter import events as ev  # noqa: E402
from roliposter import palette as P  # noqa: E402
from roliposter.config import (CHECK_SPEEDS, MAX_OFFER_ITEMS, MAX_REQUEST_SLOTS, MAX_TRACKED, OPTIONAL_TABS,  # noqa: E402
                               VALID_TAGS, Ad, Config,
                               ConfigError, load_config, save_config, validate_config)
from roliposter.cookie import (COOKIE_ENV_VAR, clean_cookie, cookie_info, get_cookie,  # noqa: E402
                               load_env_file, looks_like_cookie, save_env_value)
from roliposter.inventory import fetch_inventory, missing_offer_items  # noqa: E402
from roliposter.items import ItemCatalog, fetch_catalog  # noqa: E402
from roliposter.logsetup import REDACTOR, setup_logging  # noqa: E402
from roliposter.paths import cache_dir, config_path, env_path, log_dir, state_path  # noqa: E402
from roliposter.poster import fmt_duration  # noqa: E402
from roliposter.roblox_trades import (KINDS, KIND_LABELS, ago, parse_details, parse_list, sort_trades,  # noqa: E402
                                      verdict)
from roliposter.portfolio import (RANGES, PriceLog, fetch_best_prices, fetch_history,  # noqa: E402
                                  realistic_price, totals)
from roliposter.ai_advisor import PROVIDERS, Advice, AdvisorError, ask, build_context, check  # noqa: E402
from roliposter.item_intel import fetch_item_intel  # noqa: E402
from roliposter.trade_log import TradeLog  # noqa: E402
from roliposter.trade_planner import plan_downgrade, plan_upgrade  # noqa: E402
from roliposter.market import (active_traders, describe_ad, fetch_leaderboard, fetch_recent_ads,  # noqa: E402
                               lookup_user_id, lookup_username, verified_ids)
from roliposter.backup import (BackupError, apply_backup, backup_filename, make_backup,  # noqa: E402
                               merge_price_history, parse_backup, save_safety_copy, summary)
from roliposter.state import PostHistory  # noqa: E402
from roliposter.thumbs import ThumbnailCache  # noqa: E402
from roliposter.updates import check_for_update  # noqa: E402
from roliposter.trades_viewer import TRADE_POLL_JS, TRADES_URL, VIEW_ONLY_JS  # noqa: E402
from roliposter.values import evaluate_ad  # noqa: E402

log = logging.getLogger("roliposter.app")
COOKIE_WARN_DAYS = 3
HELP_TEXT = """[b]Getting started[/b]

[b]1. Sign in to Rolimons[/b]
Tap "Sign in to Rolimons" on the Ads tab, then log in and verify like on the website. The app picks up your Rolimons cookie by itself. (On a PC you can also copy the _RoliVerification cookie and use "Paste cookie".)

[b]2. Make ads[/b]
Tap "+ New ad", search items by name, tap Offer or Want, pick tags, and save. Ads offering items you no longer own are skipped automatically.

[b]3. Start posting[/b]
Tap "Start posting". One ad goes out about every 15 minutes (Rolimons' cooldown) with a small random delay. A notification stays while it posts, even with the screen off. In Settings, tap "Allow running in the background" so Android doesn't pause it.

[b]Trades[/b]
The Trades tab shows Roblox's trades page. Sign in to Roblox there the first time. It is view-only: accepting, declining, countering and sending are blocked inside the app. Respond on roblox.com or in the Roblox app. Settings > "Sign out of Roblox" signs you out.

[b]Items[/b]
The Items tab shows the limiteds in your Rolimons inventory, their total value and RAP (robux), and a chart of your value over the last day, month, 6 months or year (from your Rolimons player page). When you make an ad, "Add item you offer" lists only items you own.

[b]Read my trades directly (optional)[/b]
Turn this on in Settings to see your trades as a list in the app (received, sent, completed, inactive) with item pictures and Rolimons values, sorted newest first or by best or worst deal, and to get alerts for new and accepted trades even when the app is closed. To do this, the app keeps an encrypted copy of your Roblox sign-in (.ROBLOSECURITY) on this phone and uses it only to read your trades. It's never sent anywhere except Roblox. It can't be used to decline or send trades, and it only accepts trades if you turn on live auto-accept. Turning the option off deletes the copy.

[b]Market[/b]
Items: search any limited, open it for its value, RAP, demand, trend and current price, and tap Watch to get an alert when someone lists it under value. Players: look up any username to see their value, chart and items. The Richest, Traders and Verified lists help you find people; Track someone to get alerts when they post a trade ad or their value changes. Following or friending them is up to you, on their profile.

[b]New limited alerts (optional)[/b]
Settings > New limiteds and watchlist notifies you about new limiteds in the Roblox catalog, with the price, copies and description. Use the filters (verified creators, max price, max copies): new UGC limiteds come out many times a day. No Roblox sign-in needed.

[b]Backup and restore[/b]
Settings > Backup and restore saves your ads, settings and watchlist to a file, or restores one (also one made in the Windows app). Your Rolimons cookie, Roblox sign-in and AI key are never in backups. Your current setup is saved before restoring, so you can undo it.

[b]Battery[/b]
Settings > Background checks: Fast (every 2 minutes), Normal (5) or Battery saver (15).

[b]Tabs[/b]
Settings > Tabs turns off tabs you don't use. Ads and Settings always stay.

[b]Notable followers and friend requests (optional)[/b]
Settings > Notable followers and friend requests notifies you when a verified account, or one with at least your minimum number of followers, sends you a friend request or follows you. It needs "Read my trades directly". Tap the alert to open their Roblox profile.

[b]AI recommendations (optional)[/b]
Turn on Settings > AI trade recommendations, pick Claude or ChatGPT and paste your own API key from that company. Tap Open AI recommendations, then Get recommendations: the AI looks at your items and the Rolimons market (value, RAP, demand, trend, projected/hyped/rare, current prices, your value history) and suggests upgrades, downgrades and items to hold. It only runs when you tap the button, and each run costs a few cents on your API account. Your items and market data go to the AI company; your Roblox and Rolimons sign-ins never do. Suggestions can be wrong: check every trade yourself.

[b]Auto-accept (optional)[/b]
The Auto tab checks each new received trade against your rules: minimum value, RAP and price gain, and no projected items. Test mode (the default) only tells you what it would accept. Live accepts on Roblox, up to your daily limit. Accepted trades can't be undone, and Roblox's rules don't allow automating your account, so watch test mode first.

[b]Notifications[/b]
You get a notification when posting pauses (daily ad limit, outside your posting hours, no internet), when it resumes, and if it stops. Tap it to see why in History. Once you're signed in to Roblox in the Trades tab, you also get "New trade from ..." when someone sends you a trade (Settings > "Notify me about new Roblox trades"). Without "Read my trades directly", Android only checks while the app is open or recently used. With it, the app checks every couple of minutes in the background (status bar: "Checking for new Roblox trades"), and also tells you "... accepted your trade" when someone accepts a trade you sent. New-trade alerts show what you would give and get, and the % gain or loss. Tap it to see the trade in Completed.

[b]History[/b]
Every post, pause and problem in plain English. Use Problems to see only what went wrong, and tap an entry to see what to do about it.

[b]Safety[/b]
This app never asks you to type or paste your Roblox password or .ROBLOSECURITY cookie. Anyone who asks you to paste those is trying to steal your account. Your Roblox sign-in is only read if you turn on "Read my trades directly", and then only to read your trades.

Run posting on one device at a time: two devices posting for the same account hit each other's cooldown.

[b]About[/b]
LimiTools (formerly Rolimons Ad Poster) is unofficial: it isn't made by, affiliated with or endorsed by Rolimons or Roblox.
"""
ALL_TABS = ("home", "trades", "items", "market", "auto", "history", "settings")
TAB_LABELS = {"home": "Ads", "trades": "Trades", "items": "Items", "market": "Market", "auto": "Auto",
              "history": "History", "settings": "Settings"}
LIVE_AUTO_ACCEPT_TEXT = ("The app will accept new received trades on Roblox, by itself, when they pass every rule "
                         "you set. Accepted trades can't be undone.\n\n"
                         "- Scammers inflate RAP and prices; the value rule and blocking projected items protect "
                         "you best.\n- Roblox's rules don't allow automating your account; use this at your own "
                         "risk.\n- If Roblox asks for 2-step verification, the trade is skipped and you get a "
                         "notification.")
DIRECT_TRADES_TEXT = ("Your trades now show as a list in the Trades tab, and new-trade alerts work with the app "
                      "closed.\n\nThe app keeps an encrypted copy of your Roblox sign-in on this phone and uses it "
                      "only to read your trades. Turn this off any time to delete the copy.\n\n"
                      "If you aren't signed in to Roblox yet, open the Trades tab and sign in there.")


def asset(relative: str) -> Path:
    """Shared assets: copied next to main.py in the APK, or the repo's assets/ in the desktop preview."""
    bundled = HERE / relative
    return bundled if bundled.exists() else HERE.parent / relative


def register_fonts() -> None:
    """Makes Inter (the PC app's font too) the default for every label."""
    from kivy.core.text import LabelBase
    regular, bold = asset(P.FONT_FILES["regular"]), asset(P.FONT_FILES["bold"])
    if regular.exists() and bold.exists():
        LabelBase.register(name="Roboto", fn_regular=str(regular), fn_bold=str(bold))


# ---- widgets -------------------------------------------------------------------
class FlatButton(ButtonBehavior, Label):
    bg = ColorProperty()
    bg_down = ColorProperty()


class Chip(ButtonBehavior, Label):
    selected = BooleanProperty(False)


class Switchy(ButtonBehavior, Widget):
    active = BooleanProperty(False)

    def on_release(self):
        self.active = not self.active


class SettingRow(BoxLayout):
    text = StringProperty("")
    active = BooleanProperty(False)


class ItemRow(BoxLayout):
    thumb = StringProperty("")
    name = StringProperty("")
    value = StringProperty("")
    warn = BooleanProperty(False)

    def add_action(self, text: str, callback, accent: bool = False) -> None:
        btn = FlatButton(text=text, size_hint=(None, None), size=(max(56, len(text) * 11 + 28), 40),
                         font_size="14sp")
        if accent:
            btn.bg, btn.bg_down = get_color_from_hex(P.ACCENT), get_color_from_hex(P.ACCENT_PRESSED)
        btn.bind(on_release=lambda *_: callback())
        self.ids.actions.add_widget(btn)


class AdCard(ButtonBehavior, BoxLayout):
    title = StringProperty("")
    summary = StringProperty("")
    badge = StringProperty("")
    active = BooleanProperty(True)
    warned = BooleanProperty(False)

    def __init__(self, **kw):
        self.register_event_type("on_toggle")
        super().__init__(**kw)

    def on_toggle(self, value):
        pass


class Notice(ModalView):
    title = StringProperty("")
    message = StringProperty("")

    def __init__(self, title: str, message: str, buttons=(("OK", None),), **kw):
        super().__init__(title=title, message=message, **kw)
        for i, (text, callback) in enumerate(buttons):
            btn = FlatButton(text=text)
            if i == len(buttons) - 1:
                btn.bg, btn.bg_down = get_color_from_hex(P.ACCENT), get_color_from_hex(P.ACCENT_PRESSED)
                btn.color = (1, 1, 1, 1)

            def press(*_, cb=callback):
                self.dismiss()
                if cb:
                    cb()
            btn.bind(on_release=press)
            self.ids.buttons.add_widget(btn)


# ---- screens -------------------------------------------------------------------
class HomeScreen(Screen):
    pass


class NavButton(ButtonBehavior, Label):
    tab = StringProperty("")


LIST_ERRORS = {
    0: "Sign in to Roblox on the Roblox page first.",
    401: "Roblox signed you out. Sign in again on the Roblox page.",
    429: "Roblox is busy. Tap Reload in a minute.",
    -1: "Couldn't reach Roblox. Check your internet connection.",
}


class TradeCard(ButtonBehavior, BoxLayout):
    """One trade in the app's own trades list: who with, item pictures on each side, and values."""
    partner = StringProperty("")
    when = StringProperty("")
    summary = StringProperty("Loading items...")
    tone = StringProperty("loading")
    note = StringProperty("")

    def __init__(self, trade, **kw):
        super().__init__(partner=trade.partner_name, when=ago(trade.created), **kw)
        self.trade = trade
        self.details = None

    def show(self, details) -> None:
        app = App.get_running_app()
        self.details = details
        self.tone, self.summary = verdict(details)
        self.note = "Projected item in what you get" if details.has_projected else ""
        for box, side in ((self.ids.give_box, details.give), (self.ids.get_box, details.get)):
            box.clear_widgets()
            for item in side.items:
                box.add_widget(Factory.TradeThumb(source=app.thumb_source(item.asset_id)))
            if side.robux:
                box.add_widget(Factory.Muted(text=f"+R$ {side.robux:,}", size_hint_x=None, width=dp(80),
                                             height=dp(34)))
            if not side.items and not side.robux:
                box.add_widget(Factory.Muted(text="Nothing", height=dp(34)))


class TradesScreen(Screen):
    """Roblox's trades page (WebView), or with "Read my trades directly" the app's own list."""
    placeholder = StringProperty("Loading Roblox..." if droid.TradesView.available else
                                 "The Received trades tab works in the Android app.\n\n"
                                 "It shows Roblox's own trades page, view-only.")
    direct = BooleanProperty(False)   # option on and signed in: the list is available
    page = BooleanProperty(False)     # showing the Roblox page instead of the list
    kind = StringProperty("inbound")
    sort = StringProperty("newest")   # newest / best / worst (see roblox_trades.sort_trades)
    status_text = StringProperty("")
    more = BooleanProperty(False)

    def __init__(self, **kw):
        super().__init__(**kw)
        self._token = None
        self._cursor = ""
        self._loaded_at = 0.0
        self._cards: list = []  # TradeCards in Roblox's order (newest first)
        self._raw_details: dict[int, str] = {}  # trade ID -> Roblox's reply (details never change)

    @property
    def native(self) -> bool:
        return self.direct and not self.page

    def on_enter(self):
        Clock.schedule_once(lambda *_: self.apply_view(), 0)

    def on_pre_leave(self):
        App.get_running_app().hide_trades_view()

    def apply_view(self):
        """Shows the WebView or the list, loading the list if it's old."""
        app = App.get_running_app()
        if self.manager is None or self.manager.current != "trades":
            return
        if self.native:
            app.hide_trades_view()
            if time.time() - self._loaded_at > 60:
                self.load()
        else:
            if app.cfg.app.direct_trades:
                droid.RobloxDirect.capture()  # hands the page any cookie Roblox rotated in the background
            app.show_trades_view()

    def first_button(self):
        if self.direct:
            self.page = not self.page
            self.apply_view()
        elif App.get_running_app().trades_view:
            App.get_running_app().trades_view.go_home()

    def reload(self):
        if self.native:
            self.load()
        elif App.get_running_app().trades_view:
            App.get_running_app().trades_view.reload()

    def set_kind(self, kind: str):
        if kind in KINDS:
            self.kind = kind
            self.load()

    def set_sort(self, how: str):
        self.sort = how
        self.resort()
        self.ids.trades_scroll.scroll_y = 1

    def resort(self):
        """Puts the cards in the chosen order; trades still loading their items stay at the end."""
        box = self.ids.trades_box
        ordered = sort_trades([(c, c.details) for c in self._cards], self.sort)
        box.clear_widgets()
        for card, _details in ordered:
            box.add_widget(card)

    def load(self, more: bool = False):
        token = object()
        self._token = token
        self._loaded_at = time.time()
        if not more:
            self._cursor = ""
            self._cards = []
            self.ids.trades_box.clear_widgets()
            self.ids.trades_scroll.scroll_y = 1
        self.status_text = "Loading..."
        self.more = False
        threading.Thread(target=self._fetch, args=(token, self.kind, self._cursor), daemon=True).start()

    def _fetch(self, token, kind: str, cursor: str):
        try:
            self._fetch_all(token, kind, cursor)
        except Exception as e:  # never leave the list stuck on "Loading..."
            log.exception("Loading trades failed")
            self._failed(token, -4, f"{type(e).__name__}: {e}"[:200])

    def _fetch_all(self, token, kind: str, cursor: str):
        status, body = droid.RobloxDirect.fetch("list", kind, cursor)
        if status != 200:
            return self._failed(token, status)
        try:
            trades, next_cursor = parse_list(body)
        except (ValueError, AttributeError, TypeError):
            return self._failed(token, -3)
        self._listed(token, trades, next_cursor)
        for trade in trades:
            if self._token is not token:
                return
            raw = self._raw_details.get(trade.id)
            if raw is None:
                status, raw = droid.RobloxDirect.fetch("trade", str(trade.id))
                if status == 429:  # Roblox limits how fast trades can be read
                    time.sleep(6)
                    status, raw = droid.RobloxDirect.fetch("trade", str(trade.id))
                if status != 200:
                    self._no_details(token, trade.id)
                    continue
                self._raw_details[trade.id] = raw
            try:
                details = parse_details(raw, trade.partner_id, App.get_running_app().catalog)
            except (ValueError, AttributeError, TypeError):
                self._no_details(token, trade.id)
                continue
            self._detailed(token, trade.id, details)

    @mainthread
    def _failed(self, token, status: int, detail: str = ""):
        if self._token is not token:
            return
        if detail:
            self.status_text = f"Couldn't load your trades. Tap Reload to try again.\n\n({detail})"
        else:
            self.status_text = LIST_ERRORS.get(status, f"Roblox replied with an error ({status}). "
                                                       "Tap Reload to try again.")
        self._loaded_at = 0.0
        if status in (0, 401):
            droid.RobloxDirect.clear()  # shows the Roblox page to sign in again
            App.get_running_app().sync_direct_trades()

    @mainthread
    def _listed(self, token, trades, next_cursor: str):
        if self._token is not token:
            return
        box = self.ids.trades_box
        for trade in trades:
            card = TradeCard(trade)
            card.bind(on_release=lambda c: self.open(c))
            self._cards.append(card)
            box.add_widget(card)
        self._cursor = next_cursor
        self.more = bool(next_cursor)
        self.status_text = "" if box.children else f"No {KIND_LABELS[self.kind].lower()} trades."

    def _card(self, trade_id: int):
        return next((c for c in self._cards if c.trade.id == trade_id), None)

    @mainthread
    def _detailed(self, token, trade_id: int, details):
        card = self._card(trade_id) if self._token is token else None
        if card:
            card.show(details)
            if self.kind == "completed" and App.get_running_app().trade_log.add_details(card.trade, details):
                App.get_running_app().trade_log.save()
            if self.sort != "newest":
                self.resort()
            App.get_running_app().request_thumbs([i.asset_id for i in details.give.items + details.get.items])

    @mainthread
    def _no_details(self, token, trade_id: int):
        card = self._card(trade_id) if self._token is token else None
        if card:
            card.summary, card.tone = "Couldn't load the items. Tap Reload to try again.", "loading"

    def refresh_thumbs(self):
        for card in self._cards:
            if card.details:
                card.show(card.details)

    def open(self, card):
        if card.details is None:
            return
        app = App.get_running_app()
        app.sm.get_screen("trade").load(card.trade, card.details)
        app.show("trade")


class TradeScreen(Screen):
    """One trade from the app's trades list: every item on both sides, with values. View only."""
    title = StringProperty("Trade")
    summary = StringProperty("")
    tone = StringProperty("even")
    note = StringProperty("")

    def load(self, trade, details):
        self.trade, self.details = trade, details
        self.title = f"Trade with {trade.partner_name}"
        self.refresh()
        self.ids.scroll.scroll_y = 1

    def refresh(self):
        app = App.get_running_app()
        details = self.details
        self.tone, self.summary = verdict(details)
        when = ago(self.trade.created)
        kind = KIND_LABELS.get(app.sm.get_screen("trades").kind, "")
        self.note = f"{kind} trade, created {when}." if when else f"{kind} trade."
        for box, side, robux_note in ((self.ids.give_box, details.give, ""),
                                      (self.ids.get_box, details.get, "  (you get 70% after Roblox's fee)")):
            box.clear_widgets()
            for item in side.items:
                box.add_widget(app.trade_item_row(item))
            if side.robux:
                box.add_widget(Factory.Txt(text=f"R$ {side.robux:,}{robux_note}"))
            if not side.items and not side.robux:
                box.add_widget(Factory.Muted(text="Nothing"))

    def open_roblox(self):
        droid.open_url("https://www.roblox.com/trades")


class HelpScreen(Screen):
    text = StringProperty(HELP_TEXT)


class CookieScreen(Screen):
    def on_pre_enter(self):
        self.ids.cookie.text = ""

    def save(self):
        app = App.get_running_app()
        if app.save_cookie(self.ids.cookie.text):
            app.go_back()


SEVERITY_COLORS = {ev.OK: P.OK, ev.INFO: P.ACCENT, ev.WARN: P.WARN, ev.ERROR: P.BAD}


class EventRow(ButtonBehavior, BoxLayout):
    """One History entry: coloured marker, plain-English title, time and a short explanation."""
    title = StringProperty("")
    subtitle = StringProperty("")
    marker = ColorProperty()


class HistoryScreen(Screen):
    """Plain-English history (see roliposter/events.py). Tap an entry for what to do and the raw reply."""
    filter = StringProperty("all")
    show_log = BooleanProperty(False)

    def on_pre_enter(self):
        self.refresh()

    def set_filter(self, flt: str):
        self.filter = flt
        self.refresh()

    def refresh(self):
        app = App.get_running_app()
        history = PostHistory(state_path())
        timeline = history.timeline()
        self.ids.summary.text = ev.summary(timeline, history.count_24h(), app.cfg.max_ads_per_24h)
        for key, _label in ev.FILTERS:
            self.ids[f"filter_{key}"].selected = key == self.filter
        box = self.ids.events
        box.clear_widgets()
        groups = ev.grouped(timeline, self.filter)
        if not groups:
            box.add_widget(Factory.Muted(text={"posted": "No ads posted yet.",
                                               "problems": "No problems. Everything is working."}
                                         .get(self.filter, "Nothing here yet. Start posting on the Ads tab.")))
        for day, entries in groups:
            box.add_widget(Factory.FieldLabel(text=day.upper()))
            for event, info in entries:
                row = EventRow(title=info.title, subtitle=f"{ev.time_label(event['t'])}  ·  {info.body}",
                               marker=get_color_from_hex(SEVERITY_COLORS.get(info.severity, P.MUTED)))
                row.bind(on_release=lambda _r, e=event, i=info: app.notice(i.title, ev.details(e, i)))
                box.add_widget(row)
        self.load_log()

    def toggle_log(self):
        self.show_log = not self.show_log
        self.load_log()

    def load_log(self):
        if not self.show_log:
            self.ids.activity.text = ""
            return
        try:
            lines = (log_dir() / "poster.log").read_text(encoding="utf-8").splitlines()[-60:]
        except OSError:
            lines = []
        self.ids.activity.text = "\n".join(line[11:] for line in lines) or "No activity yet."


class SettingsScreen(Screen):
    battery_text = StringProperty("")
    ai_key_text = StringProperty("")

    def on_pre_enter(self):
        c = App.get_running_app().cfg
        ids = self.ids
        self.set_order(c.rotation)
        ids.jmin.text, ids.jmax.text = f"{c.jitter_seconds[0]:g}", f"{c.jitter_seconds[1]:g}"
        ids.max_ads.text = str(c.max_ads_per_24h)
        ids.skip_unowned.active = c.skip_unowned_items
        ids.hours_on.active = c.posting_hours.enabled
        ids.hstart.text, ids.hend.text = c.posting_hours.start, c.posting_hours.end
        ids.value_on.active = c.value_mode.enabled
        ids.overpay.text = f"{c.value_mode.overpay_warn_percent:g}"
        ids.skip_overpay.active = c.value_mode.skip_overpaying_ads
        ids.smart_pick.active = c.value_mode.strategy == "pick"
        ids.notify_on.active = c.app.notifications
        ids.trade_notify_on.active = c.app.trade_notifications
        ids.direct_trades.active = c.app.direct_trades
        ids.updates_on.active = c.app.check_updates
        sa = c.social_alerts
        ids.sa_on.active, ids.sa_min.text = sa.enabled, str(sa.min_followers)
        ids.sa_verified.active, ids.sa_requests.active, ids.sa_follows.active = sa.verified, sa.friend_requests, sa.follows
        ids.ai_on.active = c.ai.enabled
        self.set_ai_provider(c.ai.provider, model=c.ai.model)
        for tab in OPTIONAL_TABS:
            ids[f"tab_{tab}"].active = tab not in c.app.hidden_tabs
        self.set_speed(c.app.check_minutes)
        mk = c.market
        ids.mk_new.active, ids.mk_verified.active, ids.mk_watch.active = mk.new_limited_alerts, mk.verified_only, mk.watch_alerts
        ids.mk_max_price.text, ids.mk_max_copies.text = str(mk.max_price or ""), str(mk.max_copies or "")
        self.refresh_battery()

    # ---- AI recommendations ----------------------------------------------------------------
    def set_ai_provider(self, provider: str, model: str | None = None):
        self._ai_provider = provider if provider in PROVIDERS else "claude"
        info = PROVIDERS[self._ai_provider]
        self.ids.ai_claude.selected = self._ai_provider == "claude"
        self.ids.ai_openai.selected = self._ai_provider == "openai"
        self.ids.ai_key.text = ""
        self.ids.ai_key.hint_text = info["key_hint"]
        self.ids.ai_model.hint_text = info["model"]
        if model is not None:
            self.ids.ai_model.text = model
        saved = bool(ai_api_key(self._ai_provider))
        self.ai_key_text = (f"A {info['label']} key is saved. Leave the box empty to keep it." if saved else
                            f"Make a key at {info['key_url']} and paste it here.")

    def set_speed(self, minutes: int):
        self._speed = minutes if minutes in CHECK_SPEEDS else 2
        for option in CHECK_SPEEDS:
            self.ids[f"speed_{option}"].selected = option == self._speed

    # ---- backup and restore --------------------------------------------------------------------
    def backup(self):
        app = App.get_running_app()
        text = make_backup(app.cfg, app.price_log.points)

        def saved(ok):
            if ok:
                app.toast("Backup saved")
            elif ok is False:
                app.notice("Backup", "Couldn't save the backup there. Try another folder.")
        droid.save_document(backup_filename(), text, saved)

    def restore(self):
        app = App.get_running_app()

        def picked(text):
            if text is None:
                return  # cancelled
            try:
                restored = parse_backup(text)
            except BackupError as e:
                return app.notice("Restore", str(e))
            app.notice("Restore this backup?",
                       f"It has {summary(restored)}\n\nReplace: use everything from the backup.\n"
                       "Add: keep your settings and add the backup's ads and watched items.\n\n"
                       "Your current setup is saved first, so you can undo this.",
                       (("Cancel", None), ("Add", lambda: self._apply_restore(restored, "add")),
                        ("Replace", lambda: self._apply_restore(restored, "replace"))))
        droid.open_document(picked)

    def _apply_restore(self, restored, mode: str):
        app = App.get_running_app()
        save_safety_copy(HOME / "backups", app.cfg, app.price_log.points)
        app.cfg = apply_backup(app.cfg, restored, mode)
        app.persist()
        if restored.price_history:
            app.price_log.points = [tuple(p) for p in merge_price_history(app.price_log.points,
                                                                           restored.price_history)]
            app.price_log.save()
        app.apply_trade_notifications()
        app.rebuild_nav()
        self.on_pre_enter()
        app.notice("Restored", f"{'Replaced your setup with' if mode == 'replace' else 'Added'} the backup. "
                               "Sign in to Rolimons again if you're on a new device, and re-enter your AI key "
                               "if you use one.")

    def forget_ai_key(self):
        app = App.get_running_app()
        save_env_value(env_path(), PROVIDERS[self._ai_provider]["key_env"], "")
        self.set_ai_provider(self._ai_provider)
        app.toast("API key removed")

    # ---- other ---------------------------------------------------------------------------------
    def refresh_battery(self):
        ignoring = droid.ignoring_battery_optimizations()
        self.battery_text = ("" if ignoring in (None, True) else
                             "Android may pause posting to save battery. Allow the app to run in the "
                             "background so ads keep going with the screen off.")

    def sign_out_roblox(self):
        app = App.get_running_app()
        if not droid.TradesView.available:
            return app.notice("Roblox trades", "Signing in to Roblox happens in the Android app.")
        droid.sign_out_web()
        if app.trades_view:
            app.trades_view.go_home()
        app.sync_direct_trades()
        app.notice("Signed out", "You're signed out of Roblox in this app.")

    def request_battery(self):
        droid.request_ignore_battery_optimizations()
        Clock.schedule_once(lambda *_: self.refresh_battery(), 3)

    def set_order(self, order: str):
        self._order = order
        self.ids.order_seq.selected = order == "sequential"
        self.ids.order_rand.selected = order == "random"

    def save(self):
        app = App.get_running_app()
        ids = self.ids
        try:
            jmin, jmax = float(ids.jmin.text or 0), float(ids.jmax.text or 0)
            max_ads = int(ids.max_ads.text or 0)
            overpay = float(ids.overpay.text or 0)
            sa_min = int(ids.sa_min.text or 0)
            mk_max_price, mk_max_copies = int(ids.mk_max_price.text or 0), int(ids.mk_max_copies.text or 0)
        except ValueError:
            return app.notice("Settings", "Please enter numbers only.")
        c = copy.deepcopy(app.cfg)
        c.rotation = self._order
        c.jitter_seconds = [jmin, jmax]
        c.max_ads_per_24h = max_ads
        c.skip_unowned_items = ids.skip_unowned.active
        c.posting_hours.enabled = ids.hours_on.active
        c.posting_hours.start, c.posting_hours.end = ids.hstart.text.strip(), ids.hend.text.strip()
        c.value_mode.enabled = ids.value_on.active or ids.skip_overpay.active or ids.smart_pick.active
        c.value_mode.overpay_warn_percent = overpay
        c.value_mode.skip_overpaying_ads = ids.skip_overpay.active
        c.value_mode.strategy = "pick" if ids.smart_pick.active else "warn"
        c.app.notifications = ids.notify_on.active
        c.app.trade_notifications = ids.trade_notify_on.active
        c.app.direct_trades = ids.direct_trades.active
        c.app.check_updates = ids.updates_on.active
        sa = c.social_alerts
        sa.enabled, sa.min_followers = ids.sa_on.active, sa_min
        sa.verified, sa.friend_requests, sa.follows = ids.sa_verified.active, ids.sa_requests.active, ids.sa_follows.active
        if sa.enabled and not c.app.direct_trades:
            return app.notice("Notable accounts", 'This needs "Read my trades directly" turned on (friend requests '
                                                  "are only visible to you when signed in).")
        c.app.hidden_tabs = [t for t in OPTIONAL_TABS if not ids[f"tab_{t}"].active]
        c.app.check_minutes = self._speed
        mk = c.market
        mk.new_limited_alerts, mk.verified_only, mk.watch_alerts = ids.mk_new.active, ids.mk_verified.active, ids.mk_watch.active
        mk.max_price, mk.max_copies = mk_max_price, mk_max_copies
        c.ai.enabled = ids.ai_on.active
        c.ai.provider = self._ai_provider
        c.ai.model = ids.ai_model.text.strip()
        new_key = ids.ai_key.text.strip()
        problems = [e for e in validate_config(c) if not e.startswith(("No ads", "All ads", "roblox_user_id"))
                    and not e.startswith("Ad '")]
        if problems:
            return app.notice("Check your settings", "\n".join(problems))
        if new_key:
            save_env_value(env_path(), PROVIDERS[c.ai.provider]["key_env"], new_key)
            REDACTOR.add_secret(new_key)
        turned_on = c.app.direct_trades and not app.cfg.app.direct_trades
        app.cfg = c
        app.persist()
        app.apply_trade_notifications()
        app.rebuild_nav()
        self.set_ai_provider(c.ai.provider)
        if c.market.new_limited_alerts:
            droid.request_notification_permission()
        if turned_on and droid.RobloxDirect.available:
            droid.request_notification_permission()
            app.notice("Read my trades directly", DIRECT_TRADES_TEXT)
        else:
            app.toast("Settings saved")


def ai_api_key(provider: str) -> str:
    return os.environ.get(PROVIDERS[provider]["key_env"], "").strip()


class AutoScreen(Screen):
    """Auto-accept: rules for accepting new received trades (test mode first). See org.roliposter.AutoAccept."""

    def on_pre_enter(self):
        c = App.get_running_app().cfg
        ids, aa = self.ids, c.auto_accept
        ids.aa_on.active = aa.enabled
        self.set_aa_mode(aa.mode)
        for field_id, gain in (("aa_value", aa.min_value_gain), ("aa_rap", aa.min_rap_gain),
                               ("aa_price", aa.min_price_gain)):
            ids[field_id].text = "" if gain is None else f"{gain:g}"
        ids.aa_projected.active = aa.block_projected
        ids.aa_max.text = str(aa.max_per_day)

    def set_aa_mode(self, mode: str):
        self._aa_mode = mode
        self.ids.aa_test.selected = mode == "test"
        self.ids.aa_live.selected = mode == "live"

    def show_aa_log(self):
        app = App.get_running_app()
        entries = droid.auto_accept_log()[:12]
        if not entries:
            return app.notice("Auto-accept decisions", "Nothing yet. New received trades show up here once "
                                                       "auto-accept is on.")
        lines = []
        for e in entries:
            when = time.strftime("%d %b %H:%M", time.localtime(e.get("t", 0)))
            mode = "LIVE" if e.get("live") else "test"
            pct = f" ({e['pct']})" if e.get("pct") else ""
            lines.append(f"[b]{when}  {e.get('partner', '?')}{pct}[/b]  [{mode}]\n{e.get('result', '')}")
        app.notice("Auto-accept decisions", "\n\n".join(lines))

    def save(self):
        app = App.get_running_app()
        ids = self.ids
        try:
            gains = [float(ids[f].text) if ids[f].text.strip() else None for f in ("aa_value", "aa_rap", "aa_price")]
            max_per_day = int(ids.aa_max.text or 0)
        except ValueError:
            return app.notice("Auto-accept", "Please enter numbers only.")
        c = copy.deepcopy(app.cfg)
        aa = c.auto_accept
        aa.enabled = ids.aa_on.active
        aa.mode = self._aa_mode
        aa.min_value_gain, aa.min_rap_gain, aa.min_price_gain = gains
        aa.block_projected = ids.aa_projected.active
        aa.max_per_day = max_per_day
        if aa.enabled and not c.app.direct_trades:
            return app.notice("Auto-accept", 'Auto-accept needs "Read my trades directly" (Settings) turned on.')
        problems = [e for e in validate_config(c) if "uto-accept" in e or "auto_accept" in e]
        if problems:
            return app.notice("Check your rules", "\n".join(problems))
        going_live = aa.enabled and aa.mode == "live" and not (app.cfg.auto_accept.enabled
                                                               and app.cfg.auto_accept.mode == "live")
        if going_live and not getattr(self, "_live_confirmed", False):
            def confirm():
                self._live_confirmed = True
                self.save()
            return app.notice("Turn on live auto-accept?", LIVE_AUTO_ACCEPT_TEXT, (("Cancel", None), ("Turn on", confirm)))
        self._live_confirmed = False
        app.cfg = c
        app.persist()
        app.apply_trade_notifications()
        app.toast("Auto-accept saved")


class AiScreen(Screen):
    """AI trade recommendations: upgrades, downgrades and holds for your inventory, on request."""
    status_text = StringProperty("")
    summary_text = StringProperty("")
    busy = BooleanProperty(False)

    ADVICE_FILE = "ai_advice.json"

    def on_pre_enter(self):
        app = App.get_running_app()
        app.load_portfolio()  # current prices and value history make for better advice
        if not app.cfg.ai.enabled:
            self.status_text = "AI recommendations are off. Turn them on in Settings and add your API key."
        elif not ai_api_key(app.cfg.ai.provider):
            self.status_text = f"Add your {PROVIDERS[app.cfg.ai.provider]['label']} API key in Settings."
        elif not self.busy:
            self.status_text = ""
        self.show_saved()

    def show_saved(self):
        try:
            advice = Advice.from_dict(json.loads((HOME / self.ADVICE_FILE).read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError, KeyError):
            advice = None
        self.render(advice)

    def run(self):
        app = App.get_running_app()
        ai = app.cfg.ai
        if self.busy:
            return
        if not ai.enabled:
            return app.notice("AI recommendations", "Turn them on in Settings first.")
        key = ai_api_key(ai.provider)
        if not key:
            return app.notice("AI recommendations", f"Add your {PROVIDERS[ai.provider]['label']} API key in Settings.")
        if app.catalog is None or app.inventory is None:
            return app.notice("AI recommendations", "Your items are still loading. Try again in a moment.")
        if app.inventory.private:
            return app.notice("AI recommendations", "Your Roblox inventory is private, so there's nothing to advise on.")
        self.busy = True
        label = PROVIDERS[ai.provider]["label"]
        self.status_text = f"Asking {label}... this can take a minute."
        context = build_context(app.inventory, app.catalog, app.best_prices, app.value_history)
        model = ai.model or PROVIDERS[ai.provider]["model"]
        provider, inventory, catalog = ai.provider, app.inventory, app.catalog

        def work():
            try:
                answer = ask(provider, key, context, model=model)
                advice = check(answer, inventory, catalog, provider=provider, model=model)
                (HOME / self.ADVICE_FILE).write_text(json.dumps(advice.to_dict()), encoding="utf-8")
                self._done(advice, "")
            except AdvisorError as e:
                self._done(None, str(e))
            except Exception as e:  # never leave the screen stuck on "Asking..."
                log.exception("AI recommendations failed")
                self._done(None, f"Something went wrong: {type(e).__name__}. Try again.")
        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def _done(self, advice, error: str):
        self.busy = False
        if error:
            self.status_text = error
            return
        self.status_text = ""
        self.render(advice)

    def render(self, advice):
        app = App.get_running_app()
        box = self.ids.recs
        box.clear_widgets()
        if advice is None:
            self.summary_text = ""
            return
        when = time.strftime("%d %b %H:%M", time.localtime(advice.created))
        source = PROVIDERS.get(advice.provider, {}).get("label", advice.provider)
        note = f" · {advice.dropped} unusable suggestion(s) left out" if advice.dropped else ""
        self.summary_text = (f"{advice.summary}\n\n[size={int(sp(12))}][color={P.MUTED}]{source} · {advice.model}"
                             f" · {when}{note}[/color][/size]")
        titles = {"upgrade": "Upgrade", "downgrade": "Downgrade", "hold": "Hold"}
        shown = []
        for rec in advice.recommendations:
            card = Factory.Card()
            card.add_widget(Factory.Title(text=f"{titles.get(rec.kind, rec.kind)}  [size={int(sp(13))}]"
                                               f"[color={P.MUTED}]{rec.confidence} confidence[/color][/size]"))
            sides = (("KEEP", rec.give + rec.get),) if rec.kind == "hold" else (("YOU GIVE", rec.give),
                                                                               ("YOU GET", rec.get))
            for label, item_ids in sides:
                if not item_ids:
                    continue
                card.add_widget(Factory.FieldLabel(text=label))
                for item_id in item_ids:
                    card.add_widget(app.item_row(item_id))
                shown += item_ids
            if rec.kind != "hold" and app.catalog:
                give = sum(app.catalog.get(i).default_value for i in rec.give if app.catalog.get(i))
                get = sum(app.catalog.get(i).default_value for i in rec.get if app.catalog.get(i))
                if give:
                    card.add_widget(Factory.Muted(text=f"Value {give:,} for {get:,} ({(get - give) / give * 100:+.0f}%)"))
            card.add_widget(Factory.Txt(text=rec.reason, font_size=sp(14)))
            box.add_widget(card)
        if not advice.recommendations:
            box.add_widget(Factory.Muted(text="No usable recommendations this time.", halign="center"))
        app.request_thumbs(shown)


LINE_COLORS = {"value": P.ACCENT, "rap": "#a78bfa", "price": P.WARN}  # chart lines and their legend
LINE_NAMES = {"value": "Value", "rap": "RAP", "price": "Price"}


class ValueChart(Widget):
    """A line chart of several series on one scale: series = [(hex color, [(unix time, value), ...]), ...]."""
    series = ListProperty([])

    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(series=self.redraw, size=self.redraw, pos=self.redraw)

    def redraw(self, *_):
        self.canvas.clear()
        lines = [(color, pts) for color, pts in self.series if pts]
        if not lines or self.width < 10:
            return
        t0 = min(pts[0][0] for _c, pts in lines)
        t1 = max(pts[-1][0] for _c, pts in lines)
        values = [v for _c, pts in lines for _t, v in pts]
        lo, hi = min(values), max(values)
        pad = (hi - lo) * 0.08 or max(1, hi * 0.01)
        lo, hi = lo - pad, hi + pad
        with self.canvas:
            Color(*get_color_from_hex(P.BORDER))
            for frac in (0.0, 0.5, 1.0):  # light guide lines at the bottom, middle and top
                y = self.y + frac * self.height
                Line(points=[self.x, y, self.right, y], width=1)
            for color, pts in lines:
                coords = []
                for t, v in pts:
                    coords += [self.x + (t - t0) / ((t1 - t0) or 1) * self.width,
                               self.y + (v - lo) / (hi - lo) * self.height]
                Color(*get_color_from_hex(color))
                if len(pts) == 1:  # one reading so far (current price): a dot
                    Ellipse(pos=(coords[0] - dp(3), coords[1] - dp(3)), size=(dp(6), dp(6)))
                else:
                    Line(points=coords, width=dp(1.6), joint="round", cap="round")


def short_number(n: int) -> str:
    for size, unit in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if abs(n) >= size:
            return f"{n / size:.2f}".rstrip("0").rstrip(".") + unit
    return f"{n:,}"


class ItemsScreen(Screen):
    """What you own on Roblox (your Rolimons inventory), what it's worth, and value, RAP and price over time."""
    value_text = StringProperty("")
    rap_text = StringProperty("")
    price_text = StringProperty("")
    count_text = StringProperty("")
    change_text = StringProperty("")
    legend_text = StringProperty("")
    tone = StringProperty("even")
    range = StringProperty("1m")
    chart_note = StringProperty("")
    message = StringProperty("")

    def on_pre_enter(self):
        app = App.get_running_app()
        app.load_portfolio()
        self.refresh()

    MAX_ROWS = 150  # the most valuable items get a row; big inventories would take ages to draw in full

    def set_range(self, key: str):
        self.range = key
        if getattr(self, "_totals", None) is not None:
            self.refresh_chart(self._totals)  # the item list doesn't change with the chart's range
        else:
            self.refresh()

    def reload(self):
        App.get_running_app().load_portfolio(force=True)
        self.refresh()

    def refresh(self):
        app = App.get_running_app()
        box = self.ids.holdings
        box.clear_widgets()
        inventory = app.inventory
        if app.cfg.roblox_user_id <= 0:
            self.message = "Sign in to Rolimons on the Ads tab to see your items."
        elif inventory is None:
            self.message = "Loading your items..."
        elif inventory.private:
            self.message = "Your Roblox inventory is private, so Rolimons can't see your items."
        else:
            self.message = ""
        if inventory is None or inventory.private:
            self._totals = None
            self.value_text = self.rap_text = self.price_text = self.count_text = ""
            self.change_text = self.legend_text = self.chart_note = ""
            self.ids.chart.series = []
            return
        t = totals(inventory, app.catalog, app.best_prices)
        self._totals = t
        if t.price is not None and app.catalog:
            app.price_log.record(t.price)  # the app's own daily record of what your items cost now
        self.value_text = f"{t.value:,}"
        self.rap_text = f"{t.rap:,}"
        self.price_text = ("loading..." if t.price is None else
                           f"{t.price:,}" + (f"  ({t.unpriced} with no realistic seller, not counted)" if t.unpriced else ""))
        self.count_text = f"{t.items} item{'s' if t.items != 1 else ''}"
        self.refresh_chart(t)
        ids = []
        for h in t.holdings[:self.MAX_ROWS]:
            parts = [f"Value {h.value:,}", f"RAP {h.rap:,}"]
            if app.best_prices is not None:
                parts.append(f"Price {h.price:,}" if h.price else "No realistic seller")
            if h.count > 1:
                parts.insert(0, f"{h.count} copies")
            if h.on_hold:
                parts.append(f"{h.on_hold} on hold")
            if h.projected:
                parts.append(f"[color={P.WARN}]Projected[/color]")
            box.add_widget(ItemRow(thumb=app.thumb_source(h.item_id), name=h.name, value="  ·  ".join(parts),
                                   warn=h.projected))
            ids.append(h.item_id)
        hidden = len(t.holdings) - self.MAX_ROWS
        if hidden > 0:
            box.add_widget(Factory.Muted(text=f"and {hidden:,} more items (lower value)", halign="center"))
        app.request_thumbs(ids)

    def refresh_chart(self, t):
        app = App.get_running_app()
        history = app.value_history
        seconds = dict((key, secs) for key, _label, secs in RANGES)[self.range]
        label = dict((key, lbl) for key, lbl, _s in RANGES)[self.range]
        parts = {}
        if history is not None:
            parts["value"] = history.value.with_point(t.value).since(seconds)
            parts["rap"] = history.rap.with_point(t.rap).since(seconds)
        if t.price is not None:
            parts["price"] = app.price_log.series().since(seconds)
        self.ids.chart.series = [(LINE_COLORS[k], list(zip(s.times, s.values))) for k, s in parts.items()]
        legend, changes = [], []
        for key, s in parts.items():
            if not s.values:
                continue
            legend.append(f"[color={LINE_COLORS[key]}][b]—[/b][/color] {LINE_NAMES[key]} {short_number(s.values[-1])}")
            diff, pct = s.change()
            if len(s.values) > 1:
                changes.append(f"{LINE_NAMES[key]} {'+' if diff >= 0 else '-'}{short_number(abs(diff))}"
                               + (f" ({pct:+.1f}%)" if pct is not None else ""))
        self.legend_text = "     ".join(legend)
        self.change_text = (f"In {label}:  " + "   ·   ".join(changes)) if changes else ""
        diff = parts["value"].change()[0] if "value" in parts else 0
        self.tone = "even" if diff == 0 else "win" if diff > 0 else "loss"
        notes = []
        if history is None:
            notes.append(app.history_status or "Loading value and RAP history...")
        if "price" in parts and len(app.price_log.series().values) < 2:
            notes.append("Price history starts today: the app saves your items' current price once a day.")
        elif "price" in parts and len(parts["price"].values) < 2:
            notes.append("Not enough price history for this range yet.")
        self.chart_note = "\n".join(notes)


class MarketScreen(Screen):
    """Market tab: the item browser (search any limited, watch it for deals) and player lookup."""
    mode = StringProperty("items")
    discover = StringProperty("richest")   # Players: richest / traders / verified / tracked
    status_text = StringProperty("")
    busy = BooleanProperty(False)
    DISCOVER_CACHE = 10 * 60

    def __init__(self, **kw):
        super().__init__(**kw)
        self._cache = {}       # list name -> (fetched at, rows)
        self._loading = set()  # lists being fetched

    def on_pre_enter(self):
        App.get_running_app().ensure_prices()
        if self.mode == "items":
            self.show_items()
        elif not self.ids.search.text.strip():
            self.show_discover()

    def set_mode(self, mode: str):
        self.mode = mode
        self.ids.search.text = ""
        self.status_text = ""
        self.ids.results.clear_widgets()
        if mode == "items":
            self.show_items()
        else:
            self.show_discover()

    def schedule_search(self):
        if self.mode == "items":
            Clock.unschedule(self.show_items)
            Clock.schedule_once(self.show_items, 0.3)

    def submit(self):
        if self.mode == "players":
            self.lookup()
        else:
            self.show_items()

    # ---- items ---------------------------------------------------------------------------------
    def show_items(self, *_):
        app = App.get_running_app()
        box = self.ids.results
        box.clear_widgets()
        if not app.catalog:
            self.status_text = "Item list still loading..."
            return
        self.status_text = ""
        q = self.ids.search.text.strip().lower()
        if q:
            matches = []
            for item in app.catalog.items.values():
                if q == str(item.id) or q in item.name.lower() or q == item.acronym.lower():
                    rank = (0 if q in (item.acronym.lower(), str(item.id)) else
                            1 if item.name.lower().startswith(q) else 2)
                    matches.append((rank, -item.default_value, item.id))
            ids = [m[2] for m in sorted(matches)[:40]]
            heading = f"{len(ids)} item{'s' if len(ids) != 1 else ''}" if ids else "No matching items."
        else:
            ids = sorted(app.cfg.market.watchlist, key=lambda i: -(app.catalog.get(i).default_value
                                                                  if app.catalog.get(i) else 0))
            heading = ("Your watchlist" if ids else
                       "Search any limited by name, acronym or ID. Open one and tap Watch to get an alert when "
                       "someone lists it under value.")
        box.add_widget(Factory.FieldLabel(text=heading.upper() if ids and not q else heading))
        for item_id in ids:
            row = app.market_row(item_id)
            row.add_action("Open", lambda i=item_id: self.open_item(i), accent=True)
            box.add_widget(row)
        app.request_thumbs(ids)

    def open_item(self, item_id: int):
        app = App.get_running_app()
        app.sm.get_screen("item").load(item_id)
        app.show("item")

    def toggle_track(self, player, button):
        app = App.get_running_app()
        tracked = app.cfg.market.tracked_players
        if player.id in tracked:
            del tracked[player.id]
            button.text = "Track (alerts for trade ads and value changes)"
            app.persist()
            app.apply_trade_notifications()
            return app.toast("Stopped tracking")
        if len(tracked) >= MAX_TRACKED:
            return app.notice("Track", f"You can track up to {MAX_TRACKED} players. Stop tracking someone first.")
        tracked[player.id] = player.name
        button.text = "Stop tracking"
        app.persist()
        app.apply_trade_notifications()  # starts the background checks if needed
        droid.request_notification_permission()
        app.toast(f"Tracking {player.name}")

    # ---- players: discover lists ------------------------------------------------------------------
    def set_discover(self, name: str):
        self.discover = name
        self.ids.search.text = ""
        self.show_discover()

    def show_discover(self, force: bool = False):
        """Lists of interesting people. Opening one shows their card; following them is up to you."""
        app = App.get_running_app()
        kind = self.discover
        if kind == "tracked":
            rows = [(user_id, name, "Tracked: alerts for new trade ads and value changes", "")
                    for user_id, name in app.cfg.market.tracked_players.items()]
            return self._render_discover(rows, "Nobody tracked yet. Open a player and tap Track.")
        cached = self._cache.get(kind)
        if cached and not force and time.time() - cached[0] < self.DISCOVER_CACHE:
            return self._render_discover(cached[1])
        if kind in self._loading:  # its own flag, so Look up still works while a list loads
            return
        self._loading.add(kind)
        self.status_text = "Loading..."
        self.ids.results.clear_widgets()
        owned = set((app.owned_counts() or {}).keys())
        wanted = set(app.cfg.market.watchlist)
        catalog = app.catalog

        def work():
            session = requests.Session()
            try:
                if kind == "richest":
                    rows = [(l.id, f"#{l.rank}  {l.name}", f"Value {l.value:,}  ·  RAP {l.rap:,}", "")
                            for l in fetch_leaderboard(session)]
                elif kind == "traders":
                    rows = [(ad.user_id, ad.name, describe_ad(ad, catalog), why)
                            for ad, why in active_traders(fetch_recent_ads(session), owned, wanted)]
                else:  # verified: the verified accounts among the richest players and active traders
                    leaders = fetch_leaderboard(session)
                    traders = [ad for ad, _why in active_traders(fetch_recent_ads(session), owned, wanted, limit=200)]
                    people = {l.id: (f"#{l.rank}  {l.name}", f"Value {l.value:,}") for l in leaders}
                    for ad in traders:
                        people.setdefault(ad.user_id, (ad.name, "Posting trade ads"))
                    verified = verified_ids(session, list(people))
                    rows = [(uid, name, detail, "") for uid, (name, detail) in people.items() if uid in verified]
                self._discover_ready(kind, rows, "")
            except Exception as e:
                log.warning("Discover list failed: %s", e)
                self._discover_ready(kind, None, "Couldn't load this list. Check your internet and try again.")
        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def _discover_ready(self, kind: str, rows, error: str):
        self._loading.discard(kind)
        showing = (self.mode == "players" and self.discover == kind and not self.ids.search.text.strip()
                   and not self.busy)
        if rows is not None:
            self._cache[kind] = (time.time(), rows)
        if showing:
            self.status_text = error
            if rows is not None:
                self._render_discover(rows)

    def _render_discover(self, rows, empty: str = "Nobody here right now."):
        box = self.ids.results
        box.clear_widgets()
        self.status_text = ""
        notes = {"richest": "The richest players by Rolimons value.",
                 "traders": "People posting Rolimons trade ads right now. Ads that involve items you own or "
                            "watch come first.",
                 "verified": "Verified accounts among the richest players and active traders.",
                 "tracked": "Players you track (up to 20)."}
        box.add_widget(Factory.Muted(text=notes.get(self.discover, "") + " Open someone to see their items; "
                                     "follow or friend them yourself on their Roblox profile."))
        if not rows:
            box.add_widget(Factory.Muted(text=empty, halign="center"))
        for user_id, name, detail, why in rows:
            text = f"[color={P.OK}]{why}[/color]  ·  {detail}" if why else detail
            row = ItemRow(thumb="", name=name, value=text)
            row.add_action("Open", lambda u=user_id, n=name: self.open_player(u), accent=True)
            box.add_widget(row)

    def open_player(self, user_id: int):
        if self.busy:
            return
        self.busy = True
        self.status_text = "Loading player..."
        self.ids.results.clear_widgets()
        self._load_player(lambda session: lookup_user_id(session, user_id), "That player couldn't be found.")

    # ---- players: lookup and the player card --------------------------------------------------------
    def lookup(self):
        name = self.ids.search.text.strip()
        if not name or self.busy:
            return
        self.busy = True
        self.status_text = f"Looking up {name}..."
        self.ids.results.clear_widgets()
        self._load_player(lambda session: lookup_username(session, name), f"No Roblox user called {name}.")

    def _load_player(self, find, not_found: str):
        def work():
            session = requests.Session()
            try:
                player = find(session)
                if player is None:
                    return self._player_ready(None, None, None, not_found)
                inventory = fetch_inventory(session, player.id)
                try:
                    history = fetch_history(session, player.id)
                except Exception:
                    history = None  # players Rolimons hasn't scanned have no chart
                self._player_ready(player, inventory, history, "")
            except Exception as e:
                log.warning("Player lookup failed: %s", e)
                self._player_ready(None, None, None, "Couldn't look that player up. Check your internet and try again.")
        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def _player_ready(self, player, inventory, history, error: str):
        self.busy = False
        self.status_text = error
        if player is None:
            return
        app = App.get_running_app()
        box = self.ids.results
        box.clear_widgets()
        card = Factory.Card()
        badge = "  [color=" + P.ACCENT + "](verified)[/color]" if player.verified else ""
        card.add_widget(Factory.Title(text=f"{player.name}{badge}"))
        if player.display_name and player.display_name != player.name:
            card.add_widget(Factory.Muted(text=player.display_name))
        t = totals(inventory, app.catalog) if inventory and not inventory.private and app.catalog else None
        if inventory is not None and inventory.private:
            card.add_widget(Factory.Txt(text="Their inventory is private."))
        elif t:
            card.add_widget(Factory.Txt(text=f"[b]Value {t.value:,}[/b]   ·   RAP {t.rap:,}   ·   {t.items} items"))
        if history and history.value.values and t:
            year = history.value.with_point(t.value).since(365 * 86400)
            chart = ValueChart(size_hint_y=None, height=dp(150))
            chart.series = [(P.ACCENT, list(zip(year.times, year.values)))]
            card.add_widget(chart)
            diff, pct = year.change()
            if pct is not None:
                card.add_widget(Factory.Muted(text=f"Value {'+' if diff >= 0 else '-'}{short_number(abs(diff))} "
                                                   f"({pct:+.1f}%) in the last year"))
        buttons = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        for text, url in (("Roblox profile", f"https://www.roblox.com/users/{player.id}/profile"),
                          ("Rolimons", f"https://www.rolimons.com/player/{player.id}")):
            btn = FlatButton(text=text)
            btn.bind(on_release=lambda *_a, u=url: droid.open_url(u))
            buttons.add_widget(btn)
        card.add_widget(buttons)
        tracked = player.id in app.cfg.market.tracked_players
        track = FlatButton(text="Stop tracking" if tracked else "Track (alerts for trade ads and value changes)")
        track.bind(on_release=lambda *_a: self.toggle_track(player, track))
        card.add_widget(track)
        box.add_widget(card)
        if t:
            box.add_widget(Factory.FieldLabel(text="MOST VALUABLE ITEMS"))
            ids = [h.item_id for h in t.holdings[:40]]
            for h in t.holdings[:40]:
                row = app.market_row(h.item_id)
                if h.count > 1:
                    row.name += f"  ×{h.count}"
                row.add_action("Open", lambda i=h.item_id: self.open_item(i))
                box.add_widget(row)
            app.request_thumbs(ids)


class ItemScreen(Screen):
    """One item from the Market tab: Rolimons data, current price, and watching it for deals."""
    title = StringProperty("Item")
    thumb = StringProperty("")
    info_text = StringProperty("")
    watching = BooleanProperty(False)

    def load(self, item_id: int):
        self.item_id = item_id
        self.refresh()
        self.load_intel()

    def load_intel(self):
        """RAP / price history, sales, value changes and owners from the item's Rolimons page."""
        box = self.ids.intel
        box.clear_widgets()
        box.add_widget(Factory.Muted(text="Loading sales, history and owners..."))
        item_id = self.item_id

        def work():
            try:
                intel = fetch_item_intel(requests.Session(), item_id)
            except Exception as e:
                log.warning("Item intel failed: %s", e)
                intel = None
            self._intel_ready(item_id, intel)
        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def _intel_ready(self, item_id: int, intel):
        if item_id != getattr(self, "item_id", None):
            return
        app = App.get_running_app()
        box = self.ids.intel
        box.clear_widgets()
        if intel is None:
            box.add_widget(Factory.Muted(text="Couldn't load this item's history from Rolimons."))
            return
        year = 365 * 86400
        rap, price = intel.rap.since(year), intel.best_price.since(year)
        if len(rap.values) > 1:
            box.add_widget(Factory.FieldLabel(text="LAST YEAR"))
            chart = ValueChart(size_hint_y=None, height=dp(150))
            # Listings far above RAP (nobody selling near value) would flatten the RAP line: leave them off.
            cap = 3 * max(max(rap.values), getattr(app.catalog.get(item_id), "default_value", 0) or 0)
            chart.series = [(LINE_COLORS["rap"], list(zip(rap.times, rap.values))),
                            (LINE_COLORS["price"], [(t, v) for t, v in zip(price.times, price.values) if 0 < v <= cap])]
            box.add_widget(chart)
            legend = (f"[color={LINE_COLORS['rap']}][b]—[/b][/color] RAP {short_number(rap.values[-1])}     "
                      f"[color={LINE_COLORS['price']}][b]—[/b][/color] Best price {short_number(price.values[-1])}")
            box.add_widget(Factory.Txt(text=legend, font_size=sp(13), halign="center"))
        lines = []
        sold, avg = intel.sales_summary(30)
        lines.append(f"Sales, last 30 days: [b]{sold}[/b]" + (f" at {avg:,} R$ on average" if avg else ""))
        sold90, avg90 = intel.sales_summary(90)
        if sold90:
            lines.append(f"Last 90 days: {sold90} sold" + (f", {avg90:,} R$ on average" if avg90 else ""))
        if intel.value_changes:
            changes = [f"{time.strftime('%d %b %Y', time.localtime(t))}: {v:,}" for t, v in intel.value_changes[-4:]]
            lines.append("Value changes: " + "  ·  ".join(reversed(changes)))
        lines.append(f"{intel.owners:,} owners  ·  {intel.copies:,} copies  ·  {intel.hoarded:,} hoarded  ·  "
                     f"{intel.deleted:,} deleted")
        box.add_widget(Factory.Txt(text="\n".join(lines), font_size=sp(14)))
        for title, people, detail in (
                ("BIGGEST HOARDERS", intel.hoarders[:5], lambda o: f"{o.copies} copies"),
                ("GOT A COPY MOST RECENTLY", intel.recent_owners[:8],
                 lambda o: time.strftime("%d %b %Y", time.localtime(o.since)) if o.since else "")):
            if not people:
                continue
            box.add_widget(Factory.FieldLabel(text=title))
            for person in people:
                row = ItemRow(thumb="", name=person.name, value=detail(person))
                row.add_action("Open", lambda u=person.user_id: app.open_player(u))
                box.add_widget(row)

    def refresh(self):
        app = App.get_running_app()
        info = app.catalog.get(self.item_id) if app.catalog else None
        self.title = info.label if info else f"Item {self.item_id}"
        self.thumb = app.thumb_source(self.item_id)
        app.request_thumbs([self.item_id])
        lines = []
        if info:
            lines.append(f"[b]Value {info.default_value:,}[/b]" + ("" if info.value > 0 else "  (no Rolimons value: RAP)"))
            lines.append(f"RAP {info.rap:,}")
            lines.append(f"Demand: {info.demand_label}   ·   Trend: {info.trend_label}")
            listed = app.best_prices.get(self.item_id) if app.best_prices is not None else None
            price = realistic_price(listed, info.default_value, info.rap)
            if app.best_prices is None:
                lines.append("Current price: loading...")
            elif price:
                pct = (price - info.default_value) / info.default_value * 100 if info.default_value else 0
                lines.append(f"Current price {price:,} R$ ({pct:+.0f}% vs value)")
            else:
                lines.append("Current price: nobody is selling at a realistic price")
            flags = [f for f, on in (("Projected", info.projected), ("Hyped", info.hyped), ("Rare", info.rare)) if on]
            if flags:
                lines.append(f"[color={P.WARN}]{'  ·  '.join(flags)}[/color]")
            owned = app.owned_counts() or {}
            if owned.get(self.item_id):
                lines.append(f"You own {owned[self.item_id]}")
        self.info_text = "\n".join(lines)
        watchlist = app.cfg.market.watchlist
        self.watching = self.item_id in watchlist
        self.ids.discount.text = f"{watchlist.get(self.item_id, 10):g}"

    def toggle_watch(self):
        app = App.get_running_app()
        watchlist = app.cfg.market.watchlist
        if self.watching:
            watchlist.pop(self.item_id, None)
            app.persist()
            app.apply_trade_notifications()
            self.watching = False
            return app.toast("Removed from your watchlist")
        try:
            discount = float(self.ids.discount.text or 0)
        except ValueError:
            discount = 0
        if not 0 < discount < 100:
            return app.notice("Watchlist", "Enter a discount between 1 and 99 (%).")
        watchlist[self.item_id] = discount
        app.persist()
        app.apply_trade_notifications()  # starts the background checks if needed
        self.watching = True
        note = "" if app.cfg.app.notifications and app.cfg.market.watch_alerts else \
            " Alerts are off: turn on notifications and watchlist alerts in Settings."
        droid.request_notification_permission()
        app.notice("Watching", f"You'll get an alert when it's listed at least {discount:g}% under value.{note}")

    def open_roblox(self):
        droid.open_url(f"https://www.roblox.com/catalog/{self.item_id}")

    def open_rolimons(self):
        droid.open_url(f"https://www.rolimons.com/item/{self.item_id}")


class PlannerScreen(Screen):
    """Trade planner: pick what you want (upgrade) or what you give (downgrade); it suggests the other side.
    A planning tool: you send the trade yourself on Roblox."""
    mode = StringProperty("upgrade")
    status_text = StringProperty("")

    def __init__(self, **kw):
        super().__init__(**kw)
        self.picked: list[int] = []   # upgrade: items you want; downgrade: items you give
        self.keep: list[int] = []     # items you've fixed on the other side (the planner fills the rest)

    def on_pre_enter(self):
        self.refresh()

    def set_mode(self, mode: str):
        self.mode = mode
        self.picked, self.keep = [], []
        self.ids.suggestions.clear_widgets()
        self.status_text = ""
        self.refresh()

    def add_item(self, which: str):
        """which: "picked" or "keep". Upgrade: picked = want (any item), keep = give (yours)."""
        app = App.get_running_app()
        target = self.picked if which == "picked" else self.keep
        if len(target) >= 4:
            return app.toast("Up to 4 items per side.")
        yours = (which == "keep") == (self.mode == "upgrade")
        picker = app.sm.get_screen("picker")
        picker.open_for("offer" if yours else "request", on_pick=lambda item_id: self._picked(target, item_id))
        app.show("picker")

    def _picked(self, target: list, item_id: int) -> bool:
        target.append(item_id)
        self.refresh()
        return True

    def remove(self, target: list, index: int):
        target.pop(index)
        self.refresh()

    def refresh(self):
        app = App.get_running_app()
        for box, items in ((self.ids.picked_box, self.picked), (self.ids.keep_box, self.keep)):
            box.clear_widgets()
            for i, item_id in enumerate(items):
                row = app.item_row(item_id)
                row.add_action("×", lambda t=items, n=i: self.remove(t, n))
                box.add_widget(row)
            if not items:
                box.add_widget(Factory.Muted(text="Nothing yet."))
        app.request_thumbs(self.picked + self.keep)

    def suggest(self):
        app = App.get_running_app()
        box = self.ids.suggestions
        box.clear_widgets()
        if not app.catalog:
            self.status_text = "Item list still loading..."
            return
        if not self.picked:
            self.status_text = ("Add the item(s) you want first." if self.mode == "upgrade"
                                else "Add the item(s) you want to give first.")
            return
        try:
            pct = float(self.ids.pct.text or 0)
        except ValueError:
            pct = 0
        if self.mode == "upgrade":
            if app.inventory is None or app.inventory.private:
                self.status_text = "Your inventory isn't available (not loaded yet, or private)."
                return
            ideas = plan_upgrade(self.picked, app.inventory, app.catalog, overpay=pct, keep_give=self.keep)
        else:
            ideas = plan_downgrade(self.picked, app.catalog, ask=pct, keep_get=self.keep)
        self.status_text = "" if ideas else "No good fit found. Try a different overpay or fewer fixed items."
        for n, idea in enumerate(ideas, 1):
            card = Factory.Card()
            if abs(idea.overpay) < 0.05:
                balance = "Even trade"
            elif idea.overpay > 0:
                balance = f"You overpay {idea.overpay:.1f}%"
            else:
                balance = f"You get {-idea.overpay:.1f}% more"
            card.add_widget(Factory.Title(text=f"Idea {n}  [size={int(sp(13))}][color={P.MUTED}]{balance}"
                                               f"[/color][/size]"))
            for label, items, total in (("YOU GIVE", idea.give, idea.give_value), ("YOU GET", idea.get, idea.get_value)):
                card.add_widget(Factory.FieldLabel(text=f"{label}  ·  {total:,}"))
                for item_id in items:
                    card.add_widget(app.item_row(item_id))
            box.add_widget(card)
            app.request_thumbs(idea.give + idea.get)
        if ideas:
            box.add_widget(Factory.Muted(text="Values are Rolimons values. Check demand and recent sales before "
                                              "sending, and send the trade yourself on Roblox."))


class TradeLogScreen(Screen):
    """Trade tracker: your completed trades with their value at the time, and running totals."""
    summary_text = StringProperty("")
    status_text = StringProperty("")
    busy = BooleanProperty(False)

    def on_pre_enter(self):
        self.refresh()

    def refresh(self):
        app = App.get_running_app()
        log = app.trade_log
        t = log.totals()
        if t.trades:
            tone = P.OK if t.net > 0 else P.BAD if t.net < 0 else P.MUTED
            self.summary_text = (f"[b]{t.trades} trades[/b]  ·  {t.wins} wins  ·  {t.losses} losses\n"
                                 f"Net [color={tone}][b]{'+' if t.net >= 0 else '-'}{abs(t.net):,}[/b][/color] "
                                 f"value  ·  given {short_number(t.given)}, received {short_number(t.received)}")
        else:
            self.summary_text = ("No trades logged yet. Tap Sync, or open Trades > Completed: every completed "
                                 "trade the app sees is logged.")
        box = self.ids.entries
        box.clear_widgets()
        for trade in log.newest_first()[:150]:
            when = time.strftime("%d %b %Y", time.localtime(trade.time)) if trade.time else "?"
            tone = P.OK if trade.gain > 0 else P.BAD if trade.gain < 0 else P.MUTED
            pct = f" ({trade.gain / trade.give_value * 100:+.0f}%)" if trade.give_value else ""
            box.add_widget(ItemRow(thumb=app.thumb_source(trade.get[0]) if trade.get else "",
                                   name=f"{trade.partner}  ·  {when}",
                                   value=f"Gave {trade.give_value:,}  ·  got {trade.get_value:,}  ·  "
                                         f"[color={tone}]{'+' if trade.gain >= 0 else ''}{trade.gain:,}{pct}[/color]"))
        app.request_thumbs([t.get[0] for t in log.newest_first()[:150] if t.get])

    def sync(self):
        """Reads your recent completed trades (up to 100) and logs the new ones."""
        app = App.get_running_app()
        if self.busy:
            return
        if not (app.cfg.app.direct_trades and droid.RobloxDirect.signed_in()):
            return app.notice("Trade log", 'Syncing needs "Read my trades directly" (Settings) and a Roblox sign-in.')
        self.busy = True
        self.status_text = "Reading your completed trades..."
        catalog = app.catalog

        def work():
            added, cursor = 0, ""
            try:
                for _page in range(4):
                    status, body = droid.RobloxDirect.fetch("list", "completed", cursor)
                    if status != 200:
                        break
                    trades, cursor = parse_list(body)
                    for trade in trades:
                        if trade.id in app.trade_log.trades:
                            continue
                        status, raw = droid.RobloxDirect.fetch("trade", str(trade.id))
                        if status == 429:
                            time.sleep(6)
                            status, raw = droid.RobloxDirect.fetch("trade", str(trade.id))
                        if status == 200:
                            added += app.trade_log.add_details(trade, parse_details(raw, trade.partner_id, catalog))
                    if not cursor:
                        break
                app.trade_log.save()
                self._synced(f"Logged {added} new trade{'s' if added != 1 else ''}.")
            except Exception as e:
                log.warning("Trade log sync failed: %s", e)
                self._synced("Couldn't finish syncing. Try again in a minute.")
        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def _synced(self, message: str):
        self.busy = False
        self.status_text = message
        self.refresh()


class PickerScreen(Screen):
    """Full-screen item search: tap an item to add it to the ad being edited."""
    title = StringProperty("Add item")
    side = "want"

    def open_for(self, side: str, on_pick=None):
        """side "offer": your items; "request": any item. on_pick(item_id) -> bool: who gets the item
        (default: the ad editor)."""
        self.side = side
        self.on_pick = on_pick
        self.title = "Add item you offer" if side == "offer" else "Add item you want"
        self.ids.search.text = ""
        self.search()

    def on_enter(self):
        # Offers start with your items listed, so the keyboard only opens for "want".
        if self.side != "offer":
            Clock.schedule_once(lambda *_: setattr(self.ids.search, "focus", True), 0.15)

    def schedule_search(self):
        Clock.unschedule(self.search)
        Clock.schedule_once(self.search, 0.3)

    def _note(self, text: str):
        self.ids.results.add_widget(Factory.Muted(text=text, halign="center", height=dp(40)))

    def search(self, *_):
        """Offers: only items in your Rolimons inventory (all of them until you type). Wants: any item."""
        app = App.get_running_app()
        box = self.ids.results
        box.clear_widgets()
        q = self.ids.search.text.strip().lower()
        owned = app.owned_counts() if self.side == "offer" else None
        if self.side == "offer" and owned is None:
            self._note("Your Rolimons inventory isn't available (not loaded yet, or private), so this searches "
                       "all items.")
        if not q and owned is None:
            if self.side != "offer":
                self._note("Type to search all Rolimons items.")
            return
        if not app.catalog:
            return self._note("Item list still loading...")
        pool = ([i for i in (app.catalog.get(item_id) for item_id in owned) if i] if owned is not None
                else app.catalog.items.values())
        matches = []
        for item in pool:
            if not q or q == str(item.id) or q in item.name.lower() or q == item.acronym.lower():
                rank = (0 if q and q in (item.acronym.lower(), str(item.id)) else
                        1 if item.name.lower().startswith(q) else 2)
                matches.append((rank, -item.default_value, item.id))
        matches.sort()
        ids = [m[2] for m in matches[:200 if owned is not None else 30]]
        if owned is not None:
            self._note(f"Your items ({len(ids)})" if not q else f"Your items matching \"{q}\" ({len(ids)})")
        for item_id in ids:
            row = app.item_row(item_id)
            if owned and owned.get(item_id, 0) > 1:
                row.name += f"  ×{owned[item_id]}"
            row.add_action("Add", lambda i=item_id: self.choose(i), accent=True)
            box.add_widget(row)
        if not ids:
            self._note("You don't own a matching item." if owned is not None else "No matching items.")
        self.ids.scroll.scroll_y = 1
        app.request_thumbs(ids)

    def choose(self, item_id: int):
        app = App.get_running_app()
        handler = getattr(self, "on_pick", None) or (lambda i: app.sm.get_screen("edit").add(self.side, i))
        if handler(item_id):
            self.ids.search.focus = False
            app.go_back()


class EditScreen(Screen):
    index = NumericProperty(-1)

    def load(self, index: int, ad: Ad):
        self.index = index
        self.ad = copy.deepcopy(ad)
        self.ids.name.text = ad.name
        self.ids.enabled.active = ad.enabled
        tags = self.ids.tags
        tags.clear_widgets()
        self._chips = {}
        for tag in VALID_TAGS:
            chip = Chip(text=tag, selected=tag in ad.request_tags)
            chip.bind(on_release=lambda c, t=tag: self.toggle_tag(t))
            self._chips[tag] = chip
            tags.add_widget(chip)
        self.refresh()
        App.get_running_app().request_thumbs(ad.all_item_ids())
        self.ids.scroll.scroll_y = 1

    def _slots(self) -> int:
        return len(self.ad.request_item_ids) + sum(c.selected for c in self._chips.values())

    def toggle_tag(self, tag: str):
        chip = self._chips[tag]
        if not chip.selected and self._slots() >= MAX_REQUEST_SLOTS:
            return App.get_running_app().toast(f"You can want at most {MAX_REQUEST_SLOTS} items and tags.")
        chip.selected = not chip.selected
        self.refresh_summary()

    def refresh(self):
        app = App.get_running_app()
        missing = set(missing_offer_items(self.ad, app.inventory))
        for box, ids, side in ((self.ids.offer_box, self.ad.offer_item_ids, "offer"),
                               (self.ids.want_box, self.ad.request_item_ids, "request")):
            box.clear_widgets()
            for i, item_id in enumerate(ids):
                row = app.item_row(item_id, warn=side == "offer" and item_id in missing)
                row.add_action("×", lambda s=side, n=i: self.remove(s, n))
                box.add_widget(row)
            if not ids:
                box.add_widget(Label(text="Nothing added yet.", color=(0.55, 0.58, 0.64, 1),
                                     size_hint_y=None, height=36, font_size="14sp"))
        self.ids.owned_hint.text = ("Highlighted items aren't in your Rolimons inventory, so this ad will be skipped."
                                    if missing else "")
        self.refresh_summary()

    def refresh_summary(self):
        catalog = App.get_running_app().catalog
        if not catalog:
            self.ids.summary.text = ""
            return
        av = evaluate_ad(self.ad, catalog)
        text = f"Offer value {av.offer_value:,}"
        if av.request_value is not None:
            text += f"   ·   Want value {av.request_value:,} ({av.overpay_percent:+.0f}%)"
        self.ids.summary.text = text

    def remove(self, side: str, index: int):
        (self.ad.offer_item_ids if side == "offer" else self.ad.request_item_ids).pop(index)
        self.refresh()

    def add(self, side: str, item_id: int) -> bool:
        app = App.get_running_app()
        if side == "offer":
            if len(self.ad.offer_item_ids) >= MAX_OFFER_ITEMS:
                app.toast(f"You can offer at most {MAX_OFFER_ITEMS} items.")
                return False
            self.ad.offer_item_ids.append(item_id)
        else:
            if self._slots() >= MAX_REQUEST_SLOTS:
                app.toast(f"You can want at most {MAX_REQUEST_SLOTS} items and tags.")
                return False
            self.ad.request_item_ids.append(item_id)
        self.refresh()
        return True

    def open_picker(self, side: str):
        app = App.get_running_app()
        full = (len(self.ad.offer_item_ids) >= MAX_OFFER_ITEMS if side == "offer"
                else self._slots() >= MAX_REQUEST_SLOTS)
        if full:
            limit = (f"You can offer at most {MAX_OFFER_ITEMS} items." if side == "offer"
                     else f"You can want at most {MAX_REQUEST_SLOTS} items and tags.")
            return app.toast(limit)
        app.sm.get_screen("picker").open_for(side)
        app.show("picker")

    def save(self):
        app = App.get_running_app()
        self.ad.name = self.ids.name.text.strip()
        self.ad.enabled = self.ids.enabled.active
        self.ad.request_tags = [t for t, c in self._chips.items() if c.selected]
        if not self.ad.name:
            return app.notice("Can't save yet", "Give the ad a name.")
        if any(a.name == self.ad.name for i, a in enumerate(app.cfg.ads) if i != self.index):
            return app.notice("Can't save yet", "Another ad already has that name.")
        if not self.ad.offer_item_ids:
            return app.notice("Can't save yet", "Add at least one item you offer.")
        if not self.ad.request_item_ids and not self.ad.request_tags:
            return app.notice("Can't save yet", "Add at least one item or tag you want.")
        if self.index >= 0:
            app.cfg.ads[self.index] = self.ad
        else:
            app.cfg.ads.append(self.ad)
        app.persist()
        app.go_back()

    def delete(self):
        app = App.get_running_app()

        def really():
            del app.cfg.ads[self.index]
            app.persist()
            app.go_back()
        app.notice("Delete ad", f"Delete '{self.ad.name}'?", (("Cancel", None), ("Delete", really)))


# ---- app -----------------------------------------------------------------------
class SwipeManager(ScreenManager):
    """Swipe left/right on a main tab to go to the next/previous tab.

    A mostly-horizontal drag counts as a swipe; it cancels any button press it started on (so swiping
    across an ad card doesn't open it). Screens that aren't tabs (ad editor, item picker) ignore swipes.
    """
    START = 24  # dp of horizontal travel before a drag counts as a swipe
    MIN = 70    # dp of travel needed to change tab

    def on_touch_down(self, touch):
        touch.ud["swipe_start"] = (touch.x, touch.y)
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        from kivy.metrics import dp
        start = touch.ud.get("swipe_start")
        if start and not touch.ud.get("swiping") and self.current in App.get_running_app().visible_tabs():
            dx, dy = touch.x - start[0], touch.y - start[1]
            if abs(dx) > dp(self.START) and abs(dx) > 2 * abs(dy):
                touch.ud["swiping"] = True
                for ref in list(touch.grab_list):  # cancel presses/scrolls this touch started
                    widget = ref() if callable(ref) else ref
                    if widget is not None and widget is not self:
                        touch.ungrab(widget)
                        if hasattr(widget, "state"):
                            widget.state = "normal"
        if touch.ud.get("swiping"):
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        from kivy.metrics import dp
        if touch.ud.get("swiping"):
            dx = touch.x - touch.ud["swipe_start"][0]
            if abs(dx) >= dp(self.MIN):
                App.get_running_app().swipe_tab(1 if dx < 0 else -1)
            return True
        return super().on_touch_up(touch)


class RoliApp(App):
    title = "LimiTools"
    running = BooleanProperty(False)
    status_title = StringProperty("Stopped")
    status_detail = StringProperty("")
    cookie_text = StringProperty("")
    cookie_state = StringProperty("bad")
    ads_count = StringProperty("")
    update_text = StringProperty("")
    active_tab = StringProperty("home")
    can_sign_in = BooleanProperty(droid.RolimonsLogin.available)
    icon_path = StringProperty(str(asset("assets/icon.png")))

    def build(self):
        Window.clearcolor = get_color_from_hex(P.BG)
        if not droid.IS_ANDROID:
            Window.size = (420, 880)  # phone-shaped preview window
        Window.softinput_mode = "below_target"
        Window.bind(on_keyboard=self._on_key)
        setup_logging(log_dir())
        droid.prime_java()  # worker threads (the trades list) use the app's Java classes
        load_env_file(env_path())
        self.cfg = self._load_cfg()
        self.catalog: ItemCatalog | None = None
        self.inventory = None
        self.thumbs = ThumbnailCache(cache_dir() / "thumbs")
        self._thumb_tried: set[int] = set()
        self.engine = droid.Engine(HOME)
        self.login = None
        self._start_requested_at = 0.0
        self._stop_requested_at = 0.0
        self._last_error_seen = None
        self._update_url = ""
        self._direct_checked_at = 0.0
        self.value_history = None   # roliposter.portfolio.History, from your Rolimons player page
        self.best_prices = None     # asset ID -> cheapest copy for sale now (Rolimons deals page)
        self.price_log = PriceLog(HOME / "price_history.json")
        self.trade_log = TradeLog(HOME / "trade_log.json")
        self.history_status = ""
        self._portfolio_at = 0.0
        self._stack: list[str] = []
        register_fonts()
        from kivy.metrics import Metrics
        if Metrics.fontscale > 1.2:  # very large system font sizes would push text out of the layout
            Metrics.fontscale = 1.2
        Builder.load_file(str(HERE / "ui.kv"))
        self.sm = SwipeManager(transition=SlideTransition(duration=0.18))
        for screen in (HomeScreen(), EditScreen(), SettingsScreen(), HistoryScreen(), CookieScreen(),
                       TradesScreen(), TradeScreen(), ItemsScreen(), AutoScreen(), AiScreen(), HelpScreen(),
                       PickerScreen(), MarketScreen(), ItemScreen(), PlannerScreen(), TradeLogScreen()):
            self.sm.add_widget(screen)
        # Before anything opens the Trades tab (e.g. a tapped notification): list or Roblox page.
        Clock.schedule_once(lambda *_: self.sync_direct_trades(), 0)
        self.refresh_ads()
        self.update_cookie_status()
        Clock.schedule_interval(self.tick, 0.5)
        threading.Thread(target=self._load_catalog, daemon=True).start()
        if self.cfg.app.check_updates:
            threading.Thread(target=self._check_updates, daemon=True).start()
        Clock.schedule_once(lambda *_: self._first_run_checks(), 1.0)
        self.trades_view = (droid.TradesView(TRADES_URL, VIEW_ONLY_JS + TRADE_POLL_JS)
                            if droid.TradesView.available else None)
        Clock.schedule_once(lambda *_: self.apply_trade_notifications(), 2.5)  # after the insets are known
        if droid.IS_ANDROID:
            from android import activity  # type: ignore
            activity.bind(on_new_intent=self._on_new_intent)
        self.nav = Factory.NavBar()
        self.rebuild_nav()
        root = BoxLayout(orientation="vertical")
        root.add_widget(self.sm)
        root.add_widget(self.nav)
        self.sm.bind(current=lambda _sm, name: setattr(self, "active_tab", name) if name in ALL_TABS else None)
        self.root_box = root
        self.inset_top = self.inset_bottom = 0
        with root.canvas.before:  # fills the strip behind the gesture bar in the tab bar's colour
            Color(*get_color_from_hex(P.SURFACE))
            self._bottom_fill = Rectangle(pos=(0, 0), size=(0, 0))
        Clock.schedule_once(self._apply_insets, 0.5)
        Clock.schedule_once(self._apply_insets, 2.0)  # again once Android has finished laying out
        Window.bind(on_resize=lambda *_: Clock.schedule_once(self._apply_insets, 0.3))
        return root

    def visible_tabs(self) -> list[str]:
        hidden = set(self.cfg.app.hidden_tabs)
        return [t for t in ALL_TABS if t not in hidden]

    def rebuild_nav(self):
        """The bottom tab bar, with only the tabs turned on in Settings."""
        self.nav.clear_widgets()
        for tab in self.visible_tabs():
            self.nav.add_widget(NavButton(text=TAB_LABELS[tab], tab=tab))

    def open_player(self, user_id: int):
        """A player's card (Market > Players), from anywhere in the app."""
        market = self.sm.get_screen("market")
        self.switch_tab("market")
        market.mode = "players"
        market.ids.search.text = ""
        market.open_player(user_id)

    def ensure_prices(self):
        """Current best prices (Market tab, item screen), loaded once in the background."""
        if self.best_prices is not None or getattr(self, "_prices_loading", False):
            return
        self._prices_loading = True

        def work():
            try:
                prices = fetch_best_prices(requests.Session())
            except Exception:
                prices = None
            self._prices_ready(prices)
        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def _prices_ready(self, prices):
        self._prices_loading = False
        if prices is not None:
            self.best_prices = prices
        if self.sm.current == "item":
            self.sm.get_screen("item").refresh()

    def market_row(self, item_id: int) -> ItemRow:
        item = self.catalog.get(item_id) if self.catalog else None
        parts = []
        if item:
            parts.append(f"Value {item.default_value:,}")
            listed = self.best_prices.get(item_id) if self.best_prices is not None else None
            price = realistic_price(listed, item.default_value, item.rap)
            if price:
                pct = (price - item.default_value) / item.default_value * 100 if item.default_value else 0
                parts.append(f"Price {price:,} ({pct:+.0f}%)")
            parts.append(item.demand_label)
            if item.projected:
                parts.append(f"[color={P.WARN}]Projected[/color]")
        if item_id in self.cfg.market.watchlist:
            parts.append(f"[color={P.ACCENT}]Watching ≥{self.cfg.market.watchlist[item_id]:g}% off[/color]")
        return ItemRow(thumb=self.thumb_source(item_id), name=item.label if item else f"Item {item_id}",
                       value="  ·  ".join(parts), warn=bool(item and item.projected))

    def _apply_insets(self, *_):
        """Keeps the header and tab bar out from under Android 15's edge-to-edge system bars."""
        top, bottom = droid.system_bar_overlap(int(Window.height))
        self.inset_top, self.inset_bottom = top, bottom
        self.root_box.padding = [0, top, 0, bottom]
        self._bottom_fill.size = (Window.width, bottom)
        if self.sm.current == "trades":
            self.show_trades_view()

    def _load_cfg(self) -> Config:
        try:
            return load_config(config_path())
        except ConfigError:
            if (droid.launch_extra("demo") or "") == "1":  # sample ads for screenshots/tests
                example = HERE / "config.example.json"
                if not example.exists():
                    example = HERE.parent / "config.example.json"
                if example.exists():
                    cfg = load_config(example)
                    save_config(cfg, config_path())
                    return cfg
            return Config()

    def persist(self):
        save_config(self.cfg, config_path())
        self.refresh_ads()

    # ---- navigation ------------------------------------------------------
    def show(self, name: str):
        if name == self.sm.current:
            return
        self._stack.append(self.sm.current)
        self.sm.transition.direction = "left"
        self.sm.current = name

    def switch_tab(self, name: str):
        """Bottom tab bar: jump to a tab (tabs aren't stacked, so Back from a tab goes to Ads)."""
        if name == self.sm.current:
            return
        self._stack.clear()
        order = list(ALL_TABS)
        current = self.sm.current if self.sm.current in order else "home"
        self.sm.transition.direction = "left" if order.index(name) > order.index(current) else "right"
        self.sm.current = name

    def swipe_tab(self, step: int):
        """Swipe left (step +1) / right (step -1) between the main tabs, in tab-bar order."""
        order = self.visible_tabs()
        if self.sm.current in order:
            target = order.index(self.sm.current) + step
            if 0 <= target < len(order):
                self.switch_tab(order[target])

    def go_back(self):
        if self._stack:
            self.sm.transition.direction = "right"
            self.sm.current = self._stack.pop()
            return True
        if self.sm.current in ALL_TABS and self.sm.current != "home":
            self.switch_tab("home")
            return True
        return False

    def _on_key(self, _window, key, *_):
        if key == 27:  # Android back button (Escape on a PC)
            if self.login and self.login.is_open:
                self.login.close()
            elif self.sm.current == "trades" and self.trades_view and not self.sm.get_screen("trades").native:
                self.trades_view.go_back(otherwise=lambda: self.switch_tab("home"))
            elif not self.go_back():
                droid.move_to_background()  # like Home: never quit, posting keeps running
            return True
        return False

    # ---- received trades -------------------------------------------------
    def _trades_area(self) -> tuple[int, int]:
        """Pixels between the trades tab's top bar and the bottom tab bar (Android view coordinates)."""
        from kivy.metrics import dp
        top = self.inset_top + int(dp(58))
        return top, int(Window.height - top - self.nav.height - self.inset_bottom)

    def show_trades_view(self):
        if self.trades_view:
            self.trades_view.show(*self._trades_area())

    def hide_trades_view(self):
        if self.trades_view:
            self.trades_view.hide()

    def apply_trade_notifications(self):
        """"New trade from X": with "Read my trades directly" the background service checks; otherwise
        the (hidden) trades page does, so it's loaded at startup."""
        enabled = self.cfg.app.notifications and self.cfg.app.trade_notifications
        direct = self.cfg.app.direct_trades and droid.RobloxDirect.available
        droid.RobloxDirect.set_enabled(direct)  # off deletes the stored sign-in
        droid.push_auto_accept(self.cfg)
        droid.push_social_alerts(self.cfg)
        droid.set_trade_notifications(enabled and not direct)
        if enabled and not direct and self.trades_view:
            self.trades_view.preload(*self._trades_area())
        Clock.schedule_once(lambda *_: self.sync_direct_trades(), 1.0)  # after the sign-in is copied

    def sync_direct_trades(self):
        """Follows the Roblox sign-in for "Read my trades directly": list or Roblox page, background checks."""
        self._direct_checked_at = time.time()
        screen = self.sm.get_screen("trades")
        direct = self.cfg.app.direct_trades and droid.RobloxDirect.signed_in()
        if direct != screen.direct:
            screen.direct = direct
            screen.page = False
            screen._loaded_at = 0.0
            screen.apply_view()
        if droid.service_wanted(self.cfg):
            text = droid.WATCHING_TEXT if droid.trade_watch_wanted(self.cfg) else droid.MARKET_TEXT
            try:
                self.engine.start(text)  # no-op if the service is already running
            except Exception as e:  # e.g. Android refusing a start while the app is in the background
                log.debug("Couldn't start the background checks: %s", e)

    def thumb_source(self, item_id: int) -> str:
        return str(self.thumbs.path(item_id)) if self.thumbs.cached(item_id) else ""

    def trade_item_row(self, item) -> ItemRow:
        parts = [f"Value {item.value:,}", f"RAP {item.rap:,}"]
        if item.serial:
            parts.append(f"#{item.serial}")
        if item.projected:
            parts.append(f"[color={P.WARN}]Projected[/color]")
        return ItemRow(thumb=self.thumb_source(item.asset_id), name=item.name, value="  ·  ".join(parts),
                       warn=item.projected)

    def _on_new_intent(self, intent):
        """A notification was tapped while the app was already open."""
        tab, kind = droid.opened_tab(intent), droid.opened_trades_list(intent)
        if tab:
            Clock.schedule_once(lambda *_: self.open_tab_from_notification(tab, kind), 0)

    def open_tab_from_notification(self, tab: str, kind: str = "inbound"):
        if tab == "trades":  # a trade alert: show the trades list (not the Roblox page) it's about
            self.sync_direct_trades()
            trades = self.sm.get_screen("trades")
            trades.page, trades.kind = False, kind
            trades._loaded_at = 0.0
            if self.sm.current == "trades":
                trades.apply_view()
        self.switch_tab(tab)

    def notice(self, title: str, message: str, buttons=(("OK", None),)):
        Notice(title, message, buttons).open()

    def toast(self, message: str):
        Notice("", message).open()
        Clock.schedule_once(lambda *_: [w.dismiss() for w in Window.children if isinstance(w, Notice)], 0.9)

    # ---- status ------------------------------------------------------------
    def tick(self, *_):
        status = runner.read_status(HOME)
        now = time.time()
        starting = now - self._start_requested_at < 25 and not status.get("running")
        self.running = bool(status.get("running")) or starting
        history = PostHistory(state_path())
        count = f"{history.count_24h()} of {self.cfg.max_ads_per_24h} posted in the last 24h"
        if status.get("running"):
            nxt = f"Next: {status['next_ad']}  ·  " if status.get("next_ad") else ""
            if status.get("wait_until"):
                self.status_title = f"Next ad in {fmt_duration(max(0, status['wait_until'] - now))}"
                self.status_detail = f"{nxt}{str(status.get('status_text', '')).capitalize()}  ·  {count}"
            else:
                self.status_title = str(status.get("status_text") or "Posting").capitalize()
                self.status_detail = f"{nxt}{count}"
        elif starting:
            self.status_title, self.status_detail = "Starting...", count
        else:
            self.status_title, self.status_detail = "Stopped", f"Ready when you are  ·  {count}"
            if self._stop_requested_at:
                self._stop_requested_at = 0.0
            error = status.get("error")
            if error and not status.get("stopped_by_user") and status.get("updated") != self._last_error_seen \
                    and self._start_requested_at:
                self._last_error_seen = status.get("updated")
                self._start_requested_at = 0.0
                self.notice(status.get("error_title") or "Posting stopped", error)
        if self._stop_requested_at and now - self._stop_requested_at > 12 and status.get("running"):
            self.engine.stop_service()  # didn't respond to the stop command
            self._stop_requested_at = 0.0
        if status.get("unavailable") is not None and status.get("unavailable") != getattr(self, "_unavail", None):
            self._unavail = status.get("unavailable")
            self.refresh_ads()
        if self.cfg.app.direct_trades and now - self._direct_checked_at > 3:
            self.sync_direct_trades()  # picks up signing in (or out) on the Roblox page
        if self.login and self.login.is_open:
            found = clean_cookie(self.login.poll_cookie() or "")
            if looks_like_cookie(found):
                self.login.close()
                self.save_cookie(found, from_login=True)

    def toggle_run(self):
        if self.running:
            runner.send_command(HOME, "stop")
            runner.set_want_running(HOME, False)
            self._stop_requested_at = time.time()
            self._start_requested_at = 0.0
            self.status_title = "Stopping..."
            return
        problems = []
        try:
            if not get_cookie():
                problems.append("Sign in to Rolimons (or paste your cookie) first.")
        except ValueError:
            problems.append("Your saved cookie looks wrong. Set it again.")
        problems += [p for p in validate_config(self.cfg) if not p.startswith("roblox_user_id")]
        if self.cfg.roblox_user_id <= 0:
            problems.append("Your Roblox user ID is missing. Setting the cookie fills it in.")
        if problems:
            return self.notice("Before you start", "\n\n".join(problems))
        droid.request_notification_permission()
        runner.set_want_running(HOME, True)
        self._start_requested_at = time.time()
        self.engine.start()

    def skip(self):
        runner.send_command(HOME, "skip")
        self.toast("Skipping to the next ad")

    # ---- account -----------------------------------------------------------
    def update_cookie_status(self):
        try:
            cookie = get_cookie()
        except ValueError:
            cookie = None
        info = cookie_info(cookie) if cookie else None
        if not cookie:
            self.cookie_text, self.cookie_state = "Not set", "bad"
        elif info and info.expired:
            self.cookie_text, self.cookie_state = "Expired: sign in again", "bad"
        elif info and info.expires_at:
            who = f"{info.player_name}  ·  " if info.player_name else ""
            soon = info.expires_at - time.time() < COOKIE_WARN_DAYS * 86400
            self.cookie_text = f"{who}expires {time.strftime('%d %b %Y', time.localtime(info.expires_at))}"
            self.cookie_state = "warn" if soon else "ok"
        else:
            self.cookie_text, self.cookie_state = "Saved", "ok"

    def save_cookie(self, pasted: str, from_login: bool = False) -> bool:
        value = clean_cookie(pasted)
        if not looks_like_cookie(value):
            self.notice("Cookie", "Couldn't find a Rolimons cookie in that. Copy the _RoliVerification value "
                                  "(it starts with \"eyJ\").")
            return False
        info = cookie_info(value)
        if info and info.expired:
            self.notice("Cookie", "That cookie has already expired.")
            return False
        save_env_value(env_path(), COOKIE_ENV_VAR, value)
        REDACTOR.add_secret(value)
        if info and info.player_id and info.player_id != self.cfg.roblox_user_id:
            self.cfg.roblox_user_id = info.player_id
            self.inventory = None
            self.persist()
            droid.push_social_alerts(self.cfg)  # follower alerts watch this account
            threading.Thread(target=self._load_inventory, daemon=True).start()
        self.update_cookie_status()
        who = f" as {info.player_name}" if info and info.player_name else ""
        self.notice("Signed in" if from_login else "Cookie saved", f"You're all set{who}.")
        return True

    def sign_in(self):
        if not droid.RolimonsLogin.available:
            return self.show("cookie")
        self.login = droid.RolimonsLogin(on_cookie=None, on_close=lambda: None)
        self.login.open()
        self.toast("Log in and verify on Rolimons. This closes by itself once you're verified.")

    def _first_run_checks(self):
        try:
            cookie = get_cookie()
        except ValueError:
            cookie = None
        info = cookie_info(cookie) if cookie else None
        if info and info.expires_at and not info.expired and self.cfg.app.notifications:
            days = (info.expires_at - time.time()) / 86400
            if days < COOKIE_WARN_DAYS:
                droid.notify("Rolimons cookie expiring soon",
                             f"Your cookie expires in {max(1, round(days * 24))} hours. Sign in again to keep posting.")
        tab, kind = droid.opened_tab(), droid.opened_trades_list()  # opened by tapping one of our notifications
        if tab:
            self.open_tab_from_notification(tab, kind)
        screen = droid.launch_extra("screen")
        if screen == "edit" and self.cfg.ads:
            self.edit_ad(0)
        elif screen in ALL_TABS:
            self.switch_tab(screen)
        elif screen in ("cookie", "help"):
            self.show(screen)
        if droid.launch_extra("search") and self.cfg.ads:
            self.sm.get_screen("edit").open_picker("offer")
            self.show("picker")
            self.sm.get_screen("picker").ids.search.text = droid.launch_extra("search")
        if droid.launch_extra("autostart") == "1":
            self.toggle_run()
        if droid.launch_extra("login") == "1":
            self.sign_in()
        if droid.launch_extra("selftest") == "1":
            from selftest import SelfTest
            self._selftest = SelfTest(self, HOME)  # keep a reference: Kivy's Clock only holds weak ones
            self._selftest.start()

    # ---- ads ---------------------------------------------------------------
    def _short(self, item_id: int) -> str:
        item = self.catalog.get(item_id) if self.catalog else None
        return (item.acronym or item.name) if item else str(item_id)

    def refresh_ads(self):
        box = self.sm.get_screen("home").ids.ads_box
        box.clear_widgets()
        unavailable = getattr(self, "_unavail", None) or (
            {a.name: m for a in self.cfg.ads if (m := missing_offer_items(a, self.inventory))}
            if self.cfg.skip_unowned_items else {})
        for i, ad in enumerate(self.cfg.ads):
            offer = ", ".join(self._short(x) for x in ad.offer_item_ids)
            want = ", ".join([self._short(x) for x in ad.request_item_ids] + ad.request_tags)
            warned = ad.enabled and ad.name in unavailable
            card = AdCard(title=ad.name, summary=f"{offer}  for  {want}", active=ad.enabled, warned=warned,
                          badge="Item not owned: skipped" if warned else ("On" if ad.enabled else "Off"))
            card.bind(on_release=lambda _c, n=i: self.edit_ad(n))
            card.bind(on_toggle=lambda _c, value, n=i: self.set_enabled(n, value))
            box.add_widget(card)
        on = len(self.cfg.enabled_ads())
        self.ads_count = f"{len(self.cfg.ads)} total · {on} on" if self.cfg.ads else ""

    def set_enabled(self, index: int, value: bool):
        if self.cfg.ads[index].enabled != value:
            self.cfg.ads[index].enabled = value
            Clock.schedule_once(lambda *_: self.persist(), 0)

    def new_ad(self):
        n = len(self.cfg.ads) + 1
        while any(a.name == f"Ad {n}" for a in self.cfg.ads):
            n += 1
        self.sm.get_screen("edit").load(-1, Ad(name=f"Ad {n}"))
        self.show("edit")

    def edit_ad(self, index: int):
        self.sm.get_screen("edit").load(index, self.cfg.ads[index])
        self.show("edit")

    # ---- items ---------------------------------------------------------------
    def item_row(self, item_id: int, warn: bool = False) -> ItemRow:
        item = self.catalog.get(item_id) if self.catalog else None
        thumb = str(self.thumbs.path(item_id)) if self.thumbs.cached(item_id) else ""
        return ItemRow(thumb=thumb, warn=warn, name=item.label if item else f"Item {item_id}",
                       value=f"Value {item.default_value:,}" if item else "")

    def request_thumbs(self, item_ids: list[int]):
        # Each picture is tried once per session, so a failed download can't trigger endless refetches.
        wanted = [i for i in item_ids if not self.thumbs.cached(i) and i not in self._thumb_tried]
        if not wanted:
            return
        self._thumb_tried.update(wanted)

        def work():
            try:
                self.thumbs.fetch(requests.Session(), wanted)
            except Exception:
                pass
            self._thumbs_ready(wanted)
        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def _thumbs_ready(self, ids):
        if self.sm.current == "edit":
            self.sm.get_screen("edit").refresh()
        elif self.sm.current == "trades":
            self.sm.get_screen("trades").refresh_thumbs()
        elif self.sm.current == "trade":
            self.sm.get_screen("trade").refresh()
        elif self.sm.current == "picker":
            self.sm.get_screen("picker").search()
        elif self.sm.current == "items":
            self.sm.get_screen("items").refresh()
        elif self.sm.current == "market" and self.sm.get_screen("market").mode == "items":
            self.sm.get_screen("market").show_items()
        elif self.sm.current == "item":
            self.sm.get_screen("item").refresh()

    def owned_counts(self) -> dict[int, int] | None:
        """Item ID -> copies you own, or None when your Rolimons inventory isn't known (or is private)."""
        if self.inventory is None or self.inventory.private:
            return None
        return self.inventory.counts

    def _load_catalog(self):
        for attempt in range(4):
            try:
                self._catalog_ready(fetch_catalog(requests.Session()))
                break
            except Exception:
                time.sleep(5 * (attempt + 1))
        self._load_inventory()

    @mainthread
    def _catalog_ready(self, catalog):
        self.catalog = catalog
        self.refresh_ads()

    def _load_inventory(self):
        if self.cfg.roblox_user_id > 0:
            try:
                self._inventory_ready(fetch_inventory(requests.Session(), self.cfg.roblox_user_id))
            except Exception:
                pass

    @mainthread
    def _inventory_ready(self, inventory):
        self.inventory = inventory
        self.refresh_ads()
        if self.sm.current == "items":
            self.sm.get_screen("items").refresh()
        elif self.sm.current == "picker":
            self.sm.get_screen("picker").search()

    def load_portfolio(self, force: bool = False):
        """Items tab: refreshes your inventory, value history and current prices (at most every 10 minutes)."""
        if self.cfg.roblox_user_id <= 0 or (not force and time.time() - self._portfolio_at < 600):
            return
        self._portfolio_at = time.time()
        user_id = self.cfg.roblox_user_id

        def work():
            session = requests.Session()
            self._load_inventory()
            try:
                history, status = fetch_history(session, user_id), ""
            except Exception as e:
                log.warning("Couldn't load value history: %s", e)
                history, status = None, "Couldn't load your value history from Rolimons. Tap Reload to try again."
            try:
                prices = fetch_best_prices(session)
            except Exception as e:
                log.warning("Couldn't load current prices: %s", e)
                prices = None
            self._history_ready(history, status, prices)
        threading.Thread(target=work, daemon=True).start()

    @mainthread
    def _history_ready(self, history, status: str, prices=None):
        if history is not None or self.value_history is None:
            self.value_history = history
        if prices is not None:
            self.best_prices = prices
        self.history_status = status
        if history is None or prices is None:
            self._portfolio_at = 0.0  # try again next time the tab opens
        if self.sm.current == "items":
            self.sm.get_screen("items").refresh()

    def _check_updates(self):
        try:
            found = check_for_update(requests.Session())
        except Exception:
            return
        if found:
            self._update_found(*found)

    @mainthread
    def _update_found(self, version: str, url: str):
        self.update_text = f"Version {version} is available (you have {__version__})."
        self._update_url = url

    def open_update(self):
        droid.open_url(self._update_url or "https://github.com/rxst0/LimiTools/releases/latest")


if __name__ == "__main__":
    RoliApp().run()
