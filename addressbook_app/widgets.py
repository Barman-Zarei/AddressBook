"""Reusable widgets and popup helpers (styled in addressbook.kv)."""

from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput

C_PRIMARY = (0.42, 0.36, 0.91, 1)
C_TEXT = (0.17, 0.19, 0.25, 1)
C_MUTED = (0.5, 0.53, 0.6, 1)
C_DANGER = (0.94, 0.35, 0.35, 1)
C_TEAL = (0.0, 0.72, 0.58, 1)

AVATAR_COLORS = [
    (0.42, 0.36, 0.91, 1),
    (0.0, 0.72, 0.58, 1),
    (1.0, 0.62, 0.26, 1),
    (0.99, 0.40, 0.55, 1),
    (0.09, 0.63, 0.87, 1),
]


class AppButton(Button):
    bg_color = ListProperty(C_PRIMARY)
    corner = NumericProperty(dp(12))


class AppInput(TextInput):
    pass


class Card(BoxLayout):
    pass


class Avatar(Label):
    bg_color = ListProperty(C_PRIMARY)


def make_popup(title, content, height):
    return Popup(
        title=title,
        content=content,
        size_hint=(0.88, None),
        height=height,
        auto_dismiss=False,
        background="",
        background_color=(1, 1, 1, 1),
        title_color=C_TEXT,
        separator_color=C_PRIMARY,
    )


def _message_label(text):
    lbl = Label(text=text, color=C_TEXT, halign="center", valign="middle")
    lbl.bind(size=lambda inst, size: setattr(inst, "text_size", size))
    return lbl


def info_popup(title, message):
    box = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
    box.add_widget(_message_label(message))
    popup = make_popup(title, box, dp(240))
    ok = AppButton(text="OK")
    ok.bind(on_release=lambda *_: popup.dismiss())
    box.add_widget(ok)
    popup.open()


def confirm_popup(title, message, confirm_text="Confirm", on_confirm=None, danger=False):
    box = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
    box.add_widget(_message_label(message))
    row = BoxLayout(spacing=dp(10), size_hint_y=None, height=dp(48))
    popup = make_popup(title, box, dp(230))

    cancel = AppButton(text="Cancel", bg_color=C_MUTED)
    cancel.bind(on_release=lambda *_: popup.dismiss())
    confirm = AppButton(text=confirm_text, bg_color=C_DANGER if danger else C_PRIMARY)

    def _confirm(*_):
        popup.dismiss()
        if on_confirm:
            on_confirm()

    confirm.bind(on_release=_confirm)
    row.add_widget(cancel)
    row.add_widget(confirm)
    box.add_widget(row)
    popup.open()
