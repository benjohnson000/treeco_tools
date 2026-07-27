"""Launch the inventory dashboard in a native Windows window."""

import threading
from http.server import ThreadingHTTPServer
import os
from pathlib import Path

import webview

from app_paths import DATA_DIR, ensure_data_directories
from database import start_new_session
from dashboard import HOST, PORT, Handler


WINDOW_TITLE = "Spruce Inventory Reorder Tool"


class DesktopApi:
    """Native actions exposed to the local dashboard."""

    def __init__(self):
        self.window = None

    def save_order_csv(self, contents):
        destination = self.window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename="purchase_order_draft.csv",
            file_types=("CSV files (*.csv)",),
        )
        if not destination:
            return None
        if isinstance(destination, (tuple, list)):
            destination = destination[0]
        with Path(destination).open("w", encoding="utf-8-sig", newline="") as file:
            file.write(contents)
        return str(destination)

    def open_data_folder(self):
        ensure_data_directories()
        os.startfile(DATA_DIR)
        return str(DATA_DIR)


def main():
    start_new_session()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    api = DesktopApi()
    try:
        api.window = webview.create_window(
            WINDOW_TITLE,
            f"http://{HOST}:{PORT}",
            width=1440,
            height=900,
            min_size=(1050, 680),
            js_api=api,
        )
        webview.start()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
