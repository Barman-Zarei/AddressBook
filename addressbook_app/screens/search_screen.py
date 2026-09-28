from kivy.app import App
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.screenmanager import Screen

from api import client
from api.client import ApiError
from screens.contact_list_screen import ContactCard
from utils import run_async


class SearchScreen(Screen):
    status = StringProperty("")
    empty_text = StringProperty("")
    busy = BooleanProperty(False)

    def on_pre_enter(self, *args):
        self.status = ""
        self.empty_text = "Type a name, phone number or email."
        self.ids.query_input.text = ""
        self.ids.results_grid.clear_widgets()

    def do_search(self):
        query = self.ids.query_input.text.strip()
        if not query or self.busy:
            return
        self.status = ""
        self.empty_text = ""
        self.busy = True
        run_async(lambda: client.search_contacts(query),
                  self._on_results, self._on_error)

    def _on_results(self, contacts):
        self.busy = False
        grid = self.ids.results_grid
        grid.clear_widgets()
        for contact in contacts:
            grid.add_widget(ContactCard(contact, on_deleted=self.do_search))
        self.empty_text = "" if contacts else "No contacts match your search."

    def _on_error(self, error):
        self.busy = False
        if isinstance(error, ApiError) and error.status == 401:
            App.get_running_app().force_logout()
        else:
            self.status = str(error)
