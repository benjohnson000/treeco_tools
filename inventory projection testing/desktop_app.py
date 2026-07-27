"""Launch the inventory dashboard in a native Windows window."""

import threading
from http.server import ThreadingHTTPServer

import webview

from dashboard import HOST, PORT, Handler


WINDOW_TITLE = "Spruce Inventory Reorder Tool"


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        webview.create_window(
            WINDOW_TITLE,
            f"http://{HOST}:{PORT}",
            width=1440,
            height=900,
            min_size=(1050, 680),
        )
        webview.start()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
