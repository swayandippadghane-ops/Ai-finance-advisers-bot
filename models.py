"""Database models (SQLAlchemy)."""
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    incomes = db.relationship("Income", backref="user", cascade="all, delete-orphan")
    expenses = db.relationship("Expense", backref="user", cascade="all, delete-orphan")
    budgets = db.relationship("Budget", backref="user", cascade="all, delete-orphan")
    recommendations = db.relationship(
        "Recommendation", backref="user", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        # pbkdf2 is available on every Python build (scrypt is not).
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Income(db.Model):
    __tablename__ = "incomes"
    __table_args__ = (db.Index("ix_income_user_date", "user_id", "received_on"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    source = db.Column(db.String(60), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    received_on = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)


class Expense(db.Model):
    __tablename__ = "expenses"
    __table_args__ = (db.Index("ix_expense_user_date", "user_id", "spent_on"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category = db.Column(db.String(30), nullable=False)
    description = db.Column(db.String(120), default="", nullable=False)
    amount = db.Column(db.Float, nullable=False)
    spent_on = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)


class Budget(db.Model):
    """A monthly spending limit for one category. month is 'YYYY-MM'."""

    __tablename__ = "budgets"
    __table_args__ = (
        db.UniqueConstraint("user_id", "month", "category", name="uq_budget_user_month_cat"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    month = db.Column(db.String(7), nullable=False)
    category = db.Column(db.String(30), nullable=False)
    limit_amount = db.Column(db.Float, nullable=False)


class Recommendation(db.Model):
    """The latest advice generated for a user and month (JSON text)."""

    __tablename__ = "recommendations"
    __table_args__ = (db.UniqueConstraint("user_id", "month", name="uq_reco_user_month"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    month = db.Column(db.String(7), nullable=False)
    content = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(10), nullable=False, default="rules")  # 'gemini' or 'rules'
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
