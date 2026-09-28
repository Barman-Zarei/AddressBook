"""Keeps the JWT tokens on the device so the user stays logged in."""

import json
import os

_path = None
_data = {}


def init(user_data_dir):
    """Call once at startup with App.user_data_dir."""
    global _path, _data
    _path = os.path.join(user_data_dir, "session.json")
    _data = {}
    if os.path.exists(_path):
        try:
            with open(_path, "r", encoding="utf-8") as f:
                _data = json.load(f)
        except (OSError, ValueError):
            _data = {}


def _write():
    if _path is None:
        return
    with open(_path, "w", encoding="utf-8") as f:
        json.dump(_data, f)


def save_token(access, refresh=None, username=None):
    _data["access"] = access
    if refresh:
        _data["refresh"] = refresh
    if username:
        _data["username"] = username
    _write()


def get_access():
    return _data.get("access")


def get_refresh():
    return _data.get("refresh")


def get_username():
    return _data.get("username")


def has_token():
    return bool(_data.get("access") and _data.get("refresh"))


def clear_token():
    _data.clear()
    _write()
