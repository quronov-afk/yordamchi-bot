import hmac
import json
import hashlib
from urllib.parse import parse_qsl

from flask import Flask, request, jsonify

from config import BOT_TOKEN, DEV_MODE, PORT

app = Flask(__name__, static_folder="webapp", static_url_path="")


def validate_init_data(init_data: str):
    """Telegram yuborgan ma'lumot haqiqiyligini tekshiradi."""
    if not init_data or not BOT_TOKEN:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        got_hash = pairs.pop("hash", None)
        if not got_hash:
            return None
        check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, got_hash):
            return None
        return json.loads(pairs.get("user", "{}"))
    except Exception:
        return None


def current_user():
    user = validate_init_data(request.headers.get("X-Init-Data", ""))
    if user is None and DEV_MODE:
        return {"id": 1, "first_name": "Sinov", "last_name": "Foydalanuvchi"}
    return user


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/me")
def me():
    user = current_user()
    if not user:
        return jsonify({"error": "auth"}), 401

    name = " ".join(x for x in [user.get("first_name"), user.get("last_name")] if x)
    return jsonify({
        "id": user.get("id"),
        "name": name or "Foydalanuvchi",
        "username": user.get("username"),
        "photo": user.get("photo_url"),
        "role": "Xodim",
        "stats": {"new": 0, "doing": 0, "done": 0, "late": 0},
        "tasks": [],
    })


def run_server(port=None):
    port = port or PORT
    try:
        from waitress import serve
    except ImportError:
        app.run(host="0.0.0.0", port=port, threaded=True)
        return
    serve(app, host="0.0.0.0", port=port, threads=8)
