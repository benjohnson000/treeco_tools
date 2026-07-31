"""Launch the Buy Group Reporting dashboard in a native Windows window."""

import os
import threading
from http.server import ThreadingHTTPServer

import webview

from dashboard import HOST, PORT, Handler
from app_paths import ensure_data_directory


class DesktopApi:
    """Actions the local dashboard can request from the native window."""

    def open_data_folder(self):
        folder = ensure_data_directory()
        os.startfile(folder)
        return str(folder)

    def save_report_csv(self, contents):
        destination = self.window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename="buy_group_report.csv",
            file_types=("CSV files (*.csv)",),
        )
        if not destination:
            return None
        if isinstance(destination, (tuple, list)):
            destination = destination[0]
        with open(destination, "w", encoding="utf-8-sig", newline="") as file:
            file.write(contents)
        return str(destination)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        api = DesktopApi()
        api.window = webview.create_window(
            "Treeco Buy Group Reporting",
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
