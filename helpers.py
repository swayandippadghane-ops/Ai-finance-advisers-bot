"""Small helpers shared by route modules."""
from functools import wraps

from flask import flash, g, redirect, request, url_for


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            flash("Please log in to continue.", "info")
            target = request.full_path if request.query_string else request.path
            return redirect(url_for("auth.login", next=target))
        return view(*args, **kwargs)

    return wrapped
