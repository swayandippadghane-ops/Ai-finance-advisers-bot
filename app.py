"""Personal Finance Advisor Bot - Flask application factory.

Run locally:   python app.py
Or with Flask: flask --app app run
Production:    gunicorn "app:create_app()"
"""
import hmac
import logging
import os
import secrets
from datetime import date

from flask import Flask, abort, g, render_template, request, session
from werkzeug.exceptions import HTTPException

from config import BASE_DIR, Config
from extensions import db
from services import finance

ERROR_MESSAGES = {
    403: "You do not have permission to open that page.",
    404: "That page does not exist, or it is not yours to view.",
    405: "That action is not allowed here.",
    413: "That request was too large.",
    429: "Too many requests. Please wait a moment and try again.",
    500: "Something went wrong on our side. Your data is safe, so please try again.",
}


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    if not app.config.get("SECRET_KEY_FROM_ENV") and not app.testing:
        logging.warning("SECRET_KEY is not set in .env, so a random key is used and "
                        "logins will reset whenever the server restarts.")

    os.makedirs(BASE_DIR / "instance", exist_ok=True)
    db.init_app(app)

    import models  # noqa: F401  (registers the tables)
    from routes.auth import bp as auth_bp
    from routes.main import bp as main_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    symbol = app.config["CURRENCY_SYMBOL"]
    app.jinja_env.filters["money"] = lambda value: finance.format_money(value or 0, symbol)
    app.jinja_env.filters["pct"] = lambda value: "-" if value is None else f"{value * 100:.0f}%"

    @app.before_request
    def load_user_and_check_csrf():
        if request.endpoint == "static":
            return
        g.user = None
        user_id = session.get("user_id")
        if user_id is not None:
            g.user = db.session.get(models.User, user_id)
            if g.user is None:
                session.pop("user_id", None)
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
            expected = session.get("_csrf", "")
            if not expected or not hmac.compare_digest(str(expected), str(sent)):
                abort(400, description="Your session expired or the form was invalid. "
                                       "Please reload the page and try again.")

    @app.context_processor
    def inject_globals():
        if "_csrf" not in session:
            session["_csrf"] = secrets.token_hex(16)
        return {
            "csrf_token": session["_csrf"],
            "current_user": g.get("user"),
            "currency": symbol,
            "categories": finance.CATEGORIES,
            "year": date.today().year,
        }

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        code = error.code or 500
        message = error.description if code == 400 else ERROR_MESSAGES.get(code, error.description)
        return render_template("error.html", code=code, title=error.name, message=message), code

    @app.errorhandler(500)
    def handle_server_error(error):
        db.session.rollback()
        return render_template("error.html", code=500, title="Server error",
                               message=ERROR_MESSAGES[500]), 500

    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
