"""Dashboard, income, expenses, budget, AI recommendations and monthly reports."""
import csv
import io
import json
from datetime import datetime, timezone

from flask import (Blueprint, Response, current_app, flash, g, jsonify,
                   redirect, render_template, request, url_for)
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import Budget, Expense, Income, Recommendation
from routes.helpers import login_required
from services import ai, dates, finance, validation

bp = Blueprint("main", __name__)

_BACK = {
    "dashboard": "main.dashboard",
    "income": "main.income_page",
    "expenses": "main.expenses_page",
}


# ---------------------------------------------------------------- helpers
def _fmt():
    symbol = current_app.config["CURRENCY_SYMBOL"]
    return lambda value: finance.format_money(value, symbol)


def _month_ctx(raw):
    month = dates.parse_month(raw)
    return {
        "month": month,
        "month_label": dates.month_label(month),
        "prev_month": dates.shift_month(month, -1),
        "next_month": dates.shift_month(month, 1),
    }


def _expense_dict(e):
    return {"category": e.category, "amount": e.amount,
            "description": e.description or "", "date": e.spent_on}


def _load(user_id, month):
    """Return (incomes, expenses, budgets, summary) for one user and month."""
    start, end = dates.month_range(month)
    incomes = (Income.query
               .filter(Income.user_id == user_id, Income.received_on >= start, Income.received_on < end)
               .order_by(Income.received_on.desc(), Income.id.desc()).all())
    expenses = (Expense.query
                .filter(Expense.user_id == user_id, Expense.spent_on >= start, Expense.spent_on < end)
                .order_by(Expense.spent_on.desc(), Expense.id.desc()).all())
    budgets = {b.category: b.limit_amount
               for b in Budget.query.filter_by(user_id=user_id, month=month).all()}
    summary = finance.summarize([i.amount for i in incomes],
                                [_expense_dict(e) for e in expenses], budgets)
    return incomes, expenses, budgets, summary


def _commit():
    try:
        db.session.commit()
        return True
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Database error")
        return False


def _back_url(name, month):
    return url_for(_BACK.get(name, "main.dashboard"), month=month)


def _replace_budgets(user_id, month, limits):
    Budget.query.filter_by(user_id=user_id, month=month).delete()
    for category, limit in limits.items():
        if limit > 0:
            db.session.add(Budget(user_id=user_id, month=month, category=category, limit_amount=limit))
    return _commit()


def _average_spend(user_id, month):
    """Average monthly spend per category over the selected month and the two before it."""
    start, _ = dates.month_range(dates.shift_month(month, -2))
    _, end = dates.month_range(month)
    rows = Expense.query.filter(Expense.user_id == user_id,
                                Expense.spent_on >= start, Expense.spent_on < end).all()
    totals, months = {}, set()
    for e in rows:
        months.add(e.spent_on.strftime("%Y-%m"))
        totals[e.category] = totals.get(e.category, 0.0) + e.amount
    count = len(months) or 1
    return {category: total / count for category, total in totals.items()}


def _saved_advice(user_id, month):
    rec = Recommendation.query.filter_by(user_id=user_id, month=month).first()
    if rec is None:
        return None, None, None
    try:
        advice = json.loads(rec.content)
    except ValueError:
        return None, None, None
    if not isinstance(advice, dict):
        return None, None, None
    return advice, rec.source, rec.created_at


def _save_advice(user_id, month, advice, source):
    rec = Recommendation.query.filter_by(user_id=user_id, month=month).first()
    if rec is None:
        rec = Recommendation(user_id=user_id, month=month)
        db.session.add(rec)
    rec.content = json.dumps(advice, ensure_ascii=False)
    rec.source = source
    rec.created_at = datetime.now(timezone.utc)
    return _commit()


def _csv_safe(value):
    """Stop spreadsheet apps from treating text as a formula."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


# ---------------------------------------------------------------- pages
@bp.route("/")
def index():
    if g.user:
        return redirect(url_for("main.dashboard"))
    return render_template("index.html")


@bp.route("/healthz")
def healthz():
    return jsonify(status="ok")


@bp.route("/dashboard")
@login_required
def dashboard():
    ctx = _month_ctx(request.args.get("month"))
    incomes, expenses, _budgets, summary = _load(g.user.id, ctx["month"])
    advice, _source, _created = _saved_advice(g.user.id, ctx["month"])
    return render_template(
        "dashboard.html", summary=summary, recent_expenses=expenses[:6],
        recent_incomes=incomes[:4], default_date=dates.default_date_for(ctx["month"]),
        tips=finance.CATEGORY_TIPS, has_advice=advice is not None, **ctx)


# ---------------------------------------------------------------- income
@bp.route("/income")
@login_required
def income_page():
    ctx = _month_ctx(request.args.get("month"))
    incomes, _e, _b, summary = _load(g.user.id, ctx["month"])
    return render_template("income.html", incomes=incomes, summary=summary,
                           default_date=dates.default_date_for(ctx["month"]), **ctx)


@bp.post("/income/add")
@login_required
def add_income():
    month = dates.parse_month(request.form.get("month"))
    back = request.form.get("back", "income")
    try:
        amount = validation.parse_amount(request.form.get("amount"), "Income amount")
        received_on = validation.parse_date(request.form.get("date"), "Date")
        source = validation.clean_text(request.form.get("source"), "Source", 60, required=True)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(_back_url(back, month))
    db.session.add(Income(user_id=g.user.id, source=source, amount=amount, received_on=received_on))
    if _commit():
        flash(f"Added income of {_fmt()(amount)} from {source}.", "success")
    else:
        flash("Could not save that income. Please try again.", "error")
    return redirect(_back_url(back, received_on.strftime("%Y-%m")))


@bp.post("/income/<int:income_id>/delete")
@login_required
def delete_income(income_id):
    item = Income.query.filter_by(id=income_id, user_id=g.user.id).first_or_404()
    month = item.received_on.strftime("%Y-%m")
    db.session.delete(item)
    if _commit():
        flash("Income entry deleted.", "info")
    else:
        flash("Could not delete that entry. Please try again.", "error")
    return redirect(url_for("main.income_page", month=month))


# ---------------------------------------------------------------- expenses
@bp.route("/expenses")
@login_required
def expenses_page():
    ctx = _month_ctx(request.args.get("month"))
    category = request.args.get("category", "")
    if category not in finance.CATEGORIES:
        category = ""
    start, end = dates.month_range(ctx["month"])
    query = Expense.query.filter(Expense.user_id == g.user.id,
                                 Expense.spent_on >= start, Expense.spent_on < end)
    if category:
        query = query.filter(Expense.category == category)
    expenses = query.order_by(Expense.spent_on.desc(), Expense.id.desc()).limit(500).all()
    return render_template(
        "expenses.html", expenses=expenses, total=sum(e.amount for e in expenses),
        category=category, default_date=dates.default_date_for(ctx["month"]), **ctx)


def _read_expense_form():
    return (
        validation.parse_amount(request.form.get("amount"), "Expense amount"),
        validation.parse_category(request.form.get("category")),
        validation.parse_date(request.form.get("date"), "Date"),
        validation.clean_text(request.form.get("description"), "Description", 120),
    )


@bp.post("/expenses/add")
@login_required
def add_expense():
    month = dates.parse_month(request.form.get("month"))
    back = request.form.get("back", "expenses")
    try:
        amount, category, spent_on, description = _read_expense_form()
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(_back_url(back, month))
    db.session.add(Expense(user_id=g.user.id, category=category, description=description,
                           amount=amount, spent_on=spent_on))
    if _commit():
        flash(f"Added {category} expense of {_fmt()(amount)}.", "success")
    else:
        flash("Could not save that expense. Please try again.", "error")
    return redirect(_back_url(back, spent_on.strftime("%Y-%m")))


@bp.route("/expenses/<int:expense_id>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(expense_id):
    item = Expense.query.filter_by(id=expense_id, user_id=g.user.id).first_or_404()
    if request.method == "POST":
        try:
            amount, category, spent_on, description = _read_expense_form()
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("main.edit_expense", expense_id=item.id))
        item.amount, item.category = amount, category
        item.spent_on, item.description = spent_on, description
        if _commit():
            flash("Expense updated.", "success")
        else:
            flash("Could not update that expense. Please try again.", "error")
        return redirect(url_for("main.expenses_page", month=spent_on.strftime("%Y-%m")))
    return render_template("expense_edit.html", expense=item)


@bp.post("/expenses/<int:expense_id>/delete")
@login_required
def delete_expense(expense_id):
    item = Expense.query.filter_by(id=expense_id, user_id=g.user.id).first_or_404()
    month = item.spent_on.strftime("%Y-%m")
    db.session.delete(item)
    if _commit():
        flash("Expense deleted.", "info")
    else:
        flash("Could not delete that expense. Please try again.", "error")
    return redirect(url_for("main.expenses_page", month=month))


# ---------------------------------------------------------------- budget
@bp.route("/budget")
@login_required
def budget_page():
    ctx = _month_ctx(request.args.get("month"))
    _i, _e, _b, summary = _load(g.user.id, ctx["month"])
    planned_savings = summary["total_income"] - summary["total_budget"]
    return render_template("budget.html", summary=summary, planned_savings=planned_savings, **ctx)


@bp.post("/budget/save")
@login_required
def save_budget():
    month = dates.parse_month(request.form.get("month"))
    limits = {}
    try:
        for category in finance.CATEGORIES:
            raw = request.form.get("limit_" + category, "")
            limits[category] = (validation.parse_amount(raw, f"{category} limit", allow_zero=True)
                                if raw.strip() else 0.0)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("main.budget_page", month=month))
    if _replace_budgets(g.user.id, month, limits):
        flash(f"Budget saved for {dates.month_label(month)}.", "success")
    else:
        flash("Could not save the budget. Please try again.", "error")
    return redirect(url_for("main.budget_page", month=month))


@bp.post("/budget/generate")
@login_required
def generate_budget():
    month = dates.parse_month(request.form.get("month"))
    _i, _e, _b, summary = _load(g.user.id, month)
    if summary["total_income"] <= 0:
        flash(f"Add income for {dates.month_label(month)} first, so the budget has something to divide.", "error")
        return redirect(url_for("main.budget_page", month=month))
    limits, target = finance.suggest_budget(summary["total_income"], _average_spend(g.user.id, month))
    if _replace_budgets(g.user.id, month, limits):
        flash(f"Suggested budget created using a 50/30/20 plan. Savings target: {_fmt()(target)}.", "success")
    else:
        flash("Could not save the suggested budget. Please try again.", "error")
    return redirect(url_for("main.budget_page", month=month))


# ---------------------------------------------------------------- AI advice
@bp.route("/recommendations")
@login_required
def recommendations():
    ctx = _month_ctx(request.args.get("month"))
    _i, _e, _b, summary = _load(g.user.id, ctx["month"])
    advice, source, created = _saved_advice(g.user.id, ctx["month"])
    return render_template(
        "recommendations.html", summary=summary, advice=advice, source=source, created=created,
        ai_configured=ai.is_configured(current_app.config["GEMINI_API_KEY"]), **ctx)


@bp.post("/recommendations/generate")
@login_required
def generate_recommendations():
    month = dates.parse_month(request.form.get("month"))
    label = dates.month_label(month)
    _i, _e, _b, summary = _load(g.user.id, month)
    target = url_for("main.recommendations", month=month)
    if not summary["has_data"]:
        flash(f"Add some income or expenses for {label} first.", "error")
        return redirect(target)

    cfg = current_app.config
    fmt = _fmt()
    source = "rules"
    if ai.is_configured(cfg["GEMINI_API_KEY"]):
        try:
            advice = ai.generate_advice(summary, label, cfg["GEMINI_API_KEY"], cfg["GEMINI_MODEL"],
                                        cfg["CURRENCY_SYMBOL"], cfg["GEMINI_TIMEOUT"])
            source = "gemini"
        except ai.AIUnavailable as exc:
            flash(f"Gemini advice was unavailable ({exc}). Showing built-in advice instead.", "warning")
            advice = finance.rule_based_advice(summary, fmt)
        except Exception:  # never let an AI problem break the page
            current_app.logger.exception("Unexpected error while calling Gemini")
            flash("Gemini advice was unavailable. Showing built-in advice instead.", "warning")
            advice = finance.rule_based_advice(summary, fmt)
    else:
        flash("No Gemini API key is set, so this advice comes from built-in rules. "
              "Add GEMINI_API_KEY to your .env file to turn on AI advice.", "info")
        advice = finance.rule_based_advice(summary, fmt)

    if _save_advice(g.user.id, month, advice, source):
        if source == "gemini":
            flash("Fresh advice generated with Gemini.", "success")
    else:
        flash("Could not save the advice. Please try again.", "error")
    return redirect(target)


# ---------------------------------------------------------------- report
def _report_data(month):
    incomes, expenses, _budgets, summary = _load(g.user.id, month)
    _pi, _pe, _pb, prev = _load(g.user.id, dates.shift_month(month, -1))
    compare = None
    if prev["has_data"]:
        compare = {
            "income": summary["total_income"] - prev["total_income"],
            "expenses": summary["total_expenses"] - prev["total_expenses"],
            "savings": summary["savings"] - prev["savings"],
        }
    by_source = {}
    for i in incomes:
        by_source[i.source] = by_source.get(i.source, 0.0) + i.amount
    return incomes, expenses, summary, compare, sorted(by_source.items(), key=lambda kv: -kv[1])


@bp.route("/report")
@login_required
def report():
    ctx = _month_ctx(request.args.get("month"))
    incomes, expenses, summary, compare, by_source = _report_data(ctx["month"])
    advice, source, created = _saved_advice(g.user.id, ctx["month"])
    if advice is None:
        advice, source = finance.rule_based_advice(summary, _fmt()), "rules"
    return render_template(
        "report.html", summary=summary, compare=compare, by_source=by_source,
        advice=advice, advice_source=source, generated_on=datetime.now().strftime("%d %b %Y"), **ctx)


@bp.route("/report.csv")
@login_required
def report_csv():
    month = dates.parse_month(request.args.get("month"))
    incomes, expenses, summary, _compare, _by_source = _report_data(month)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Personal Finance Advisor Bot - monthly report", dates.month_label(month)])
    writer.writerow([])
    writer.writerow(["Total income", summary["total_income"]])
    writer.writerow(["Total expenses", summary["total_expenses"]])
    writer.writerow(["Savings", summary["savings"]])
    rate = summary["savings_rate"]
    writer.writerow(["Savings rate", f"{rate * 100:.1f}%" if rate is not None else "n/a"])
    writer.writerow([])
    writer.writerow(["Category", "Spent", "Budget limit", "Status"])
    for r in summary["rows"]:
        if r["spent"] or r["limit"]:
            writer.writerow([r["category"], r["spent"], r["limit"] or "", r["status"]])
    writer.writerow([])
    writer.writerow(["Income entries"])
    writer.writerow(["Date", "Source", "Amount"])
    for i in incomes:
        writer.writerow([i.received_on.isoformat(), _csv_safe(i.source), i.amount])
    writer.writerow([])
    writer.writerow(["Expense entries"])
    writer.writerow(["Date", "Category", "Description", "Amount"])
    for e in expenses:
        writer.writerow([e.spent_on.isoformat(), e.category, _csv_safe(e.description or ""), e.amount])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="finance-report-{month}.csv"'})
