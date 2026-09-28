"""App configuration.

API_BASE_URL is the address of the AddressBook backend.
  - Local testing : "http://127.0.0.1:8000"
  - Production    : "https://YOUR-SERVICE-NAME.onrender.com"

Only the server address lives here. No database password is ever
stored in the app -- that is the whole point of the backend layer.
"""

API_BASE_URL = "https://addressbook-x2vp.onrender.com"

# Render's free tier can take up to ~1 minute to wake up after being idle.
REQUEST_TIMEOUT = 60
