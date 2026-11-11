from dataclasses import asdict

from roliposter.config import Config, config_from_dict, validate_config


def test_auto_accept_defaults_off_in_test_mode():
    aa = config_from_dict({}).auto_accept
    assert aa.enabled is False and aa.mode == "test" and aa.block_projected is True
    assert aa.min_value_gain == 10.0 and aa.min_rap_gain is None and aa.max_per_day == 5


def test_auto_accept_round_trips_and_empty_gain_means_unchecked():
    cfg = config_from_dict({"auto_accept": {"enabled": True, "mode": "LIVE", "min_value_gain": 15,
                                            "min_rap_gain": "", "min_price_gain": 5, "max_per_day": 2}})
    aa = cfg.auto_accept
    assert (aa.enabled, aa.mode, aa.min_value_gain, aa.min_rap_gain, aa.min_price_gain, aa.max_per_day) == \
        (True, "live", 15.0, None, 5.0, 2)
    assert config_from_dict(asdict(cfg)).auto_accept == aa


def test_auto_accept_validation():
    def problems(**aa):
        cfg = Config()
        for key, value in aa.items():
            setattr(cfg.auto_accept, key, value)
        return [e for e in validate_config(cfg) if "uto" in e]

    assert problems() == []
    assert problems(mode="yolo")
    assert problems(max_per_day=500)
    assert problems(min_value_gain=5000)
    assert problems(enabled=True, min_value_gain=None)  # at least one rule needed


def test_ai_settings_default_off_and_round_trip():
    cfg = config_from_dict({})
    assert (cfg.ai.enabled, cfg.ai.provider, cfg.ai.model) == (False, "claude", "")
    cfg = config_from_dict({"ai": {"enabled": True, "provider": "OpenAI", "model": " gpt-5 "}})
    assert (cfg.ai.enabled, cfg.ai.provider, cfg.ai.model) == (True, "openai", "gpt-5")
    assert config_from_dict(asdict(cfg)).ai == cfg.ai
    cfg.ai.provider = "bard"
    assert any("ai.provider" in e for e in validate_config(cfg))


def test_social_alerts_defaults_round_trip_and_validation():
    cfg = config_from_dict({})
    sa = cfg.social_alerts
    assert (sa.enabled, sa.min_followers, sa.verified, sa.friend_requests, sa.follows) == (False, 1000, True, True, True)
    cfg = config_from_dict({"social_alerts": {"enabled": True, "min_followers": 50000, "follows": False}})
    assert config_from_dict(asdict(cfg)).social_alerts == cfg.social_alerts
    assert not [e for e in validate_config(cfg) if "Notable" in e]
    cfg.social_alerts.friend_requests = False
    assert any("pick friend requests" in e for e in validate_config(cfg))
    cfg.social_alerts.friend_requests, cfg.social_alerts.min_followers, cfg.social_alerts.verified = True, 0, False
    assert any("minimum follower count" in e for e in validate_config(cfg))


def test_market_settings_and_hidden_tabs_round_trip():
    import json
    cfg = config_from_dict({})
    assert cfg.market.watchlist == {} and cfg.app.hidden_tabs == [] and not cfg.market.new_limited_alerts
    cfg = config_from_dict({"market": {"new_limited_alerts": True, "max_price": 500, "watchlist": {"1365767": 15}},
                            "app": {"hidden_tabs": ["auto", "nonsense", "history"]}})
    assert cfg.market.watchlist == {1365767: 15.0} and cfg.app.hidden_tabs == ["auto", "history"]
    again = config_from_dict(json.loads(json.dumps(asdict(cfg))))  # how save_config writes it
    assert again.market == cfg.market and again.app.hidden_tabs == cfg.app.hidden_tabs
    cfg.market.watchlist[1] = 150
    assert any("Watchlist" in e for e in validate_config(cfg))


def test_check_speed_setting():
    assert config_from_dict({}).app.check_minutes == 2
    cfg = config_from_dict({"app": {"check_minutes": 15}})
    assert cfg.app.check_minutes == 15 and config_from_dict(asdict(cfg)).app.check_minutes == 15
    assert not [e for e in validate_config(cfg) if "check_minutes" in e]
    cfg.app.check_minutes = 7
    assert any("check_minutes" in e for e in validate_config(cfg))


def test_tracked_players_round_trip_and_limit():
    import json
    cfg = config_from_dict({"market": {"tracked_players": {"156": "builderman"}}})
    assert cfg.market.tracked_players == {156: "builderman"} and cfg.market.track_alerts is True
    assert config_from_dict(json.loads(json.dumps(asdict(cfg)))).market == cfg.market
    cfg.market.tracked_players = {i: f"p{i}" for i in range(21)}
    assert any("track at most" in e for e in validate_config(cfg))
