#!/usr/bin/env python3
"""Shipcrawler OSINT Dashboard — Flask Application Factory."""

import os

from flask import Flask

TAILSCALE_IP = "100.72.133.89"
PORT = 9091


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["SECRET_KEY"] = os.urandom(24)

    # Register routes
    from routes.api import init_routes
    init_routes(app)

    return app


app = create_app()

if __name__ == "__main__":
    print(f"  🚢 Shipcrawler OSINT Dashboard v5 (Phase Agent)")
    print(f"  🌐 http://{TAILSCALE_IP}:{PORT}")
    print(f"  🔒 Binding to Tailscale IP: {TAILSCALE_IP}")
    print()
    # threaded=True so SSE long-poll doesn't block other connections
    app.run(host=TAILSCALE_IP, port=PORT, debug=False, threaded=True)
