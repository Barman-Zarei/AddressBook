from kivy.app import App
from kivy.properties import (BooleanProperty, ListProperty, NumericProperty,
                             StringProperty)
from kivy.uix.screenmanager import Screen

from api import client
from api.client import ApiError
from utils import run_async
from widgets import AVATAR_COLORS, Card


class ContactCard(Card):
    """One contact row. Used by both the list and the search screens."""
    contact_id = NumericProperty(0)
    name = StringProperty("")
    subtitle = StringProperty("")
    initial = StringProperty("?")
    avatar_color = ListProperty(AVATAR_COLORS[0])

    def __init__(self, contact, on_deleted, **kwargs):
        super().__init__(**kwargs)
        self.contact = contact
        self.on_deleted = on_deleted
        self.contact_id = contact["id"]
        self.name = contact["name"]
        parts = [contact.get("phone", ""), contact.get("city", "")]
        self.subtitle = "  |  ".join(p for p in parts if p)
        self.initial = contact["name"][:1].upper() or "?"
        self.avatar_color = AVATAR_COLORS[contact["id"] % len(AVATAR_COLORS)]

    def edit(self):
        App.get_running_app().open_editor(self.contact)

    def delete(self):
        App.get_running_app().confirm_delete(self.contact, self.on_deleted)


class ContactListScreen(Screen):
    status = StringProperty("")
    count_text = StringProperty("")
    empty_text = StringProperty("")
    busy = BooleanProperty(False)

    def on_pre_enter(self, *args):
        self.load_contacts()

    def load_contacts(self):
        self.status = ""
        self.empty_text = ""
        self.count_text = "Loading..."
        self.busy = True
        run_async(client.get_contacts, self._on_loaded, self._on_error)

    def _on_loaded(self, contacts):
        self.busy = False
        grid = self.ids.contact_grid
        grid.clear_widgets()
        for contact in contacts:
            grid.add_widget(ContactCard(contact, on_deleted=self.load_contacts))
        self.count_text = "%d contact%s" % (len(contacts), "" if len(contacts) == 1 else "s")
        self.empty_text = "" if contacts else "No contacts yet.\nTap + to add your first one."

    def _on_error(self, error):
        self.busy = False
        self.count_text = ""
        if isinstance(error, ApiError) and error.status == 401:
            App.get_running_app().force_logout()
        else:
            self.status = str(error)
