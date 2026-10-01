"""Create a demo account with two months of sample data.

Usage:  python seed_demo.py
Login:  demo@example.com / Demo@1234
"""
from calendar import monthrange
from datetime import date

from app import create_app
from extensions import db
from models import Budget, Expense, Income, User
from services import dates, finance

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "Demo@1234"

# (day, category, note, amount)
EXPENSES = [
    (1, "Rent", "Monthly rent", 18000), (2, "Food", "Groceries", 2400),
    (3, "Transport", "Metro card", 900), (4, "Utilities", "Electricity", 1800),
    (5, "Food", "Dinner with friends", 1600), (6, "Entertainment", "Streaming and movie", 1100),
    (8, "Food", "Vegetables", 1300), (9, "Healthcare", "Pharmacy", 700),
    (10, "Food", "Lunches", 2100), (11, "Transport", "Cab rides", 1500),
    (13, "Education", "Online course", 3500), (14, "Entertainment", "Concert tickets", 3200),
    (15, "Shopping", "Clothes", 4200), (16, "Food", "Weekend brunch", 1900),
    (18, "Shopping", "Headphones", 2600), (20, "Food", "Groceries", 2200),
    (22, "Food", "Takeaway", 1400), (24, "Transport", "Fuel", 1600),
]


def seed():
    app = create_app()
    with app.app_context():
        existing = User.query.filter_by(email=DEMO_EMAIL).first()
        if existing:
            db.session.delete(existing)
            db.session.commit()

        user = User(name="Demo User", email=DEMO_EMAIL)
        user.set_password(DEMO_PASSWORD)
        db.session.add(user)
        db.session.commit()

        today = date.today()
        for offset in (-1, 0):
            month = dates.shift_month(dates.current_month(), offset)
            year, mon = (int(p) for p in month.split("-"))
            last_day = monthrange(year, mon)[1]
            if offset == 0:
                last_day = min(last_day, today.day)
            db.session.add(Income(user_id=user.id, source="Salary", amount=60000, received_on=date(year, mon, 1)))
            db.session.add(Income(user_id=user.id, source="Freelance project", amount=8000,
                                  received_on=date(year, mon, min(12, last_day))))
            for day, category, note, amount in EXPENSES:
                if day <= last_day:
                    db.session.add(Expense(user_id=user.id, category=category, description=note,
                                           amount=amount, spent_on=date(year, mon, day)))
        db.session.commit()

        month = dates.current_month()
        limits, _target = finance.suggest_budget(68000, {})
        for category, limit in limits.items():
            db.session.add(Budget(user_id=user.id, month=month, category=category, limit_amount=limit))
        db.session.commit()

    print(f"Demo account ready. Log in with {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    seed()
