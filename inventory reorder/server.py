"""Railway web server for the Spruce Inventory Reorder Tool."""

import base64
import hmac
import os
from http.server import ThreadingHTTPServer

from app_paths import ensure_data_directories
from dashboard import Handler


class ProtectedHandler(Handler):
    """Protect every dashboard route with HTTP Basic Authentication."""

    def authorized(self):
        password = os.environ.get("APP_PASSWORD", "")
        if not password:
            return True
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            username, supplied_password = base64.b64decode(header[6:]).decode().split(":", 1)
        except (ValueError, UnicodeDecodeError):
            return False
        expected_username = os.environ.get("APP_USERNAME", "treeco")
        return hmac.compare_digest(username, expected_username) and hmac.compare_digest(supplied_password, password)

    def require_auth(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Spruce Inventory Reorder Tool"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if not self.authorized():
            self.require_auth()
            return
        super().do_GET()

    def do_POST(self):
        if not self.authorized():
            self.require_auth()
            return
        super().do_POST()


def main():
    if os.environ.get("RAILWAY_ENVIRONMENT") and not os.environ.get("APP_PASSWORD"):
        raise RuntimeError("Set APP_PASSWORD before deploying this internal reorder tool.")
    ensure_data_directories()
    port = int(os.environ.get("PORT", "8080"))
    print(f"Spruce Inventory Reorder Tool listening on port {port}")
    ThreadingHTTPServer(("0.0.0.0", port), ProtectedHandler).serve_forever()


if __name__ == "__main__":
    main()
