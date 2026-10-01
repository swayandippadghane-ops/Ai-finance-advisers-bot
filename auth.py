"""Registration, login and logout."""
import secrets
import time

from flask import (Blueprint, flash, g, redirect, render_template, request,
                   session, url_for)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db
from models import User
from services import validation

bp = Blueprint("auth", __name__)

# Simple in-memory brake on password guessing: 5 failures per 5 minutes per IP + email.
_FAILURES = {}
_MAX_FAILURES = 5
_WINDOW_SECONDS = 300


def _recent_failures(key):
    now = time.time()
    hits = [t for t in _FAILURES.get(key, []) if now - t < _WINDOW_SECONDS]
    if hits:
        _FAILURES[key] = hits
    else:
        _FAILURES.pop(key, None)
    return hits


def _safe_next(target):
    """Only allow redirects to paths on this site."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        return target
    return url_for("main.dashboard")


def _start_session(user):
    session.clear()
    session["user_id"] = user.id
    session["_csrf"] = secrets.token_hex(16)
    session.permanent = True


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("main.dashboard"))
    form = {"name": "", "email": ""}
    if request.method == "POST":
        form = {
            "name": request.form.get("name", "").strip()[:60],
            "email": request.form.get("email", "").strip()[:254],
        }
        cleaned, errors = validation.validate_registration(request.form)
        exists_msg = "An account with this email already exists. Try logging in instead."
        if not errors and User.query.filter_by(email=cleaned["email"]).first():
            errors.append(exists_msg)
        if not errors:
            user = User(name=cleaned["name"], email=cleaned["email"])
            user.set_password(cleaned["password"])
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                errors.append(exists_msg)
            except SQLAlchemyError:
                db.session.rollback()
                errors.append("Something went wrong while saving your account. Please try again.")
            else:
                _start_session(user)
                flash(f"Welcome, {user.name}! Start by adding this month's income.", "success")
                return redirect(url_for("main.dashboard"))
        for message in errors:
            flash(message, "error")
        return render_template("register.html", form=form), 400
    return render_template("register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("main.dashboard"))
    next_url = request.args.get("next") or request.form.get("next") or ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "")[:128]
        key = f"{request.remote_addr}|{email}"
        if len(_recent_failures(key)) >= _MAX_FAILURES:
            flash("Too many failed attempts. Please wait a few minutes and try again.", "error")
            return render_template("login.html", email=email, next_url=next_url), 429
        user = User.query.filter_by(email=email).first() if email else None
        if user and user.check_password(password):
            _FAILURES.pop(key, None)
            _start_session(user)
            flash(f"Welcome back, {user.name}.", "success")
            return redirect(_safe_next(next_url))
        _FAILURES.setdefault(key, []).append(time.time())
        flash("Incorrect email or password.", "error")
        return render_template("login.html", email=email, next_url=next_url), 401
    return render_template("login.html", email="", next_url=next_url)


@bp.post("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
