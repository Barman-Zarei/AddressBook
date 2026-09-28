from kivy.app import App
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.screenmanager import Screen

from api import client
from api.client import ApiError
from utils import run_async

FIELDS = ("name", "phone", "email", "city", "address")


class AddEditContactScreen(Screen):
    title_text = StringProperty("New Contact")
    status = StringProperty("")
    busy = BooleanProperty(False)
    contact_id = None

    def prepare(self, contact=None):
        """Call before showing the screen. contact=None means 'add new'."""
        self.status = ""
        self.busy = False
        self.contact_id = contact["id"] if contact else None
        self.title_text = "Edit Contact" if contact else "New Contact"
        for field in FIELDS:
            self.ids[field + "_input"].text = (contact or {}).get(field, "") or ""

    def save(self):
        if self.busy:
            return
        data = {f: self.ids[f + "_input"].text.strip() for f in FIELDS}

        if not data["name"]:
            self.status = "Name is required."
            return
        if not data["phone"]:
            self.status = "Phone number is required."
            return
        digits = data["phone"].replace("+", "").replace("-", "").replace(" ", "")
        if not digits.isdigit() or len(digits) < 5:
            self.status = "Please enter a valid phone number."
            return
        if data["email"] and ("@" not in data["email"]
                              or "." not in data["email"].split("@")[-1]):
            self.status = "Please enter a valid email address."
            return

        self.status = ""
        self.busy = True
        if self.contact_id:
            work = lambda: client.update_contact(self.contact_id, data)
        else:
            work = lambda: client.add_contact(data)
        run_async(work, self._on_saved, self._on_error)

    def _on_saved(self, _result):
        self.busy = False
        App.get_running_app().go("contacts")

    def _on_error(self, error):
        self.busy = False
        if isinstance(error, ApiError) and error.status == 401:
            App.get_running_app().force_logout()
        else:
            self.status = str(error)
