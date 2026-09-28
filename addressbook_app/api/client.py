"""HTTP client for the AddressBook backend (JWT auth)."""

import requests

from config import API_BASE_URL, REQUEST_TIMEOUT
from api import token_storage


class ApiError(Exception):
    """Raised for any failed API call. `status` is the HTTP code (or None)."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def _extract_error(resp):
    try:
        data = resp.json()
    except ValueError:
        return "Server error (%s)" % resp.status_code
    if isinstance(data, dict):
        if "detail" in data:
            return str(data["detail"])
        parts = []
        for field, msgs in data.items():
            if isinstance(msgs, (list, tuple)):
                msgs = ", ".join(str(m) for m in msgs)
            label = "" if field == "non_field_errors" else field.capitalize() + ": "
            parts.append(label + str(msgs))
        return "\n".join(parts)
    return str(data)


def _refresh_access_token():
    """Try to get a new access token. Returns True on success."""
    refresh = token_storage.get_refresh()
    if not refresh:
        return False
    try:
        resp = requests.post(
            API_BASE_URL.rstrip("/") + "/api/auth/refresh/",
            json={"refresh": refresh},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        return False
    if not resp.ok:
        return False
    data = resp.json()
    token_storage.save_token(data["access"], data.get("refresh"))
    return True


def _request(method, path, auth=True, **kwargs):
    url = API_BASE_URL.rstrip("/") + path

    def send():
        headers = {}
        if auth:
            headers["Authorization"] = "Bearer " + (token_storage.get_access() or "")
        return requests.request(
            method, url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs
        )

    try:
        resp = send()
        if resp.status_code == 401 and auth:
            if _refresh_access_token():
                resp = send()
            else:
                token_storage.clear_token()
                raise ApiError("Your session has expired. Please log in again.", 401)
    except requests.exceptions.Timeout:
        raise ApiError("The server took too long to respond. Please try again.")
    except requests.exceptions.RequestException:
        raise ApiError("Cannot reach the server. Check your internet connection.")

    if not resp.ok:
        raise ApiError(_extract_error(resp), resp.status_code)
    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()


# ---------- auth ----------

def register(username, password, email=""):
    return _request(
        "POST", "/api/auth/register/", auth=False,
        json={"username": username, "password": password, "email": email},
    )


def login(username, password):
    data = _request(
        "POST", "/api/auth/login/", auth=False,
        json={"username": username, "password": password},
    )
    token_storage.save_token(data["access"], data["refresh"], username)
    return data


def delete_account():
    _request("DELETE", "/api/auth/delete/")
    token_storage.clear_token()


# ---------- contacts ----------

def get_contacts():
    return _request("GET", "/api/contacts/")


def add_contact(data):
    return _request("POST", "/api/contacts/", json=data)


def update_contact(contact_id, data):
    return _request("PUT", "/api/contacts/%s/" % contact_id, json=data)


def delete_contact(contact_id):
    return _request("DELETE", "/api/contacts/%s/" % contact_id)


def search_contacts(query):
    return _request("GET", "/api/contacts/search/", params={"q": query})
