#!/usr/bin/env python3
"""Shipcrawler OSINT Dashboard — Flask Application Factory."""

import os

from flask import Flask

TAILSCALE_IP = "100.72.133.89"
PORT = 9091


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["SECRET_KEY"] = os.urandom(24)
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    # Register routes
    from routes.api import init_routes
    init_routes(app)

    return app


app = create_app()

if __name__ == "__main__":
    import socket

    print(f"  🚢 Shipcrawler OSINT Dashboard v6.3 (AI Agent)")
    print(f"  🌐 http://{TAILSCALE_IP}:{PORT}")
    print(f"  🔒 Binding to Tailscale IP: {TAILSCALE_IP}")
    print()

    # Enable TCP keepalive so stale connections don't hang forever
    from werkzeug.serving import make_server

    srv = make_server(TAILSCALE_IP, PORT, app, threaded=True)
    srv.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    srv.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
    srv.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
    srv.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
    srv.serve_forever()
