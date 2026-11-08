import json

import pytest

from roliposter.backup import (BackupError, apply_backup, backup_filename, make_backup, merge_price_history,
                               parse_backup, save_safety_copy, summary)
from roliposter.config import Ad, Config

DAY = 86400


def _config() -> Config:
    cfg = Config(roblox_user_id=123)
    cfg.ads = [Ad("Dom ad", offer_item_ids=[1], request_tags=["upgrade"]),
               Ad("Valk ad", offer_item_ids=[2], request_item_ids=[3])]
    cfg.market.watchlist = {1365767: 15.0}
    cfg.app.hidden_tabs = ["auto"]
    cfg.auto_accept.min_value_gain = 20.0
    return cfg


def test_round_trip_keeps_everything():
    text = make_backup(_config(), [[DAY, 100]], now=1_800_000_000)
    b = parse_backup(text)
    assert b.config == _config()
    assert b.price_history == [[DAY, 100]] and b.created == 1_800_000_000
    assert "2 ads, 1 watched item, and settings from" in summary(b)


def test_backup_has_no_secrets(monkeypatch):
    monkeypatch.setenv("ROLI_VERIFICATION", "eyJsecret.cookie.value")
    monkeypatch.setenv("AI_KEY_CLAUDE", "sk-ant-secret")
    text = make_backup(_config())
    assert "secret" not in text and "ROLI_VERIFICATION" not in text and "AI_KEY" not in text


@pytest.mark.parametrize("text,message", [
    ("not json", "valid JSON"),
    (json.dumps({"app": "Something else", "config": {}}), "isn't a LimiTools backup"),
    (json.dumps({"app": "LimiTools", "format": 99, "config": {}}), "newer version"),
    (json.dumps({"app": "LimiTools", "config": {"ads": "nope"}}), "couldn't be read"),
])
def test_bad_files_are_explained(text, message):
    with pytest.raises(BackupError, match=message):
        parse_backup(text)


def test_replace_keeps_your_roblox_id():
    restored = parse_backup(make_backup(_config()))
    current = Config(roblox_user_id=999)
    cfg = apply_backup(current, restored, "replace")
    assert cfg.roblox_user_id == 999 and len(cfg.ads) == 2 and cfg.app.hidden_tabs == ["auto"]
    assert apply_backup(Config(), restored, "replace").roblox_user_id == 123


def test_add_merges_ads_and_watchlist_without_duplicates():
    restored = parse_backup(make_backup(_config()))
    current = Config(roblox_user_id=5)
    current.ads = [Ad("Dom ad", offer_item_ids=[9], request_tags=["any"]),          # same name, different ad
                   Ad("Mine", offer_item_ids=[2], request_item_ids=[3])]            # same ad as "Valk ad"
    current.market.watchlist = {1365767: 30.0}
    current.app.hidden_tabs = ["history"]
    cfg = apply_backup(current, restored, "add")
    assert [a.name for a in cfg.ads] == ["Dom ad", "Mine", "Dom ad (2)"]
    assert cfg.market.watchlist == {1365767: 30.0}       # yours wins
    assert cfg.app.hidden_tabs == ["history"]            # your settings stay
    assert current.ads[0].name == "Dom ad" and len(current.ads) == 2  # not changed in place


def test_price_history_merge_and_safety_copies(tmp_path):
    assert merge_price_history([[DAY + 5, 200]], [[DAY + 1, 100], [2 * DAY, 300]]) == [[DAY + 5, 200], [2 * DAY, 300]]
    for _ in range(7):
        path = save_safety_copy(tmp_path, _config())
        path.rename(path.with_name(path.stem + f"-{_}.json"))  # unique names despite the same second
    assert len(list(tmp_path.glob("before-restore-*.json"))) <= 7
    assert parse_backup(path.with_name(path.stem + "-6.json").read_text(encoding="utf-8")).config == _config()


def test_filename():
    assert backup_filename(1_800_000_000).startswith("LimiTools-backup-") and backup_filename().endswith(".json")
