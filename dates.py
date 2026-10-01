"""Month helpers. A month is always the string 'YYYY-MM'."""
import calendar
from datetime import date, datetime


def current_month():
    return date.today().strftime("%Y-%m")


def parse_month(raw):
    """Return a valid 'YYYY-MM' string, falling back to the current month."""
    try:
        parsed = datetime.strptime((raw or "").strip(), "%Y-%m")
    except ValueError:
        return current_month()
    if parsed.year < 2000 or parsed.year > 2100:
        return current_month()
    return parsed.strftime("%Y-%m")


def month_range(month):
    """Return (first_day, first_day_of_next_month) for a 'YYYY-MM' string."""
    year, mon = (int(part) for part in month.split("-"))
    start = date(year, mon, 1)
    end = date(year + 1, 1, 1) if mon == 12 else date(year, mon + 1, 1)
    return start, end


def shift_month(month, delta):
    year, mon = (int(part) for part in month.split("-"))
    index = year * 12 + (mon - 1) + delta
    new_year, new_mon = divmod(index, 12)
    return f"{new_year:04d}-{new_mon + 1:02d}"


def month_label(month):
    year, mon = (int(part) for part in month.split("-"))
    return f"{calendar.month_name[mon]} {year}"


def default_date_for(month):
    """Today if it falls inside the month, otherwise the 1st of that month."""
    today = date.today()
    if today.strftime("%Y-%m") == month:
        return today.isoformat()
    return month + "-01"
