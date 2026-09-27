"""Histórico e configuração em ~/.tabuada (ou TABUADA_HOME)."""

import json
import os
import sys
import time
from pathlib import Path

DEFAULT_CONFIG = {
    "last": {"tabelas": list(range(1, 13)), "n": 20, "tempo": None,
             "min": 1, "max": 12, "foco": False},
    "show_shortcuts": True,
}


def home():
    return Path(os.environ.get("TABUADA_HOME") or Path.home() / ".tabuada")


def _read(name, default):
    path = home() / name
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        backup = path.with_name("%s.corrompido-%d" % (name, int(time.time())))
        try:
            path.rename(backup)
            print("Aviso: %s estava ilegível e foi movido para %s." % (path, backup),
                  file=sys.stderr)
        except OSError:
            pass
        return default


def _write(name, data):
    folder = home()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    tmp = path.with_name(name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def load_history():
    return _read("history.json", {"sessions": []}).get("sessions", [])


def add_session(session):
    sessions = load_history()
    session["id"] = (sessions[-1]["id"] + 1) if sessions else 1
    sessions.append(session)
    _write("history.json", {"sessions": sessions})
    return session["id"]


def reset_history():
    _write("history.json", {"sessions": []})


def load_config():
    cfg = _read("config.json", {})
    merged = {"last": dict(DEFAULT_CONFIG["last"]),
              "show_shortcuts": DEFAULT_CONFIG["show_shortcuts"]}
    merged["last"].update(cfg.get("last") or {})
    if "show_shortcuts" in cfg:
        merged["show_shortcuts"] = bool(cfg["show_shortcuts"])
    return merged


def save_config(cfg):
    _write("config.json", cfg)


def update_config(**changes):
    cfg = load_config()
    cfg.update(changes)
    save_config(cfg)
    return cfg
