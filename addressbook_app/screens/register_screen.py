from kivy.app import App
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.screenmanager import Screen

from api import client
from utils import run_async


class RegisterScreen(Screen):
    status = StringProperty("")
    busy = BooleanProperty(False)

    def on_pre_enter(self, *args):
        self.status = ""
        for name in ("username_input", "email_input", "password_input", "confirm_input"):
            self.ids[name].text = ""

    def do_register(self):
        if self.busy:
            return
        username = self.ids.username_input.text.strip()
        email = self.ids.email_input.text.strip()
        password = self.ids.password_input.text
        confirm = self.ids.confirm_input.text

        if len(username) < 3:
            self.status = "Username must be at least 3 characters."
        elif email and ("@" not in email or "." not in email.split("@")[-1]):
            self.status = "Please enter a valid email address."
        elif len(password) < 6:
            self.status = "Password must be at least 6 characters."
        elif password != confirm:
            self.status = "Passwords do not match."
        else:
            self.status = ""
            self.busy = True

            def work():
                client.register(username, password, email)
                client.login(username, password)  # log in right after signing up

            run_async(work, self._on_success, self._on_error)

    def _on_success(self, _result):
        self.busy = False
        App.get_running_app().go("contacts")

    def _on_error(self, error):
        self.busy = False
        self.status = str(error)
