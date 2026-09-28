from kivy.app import App
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.screenmanager import Screen

from api import client
from utils import run_async


class LoginScreen(Screen):
    status = StringProperty("")
    busy = BooleanProperty(False)

    def on_pre_enter(self, *args):
        self.status = ""
        self.ids.password_input.text = ""

    def do_login(self):
        if self.busy:
            return
        username = self.ids.username_input.text.strip()
        password = self.ids.password_input.text
        if not username or not password:
            self.status = "Please enter your username and password."
            return
        self.status = ""
        self.busy = True
        run_async(lambda: client.login(username, password),
                  self._on_success, self._on_error)

    def _on_success(self, _result):
        self.busy = False
        App.get_running_app().go("contacts")

    def _on_error(self, error):
        self.busy = False
        self.status = str(error)
