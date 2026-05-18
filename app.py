"""
Entry point for the Real-Money Prediction & Card Gaming Platform.
Run locally:  python app.py
"""

import os
from app import create_app, socketio
from app.extensions import db

app = create_app()


@app.cli.command("init-db")
def init_db():
    """Create all tables (use only for first-run / local dev)."""
    with app.app_context():
        db.create_all()
        print("Database initialised.")


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"

    # Auto-create tables on first localhost run (safe + idempotent)
    with app.app_context():
        os.makedirs(app.instance_path, exist_ok=True)
        db.create_all()

    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=True,
        allow_unsafe_werkzeug=True
    )
