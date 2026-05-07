"""Persist named API keys on disk (app data dir, not the git repo)."""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

_FILE_VERSION = 1


def storage_path() -> Path:
    """User-writable folder + file for saved keys."""
    app = "quizhelper"
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            base = Path(local) / app
        else:
            base = Path.home() / "AppData" / "Local" / app
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / app
    else:
        base = Path.home() / ".config" / app
    base.mkdir(parents=True, exist_ok=True)
    return base / "saved_api_keys.json"


_STORAGE = storage_path()


def _default_shell() -> Dict[str, Any]:
    return {
        "version": _FILE_VERSION,
        "last_entry_id": None,
        "entries": [],
    }


def _read_shell() -> Dict[str, Any]:
    if not _STORAGE.exists():
        return _default_shell()
    try:
        raw = _STORAGE.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return _default_shell()
    if not isinstance(data, dict):
        return _default_shell()
    if data.get("version") != _FILE_VERSION:
        return _default_shell()
    entries = data.get("entries") or []
    if not isinstance(entries, list):
        entries = []
    normalized = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        eid = str(item.get("id") or "")
        label = str(item.get("label") or "").strip()
        key = str(item.get("api_key") or "")
        if eid and label and key:
            normalized.append({"id": eid, "label": label, "api_key": key})
    lid = data.get("last_entry_id")
    last = str(lid) if lid else None
    if last and not any(e["id"] == last for e in normalized):
        last = None
    return {
        "version": _FILE_VERSION,
        "last_entry_id": last,
        "entries": normalized,
    }


def _write_shell(data: Dict[str, Any]) -> None:
    _STORAGE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STORAGE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(_STORAGE)


def list_entries() -> List[Dict[str, str]]:
    return list(_read_shell()["entries"])


def get_last_entry_id() -> Optional[str]:
    return _read_shell().get("last_entry_id")


def set_last_entry_id(entry_id: Optional[str]) -> None:
    shell = _read_shell()
    if entry_id and not any(e["id"] == entry_id for e in shell["entries"]):
        entry_id = None
    shell["last_entry_id"] = entry_id
    _write_shell(shell)


def get_key_by_id(entry_id: str) -> Optional[str]:
    for e in list_entries():
        if e["id"] == entry_id:
            return e["api_key"]
    return None


def add_entry(label: str, api_key: str) -> Dict[str, str]:
    label = label.strip()
    key = api_key.strip()
    shell = _read_shell()
    entry = {"id": str(uuid.uuid4()), "label": label, "api_key": key}
    shell["entries"].append(entry)
    shell["last_entry_id"] = entry["id"]
    _write_shell(shell)
    return entry


def delete_entry(entry_id: str) -> bool:
    shell = _read_shell()
    shell["entries"] = [e for e in shell["entries"] if e["id"] != entry_id]
    if shell.get("last_entry_id") == entry_id:
        shell["last_entry_id"] = None
    _write_shell(shell)
    return True


def storage_location_hint() -> str:
    """For UI tooltips."""
    return str(_STORAGE)
