import threading

from kivy.clock import Clock


def run_async(func, on_success=None, on_error=None):
    """Run `func` in a background thread so the UI never freezes.

    Callbacks are always delivered on the main (Kivy) thread.
    """
    def worker():
        try:
            result = func()
        except Exception as exc:  # noqa: BLE001
            error = exc
            if on_error:
                Clock.schedule_once(lambda dt: on_error(error), 0)
            return
        if on_success:
            Clock.schedule_once(lambda dt: on_success(result), 0)

    threading.Thread(target=worker, daemon=True).start()
