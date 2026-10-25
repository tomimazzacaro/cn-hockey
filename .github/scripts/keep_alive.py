"""Mantiene despierta la app de Streamlit Community Cloud.

Un GET con curl solo baja el HTML estático: no abre la sesión (websocket) que
Streamlit cuenta como "visita". Acá abrimos la app en un Chromium real y, si
está dormida, clickeamos el botón de despertar.
"""

import os
import sys
import time

from playwright.sync_api import sync_playwright

URL = os.environ.get("APP_URL", "https://cn-hockey.streamlit.app/")
WAKE_BUTTON_TEXT = "get this app back up"
APP_SELECTOR = '[data-testid="stApp"]'
TIMEOUT_S = 150
SETTLE_S = 15


def app_loaded(page) -> bool:
    # En Community Cloud la app vive dentro de un iframe; en local, en la página.
    return any(frame.query_selector(APP_SELECTOR) for frame in page.frames)


def wake_button(page):
    button = page.get_by_role("button", name=WAKE_BUTTON_TEXT, exact=False)
    return button if button.count() else None


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60_000)

        deadline = time.time() + TIMEOUT_S
        woke_up = False
        while time.time() < deadline:
            if app_loaded(page):
                break
            button = wake_button(page)
            if button and not woke_up:
                print("App dormida: clickeando el botón de despertar")
                button.first.click()
                woke_up = True
            time.sleep(3)
        else:
            page.screenshot(path="keep_alive_fail.png")
            print(f"La app no cargó en {TIMEOUT_S}s")
            browser.close()
            return 1

        # Dejamos la sesión abierta unos segundos para que cuente como visita.
        time.sleep(SETTLE_S)
        print("App activa" + (" (se despertó)" if woke_up else ""))
        browser.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())
