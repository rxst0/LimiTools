"""Guards for the Android app's Roblox sign-in handling.

Everything runs in one process and pyjnius can call any Java method, so access modifiers don't stop the
Python side from accepting trades or reading the stored cookie. What keeps it from happening is that no
Python code asks: these tests fail if any of it ever does.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON_FILES = sorted(p for d in ("android", "roliposter") for p in (ROOT / d).rglob("*.py")
                      if ".buildozer" not in p.parts and ".devdata" not in p.parts)


def _source() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in PYTHON_FILES)


def test_python_files_found():
    assert any(p.name == "droid.py" for p in PYTHON_FILES)


def test_python_never_accepts_trades():
    assert not re.search(r"\.accept\s*\(", _source()), "only org.roliposter.AutoAccept may accept a trade"


def test_python_never_reads_the_roblox_sign_in():
    src = _source()
    assert not re.search(r"RobloxSession[^\n]*\.get\s*\(", src)
    # Reading cookies is fine for Rolimons (its sign-in), never for Roblox.
    assert not re.search(r"getCookie\([^)]*roblox", src, re.I)


def test_python_only_uses_the_allowed_roblox_requests():
    kinds = set(re.findall(r'RobloxDirect\.fetch\(\s*"([a-z]+)"', _source()))
    assert kinds <= {"list", "trade"}, kinds


def _defs_calling(path: Path, call: str) -> list[str]:
    """Names of the functions in `path` whose body contains `call`."""
    import ast
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if call in ast.get_source_segment(path.read_text(encoding="utf-8"), node):
                names.append(node.name)
    return names


def test_trades_are_sent_only_after_confirming_or_by_auto_send():
    """Sending goes through droid.send_trade (Java TradeSender holds the sign-in). Its only callers: the
    trade ad screen's _send, which only the confirmation dialog's Send button calls, and auto-send in the
    background service (which checks the auto-send settings)."""
    callers = {p.name for p in PYTHON_FILES if "send_trade(" in p.read_text(encoding="utf-8")
               and "def send_trade(" not in p.read_text(encoding="utf-8")}
    assert callers == {"main.py", "service.py"}, callers
    assert not any("TradeSender" in p.read_text(encoding="utf-8") for p in PYTHON_FILES if p.name != "droid.py")
    main = ROOT / "android" / "main.py"
    assert set(_defs_calling(main, "droid.send_trade(")) <= {"_send", "work"}
    src = main.read_text(encoding="utf-8")
    assert src.count("self._send(") == 1 and '("Send", lambda: self._send(match))' in src
    service = ROOT / "android" / "service.py"
    assert _defs_calling(service, "droid.send_trade(") == ["handle_matches"]
    body = service.read_text(encoding="utf-8")
    assert 'al.auto_mode != "live"' in body and "auto_sends_today() < al.max_sends_per_day" in body
