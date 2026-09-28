"""AddressBook V7.9.0 -- Kivy client for the AddressBook backend."""

from kivy.app import App
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import FadeTransition, ScreenManager
from kivy.utils import platform

from api import client, token_storage
from api.client import ApiError
from screens.add_edit_screen import AddEditContactScreen
from screens.contact_list_screen import ContactListScreen
from screens.login_screen import LoginScreen
from screens.register_screen import RegisterScreen
from screens.search_screen import SearchScreen
from utils import run_async
from widgets import (C_DANGER, C_MUTED, C_TEXT, AppButton, confirm_popup,
                     info_popup, make_popup)

if platform in ("win", "linux", "macosx"):
    Window.size = (400, 720)  # phone-sized window when testing on a PC


class AddressBookApp(App):
    title = "AddressBook"

    def build(self):
        Window.softinput_mode = "below_target"
        Window.bind(on_keyboard=self._on_keyboard)
        token_storage.init(self.user_data_dir)

        self.sm = ScreenManager(transition=FadeTransition(duration=0.15))
        for screen_class in (LoginScreen, RegisterScreen, ContactListScreen,
                             AddEditContactScreen, SearchScreen):
            self.sm.add_widget(screen_class())
        self.sm.current = "contacts" if token_storage.has_token() else "login"
        return self.sm

    # ---------- navigation ----------
    def go(self, screen_name):
        self.sm.current = screen_name

    def open_editor(self, contact=None):
        self.sm.get_screen("edit").prepare(contact)
        self.go("edit")

    def _on_keyboard(self, window, key, *args):
        """Android back button / Esc key."""
        if key == 27:
            if self.sm.current in ("edit", "search"):
                self.go("contacts")
                return True
            if self.sm.current == "register":
                self.go("login")
                return True
        return False

    # ---------- session ----------
    def force_logout(self):
        token_storage.clear_token()
        self.go("login")
        info_popup("Signed out", "Your session has expired.\nPlease log in again.")

    def logout(self):
        token_storage.clear_token()
        self.go("login")

    def _handle_error(self, error):
        if isinstance(error, ApiError) and error.status == 401:
            self.force_logout()
        else:
            info_popup("Something went wrong", str(error))

    # ---------- actions ----------
    def confirm_delete(self, contact, on_done):
        def do_delete():
            run_async(lambda: client.delete_contact(contact["id"]),
                      lambda _r: on_done(), self._handle_error)

        confirm_popup("Delete contact",
                      "Delete %s?\nThis cannot be undone." % contact["name"],
                      "Delete", do_delete, danger=True)

    def show_account_popup(self):
        box = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        who = Label(text="Signed in as [b]%s[/b]" % (token_storage.get_username() or "you"),
                    markup=True, color=C_TEXT, size_hint_y=None, height=dp(30))
        box.add_widget(who)
        popup = make_popup("Account", box, dp(300))

        logout_btn = AppButton(text="Log out")
        delete_btn = AppButton(text="Delete my account", bg_color=C_DANGER)
        close_btn = AppButton(text="Close", bg_color=C_MUTED)

        def do_logout(*_):
            popup.dismiss()
            self.logout()

        def ask_delete(*_):
            popup.dismiss()
            confirm_popup(
                "Delete account",
                "This permanently deletes your account\nand ALL your contacts.",
                "Delete", self._delete_account, danger=True)

        logout_btn.bind(on_release=do_logout)
        delete_btn.bind(on_release=ask_delete)
        close_btn.bind(on_release=lambda *_: popup.dismiss())
        for widget in (logout_btn, delete_btn, close_btn):
            box.add_widget(widget)
        popup.open()

    def _delete_account(self):
        run_async(client.delete_account, lambda _r: self.go("login"),
                  self._handle_error)


if __name__ == "__main__":
    AddressBookApp().run()
