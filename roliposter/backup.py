"""Backup and restore of ads, settings and the watchlist (Android and Windows, same file format).

Left out on purpose: the Rolimons cookie, the stored Roblox sign-in and the AI API key. They live in .env and
the Android keystore, not in config.json, and a backup file can end up anywhere (Discord, a cloud drive).
"""
import copy
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import __version__
from .config import Ad, Config, ConfigError, config_from_dict

FORMAT = 1
MAX_SIZE = 5 * 1024 * 1024


class BackupError(Exception):
    """A plain-English reason a file can't be restored."""


@dataclass
class Backup:
    config: Config
    price_history: list = field(default_factory=list)  # [[unix time, total price], ...] (Items chart)
    created: float = 0.0
    app_version: str = ""


def make_backup(cfg: Config, price_history: list | None = None, now: float | None = None) -> str:
    data = {"app": "LimiTools", "format": FORMAT, "created": now or time.time(), "version": __version__,
            "config": asdict(cfg), "price_history": price_history or []}
    return json.dumps(data, indent=1)


def backup_filename(now: float | None = None) -> str:
    return time.strftime("LimiTools-backup-%Y-%m-%d.json", time.localtime(now or time.time()))


def parse_backup(text: str) -> Backup:
    if len(text) > MAX_SIZE:
        raise BackupError("That file is too big to be a LimiTools backup.")
    try:
        data = json.loads(text)
    except ValueError:
        raise BackupError("That file isn't a LimiTools backup (it isn't valid JSON).") from None
    if not isinstance(data, dict) or data.get("app") not in ("LimiTools", "Rolimons Ad Poster") \
            or not isinstance(data.get("config"), dict):
        raise BackupError("That file isn't a LimiTools backup.")
    if int(data.get("format", 1)) > FORMAT:
        raise BackupError("That backup was made by a newer version of LimiTools. Update the app first.")
    try:
        cfg = config_from_dict(data["config"])
    except ConfigError as e:
        raise BackupError(f"That backup's settings couldn't be read: {e}") from None
    history = [p for p in data.get("price_history") or [] if isinstance(p, list) and len(p) == 2]
    return Backup(cfg, history, float(data.get("created") or 0), str(data.get("version") or ""))


def summary(backup: Backup) -> str:
    cfg = backup.config
    parts = [f"{len(cfg.ads)} ad{'s' if len(cfg.ads) != 1 else ''}",
             f"{len(cfg.market.watchlist)} watched item{'s' if len(cfg.market.watchlist) != 1 else ''}"]
    when = time.strftime("%d %b %Y", time.localtime(backup.created)) if backup.created else "an unknown date"
    version = f" (LimiTools {backup.app_version})" if backup.app_version else ""
    return f"{', '.join(parts)}, and settings from {when}{version}."


def apply_backup(current: Config, backup: Backup, mode: str) -> Config:
    """"replace": everything from the backup. "add": keep your settings and add the backup's ads and watched
    items. Your Roblox user ID stays (it comes from your Rolimons sign-in, which isn't in backups)."""
    if mode == "replace":
        cfg = copy.deepcopy(backup.config)
        if current.roblox_user_id > 0:
            cfg.roblox_user_id = current.roblox_user_id
        return cfg
    if mode != "add":
        raise ValueError(mode)
    cfg = copy.deepcopy(current)
    names = {a.name for a in cfg.ads}
    for ad in backup.config.ads:
        if any(_same_ad(ad, mine) for mine in cfg.ads):
            continue
        new = copy.deepcopy(ad)
        base, n = new.name, 2
        while new.name in names:
            new.name, n = f"{base} ({n})", n + 1
        names.add(new.name)
        cfg.ads.append(new)
    for item_id, discount in backup.config.market.watchlist.items():
        cfg.market.watchlist.setdefault(item_id, discount)
    return cfg


def _same_ad(a: Ad, b: Ad) -> bool:
    return (sorted(a.offer_item_ids), sorted(a.request_item_ids), sorted(a.request_tags)) == \
        (sorted(b.offer_item_ids), sorted(b.request_item_ids), sorted(b.request_tags))


def merge_price_history(current: list, restored: list) -> list:
    """One point per day; your own newer readings win."""
    by_day = {}
    for t, v in list(restored) + list(current):
        by_day[int(float(t) // 86400)] = [float(t), int(v)]
    return sorted(by_day.values())[-800:]


def save_safety_copy(folder: Path, cfg: Config, price_history: list | None = None) -> Path:
    """Saved automatically before a restore, so a wrong restore can be undone."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / time.strftime("before-restore-%Y%m%d-%H%M%S.json")
    path.write_text(make_backup(cfg, price_history), encoding="utf-8")
    copies = sorted(folder.glob("before-restore-*.json"))
    for old in copies[:-5]:  # keep the last five
        old.unlink(missing_ok=True)
    return path
