"""Server-side input validation. Functions raise ValueError with a user-friendly message."""
import math
import re
from datetime import date, datetime

from services.finance import CATEGORIES

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
MAX_AMOUNT = 10_000_000


def parse_amount(raw, label="Amount", allow_zero=False):
    text = (raw or "").strip().replace(",", "")
    if not text:
        raise ValueError(f"{label} is required.")
    try:
        value = float(text)
    except ValueError:
        raise ValueError(f"{label} must be a number.")
    if not math.isfinite(value):
        raise ValueError(f"{label} must be a valid number.")
    if value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{label} must be greater than zero.")
    if value > MAX_AMOUNT:
        raise ValueError(f"{label} cannot be more than {MAX_AMOUNT:,}.")
    return round(value, 2)


def parse_date(raw, label="Date"):
    text = (raw or "").strip()
    if not text:
        raise ValueError(f"{label} is required.")
    try:
        value = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"{label} must be a valid date.")
    if value.year < 2000 or value.year > date.today().year + 1:
        raise ValueError(f"{label} is outside the supported range.")
    return value


def parse_category(raw):
    value = (raw or "").strip()
    if value not in CATEGORIES:
        raise ValueError("Please choose a valid category.")
    return value


def clean_text(raw, label, max_len, required=False):
    text = CONTROL_RE.sub("", (raw or "")).strip()
    if required and not text:
        raise ValueError(f"{label} is required.")
    if len(text) > max_len:
        raise ValueError(f"{label} must be {max_len} characters or fewer.")
    return text


def validate_registration(form):
    """Return (cleaned, errors) for the registration form."""
    errors = []
    name = CONTROL_RE.sub("", form.get("name", "")).strip()
    email = form.get("email", "").strip().lower()
    password = form.get("password", "")
    confirm = form.get("confirm_password", "")

    if not 2 <= len(name) <= 60:
        errors.append("Name must be between 2 and 60 characters.")
    if len(email) > 254 or not EMAIL_RE.match(email):
        errors.append("Enter a valid email address.")
    if not 8 <= len(password) <= 128:
        errors.append("Password must be 8 to 128 characters long.")
    elif not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        errors.append("Password must contain at least one letter and one number.")
    if password != confirm:
        errors.append("The two passwords do not match.")
    return {"name": name, "email": email, "password": password}, errors
