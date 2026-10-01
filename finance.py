"""Financial calculations. Pure Python: no Flask or database code in here."""
import math

CATEGORIES = [
    "Food", "Rent", "Transport", "Education", "Shopping",
    "Entertainment", "Utilities", "Healthcare", "Other",
]

# Share of the "needs" pool (50% of income) and "wants" pool (30%) per category.
NEEDS = {"Rent": 0.45, "Food": 0.20, "Transport": 0.10,
         "Education": 0.10, "Utilities": 0.10, "Healthcare": 0.05}
WANTS = {"Shopping": 0.40, "Entertainment": 0.40, "Other": 0.20}

CATEGORY_COLORS = {
    "Food": "#C9822B", "Rent": "#1F5F73", "Transport": "#4F8A5B",
    "Education": "#7A5AA6", "Shopping": "#C4507A", "Entertainment": "#D0A21E",
    "Utilities": "#5C7A8C", "Healthcare": "#B8322A", "Other": "#8A8F86",
}

CATEGORY_TIPS = {
    "Food": "Plan meals for the week and cook at home more often; eating out is usually the easiest food saving.",
    "Rent": "Rent is hard to change quickly. Consider renegotiating at renewal or sharing the space.",
    "Transport": "Combine trips, use a transit pass where possible, and compare fuel and cab costs.",
    "Education": "Look for free or discounted material, library copies and student pricing.",
    "Shopping": "Wait 48 hours before non-essential purchases and remove saved cards from shopping apps.",
    "Entertainment": "Cancel subscriptions you rarely use and swap one paid outing a month for a free one.",
    "Utilities": "Switch off standby devices, use efficient bulbs and compare your phone and internet plans.",
    "Healthcare": "Ask for generic medicines and use preventive check-ups to avoid bigger bills later.",
    "Other": "Review this category for one-off items and give recurring ones their own category.",
}


def format_money(value, symbol="\u20b9"):
    """Format a number as money. Rupee amounts use Indian digit grouping."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    whole = int(round(abs(number)))
    digits = str(whole)
    if symbol == "\u20b9" and len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        digits = ",".join(parts + [tail])
    else:
        digits = f"{whole:,}"
    sign = "-" if number < 0 and whole else ""
    return f"{sign}{symbol}{digits}"


def health_score(total_income, total_expenses, budgeted_count, over_count):
    """0-100: half from savings rate (20% earns full marks), half from budget adherence."""
    if total_income <= 0 and total_expenses <= 0:
        return 0, "Not enough data"
    rate = (total_income - total_expenses) / total_income if total_income > 0 else -1.0
    saving_points = max(0.0, min(1.0, rate / 0.20)) * 50
    if budgeted_count == 0:
        adherence = 0.5
    else:
        adherence = (budgeted_count - over_count) / budgeted_count
    score = int(round(saving_points + adherence * 50))
    if score >= 75:
        label = "Strong"
    elif score >= 50:
        label = "Steady"
    elif score >= 25:
        label = "Needs attention"
    else:
        label = "At risk"
    return score, label


def donut_css(rows):
    """CSS conic-gradient for the spending donut chart."""
    total = sum(r["spent"] for r in rows)
    if total <= 0:
        return "conic-gradient(var(--line) 0% 100%)"
    segments, acc = [], 0.0
    for r in rows:
        if r["spent"] <= 0:
            continue
        start = acc
        acc += r["spent"] / total * 100
        segments.append(f"{r['color']} {start:.2f}% {acc:.2f}%")
    return "conic-gradient(" + ", ".join(segments) + ")"


def summarize(income_amounts, expenses, budgets):
    """Build the full month summary.

    income_amounts: list of numbers
    expenses: list of dicts with category, amount, description, date
    budgets: dict of category -> monthly limit
    """
    total_income = round(sum(income_amounts), 2)
    total_expenses = round(sum(e["amount"] for e in expenses), 2)
    savings = round(total_income - total_expenses, 2)
    savings_rate = savings / total_income if total_income > 0 else None

    spent = {c: 0.0 for c in CATEGORIES}
    for e in expenses:
        if e["category"] in spent:
            spent[e["category"]] += e["amount"]

    rows = []
    for c in CATEGORIES:
        amount = round(spent[c], 2)
        limit = float(budgets.get(c) or 0)
        share = amount / total_expenses * 100 if total_expenses > 0 else 0.0
        if limit > 0:
            pct_used = amount / limit * 100
            status = "over" if amount > limit else ("warning" if pct_used >= 85 else "ok")
            bar_pct = min(pct_used, 100.0)
            over_by = max(0.0, amount - limit)
        else:
            pct_used, status, bar_pct, over_by = None, "none", share, 0.0
        rows.append({
            "category": c, "spent": amount, "limit": limit, "share": share,
            "pct_used": pct_used, "status": status, "bar_pct": bar_pct,
            "over_by": round(over_by, 2), "color": CATEGORY_COLORS[c],
        })

    over_categories = [r for r in rows if r["status"] == "over"]
    budgeted = [r for r in rows if r["limit"] > 0]
    total_budget = round(sum(r["limit"] for r in budgeted), 2)
    score, label = health_score(total_income, total_expenses, len(budgeted), len(over_categories))
    top = sorted(expenses, key=lambda e: e["amount"], reverse=True)[:5]

    return {
        "total_income": total_income,
        "total_expenses": total_expenses,
        "savings": savings,
        "savings_rate": savings_rate,
        "rows": rows,
        "over_categories": over_categories,
        "total_budget": total_budget,
        "budget_used_pct": (total_expenses / total_budget * 100) if total_budget > 0 else None,
        "needs_spent": round(sum(r["spent"] for r in rows if r["category"] in NEEDS), 2),
        "wants_spent": round(sum(r["spent"] for r in rows if r["category"] in WANTS), 2),
        "health_score": score,
        "health_label": label,
        "top_expenses": top,
        "donut_css": donut_css(rows),
        "expense_count": len(expenses),
        "has_data": bool(total_income > 0 or expenses),
    }


def _round10(value):
    return int(round(value / 10.0)) * 10


def suggest_budget(income, history):
    """Suggest category limits from income using a 50/30/20 plan.

    history: dict of category -> average monthly spend (may be empty). Each
    category's share blends the default weight with the user's own habits.
    Returns (budgets, savings_target).
    """
    budgets = {}
    for pool_share, weights in ((0.50, NEEDS), (0.30, WANTS)):
        pool = income * pool_share
        hist_total = sum(history.get(c, 0.0) for c in weights)
        for category, weight in weights.items():
            if hist_total > 0:
                share = 0.5 * weight + 0.5 * history.get(category, 0.0) / hist_total
            else:
                share = weight
            budgets[category] = _round10(pool * share)
    return budgets, round(income * 0.20, 2)


def rule_based_advice(summary, fmt):
    """Built-in advice, same shape as the Gemini response. fmt formats money."""
    income = summary["total_income"]
    spent = summary["total_expenses"]
    savings = summary["savings"]
    rate = summary["savings_rate"]
    rows = summary["rows"]

    if not summary["has_data"]:
        return {
            "summary": "Add some income and expenses for this month to get advice.",
            "overspending": [], "saving_tips": [],
            "emergency_fund": "", "next_month_goal": "",
        }

    if income > 0:
        text = (f"You earned {fmt(income)} and spent {fmt(spent)}, "
                f"{'saving ' + fmt(savings) if savings >= 0 else 'overspending by ' + fmt(-savings)}"
                f" ({rate * 100:.0f}% of income).")
    else:
        text = f"You spent {fmt(spent)} this month and no income is recorded yet."

    overspending = []
    for r in summary["over_categories"]:
        overspending.append({
            "category": r["category"],
            "issue": f"Spent {fmt(r['spent'])} against a limit of {fmt(r['limit'])}, which is {fmt(r['over_by'])} over.",
            "fix": CATEGORY_TIPS[r["category"]],
        })
    if income > 0 and spent > income:
        overspending.append({
            "category": "Overall",
            "issue": f"Total spending is {fmt(spent - income)} higher than income.",
            "fix": "Pause non-essential spending until the month balances, and check the largest categories first.",
        })
    if not overspending and summary["total_budget"] == 0 and income > 0 and summary["wants_spent"] > 0.30 * income:
        wants = [r for r in rows if r["category"] in WANTS and r["spent"] > 0]
        top = max(wants, key=lambda r: r["spent"])
        overspending.append({
            "category": top["category"],
            "issue": f"Wants spending is {fmt(summary['wants_spent'])}, above the 30% guide ({fmt(income * 0.30)}).",
            "fix": CATEGORY_TIPS[top["category"]],
        })

    tips = []
    if income > 0 and (rate is None or rate < 0.20):
        tips.append(f"Aim to save at least 20% of income, which is {fmt(income * 0.20)} a month.")
    wants_rows = sorted((r for r in rows if r["category"] in WANTS and r["spent"] > 0),
                        key=lambda r: r["spent"], reverse=True)
    if wants_rows:
        r = wants_rows[0]
        tips.append(f"Trim {r['category']} by 15% to free up about {fmt(r['spent'] * 0.15)} a month.")
    tips.append("Move your savings out on payday so you save first and spend what is left.")
    if summary["total_budget"] == 0:
        tips.append("Set category limits on the Budget page so overspending is flagged early.")
    else:
        tips.append("Review each category's limit once a month and adjust it to what is realistic.")

    if spent > 0 and savings > 0:
        target = spent * 3
        months = math.ceil(target / savings)
        emergency = (f"A three-month cushion is about {fmt(target)}. Saving {fmt(savings)} a month "
                     f"would build it in roughly {months} month{'s' if months != 1 else ''}.")
    elif spent > 0:
        emergency = (f"A three-month cushion is about {fmt(spent * 3)}. Start with a small fixed "
                     f"amount each payday, even {fmt(max(500, spent * 0.02))}, and grow it over time.")
    else:
        emergency = "Once you log expenses, this will show a three-month cushion target."

    if savings < 0:
        goal = f"Bring spending back under income by cutting at least {fmt(-savings)}."
    elif income > 0 and rate < 0.20:
        goal = f"Raise savings to {fmt(income * 0.20)} (20% of income)."
    else:
        goal = f"Keep saving at least {fmt(max(savings, 0))} and put it toward your emergency fund."

    return {
        "summary": text, "overspending": overspending, "saving_tips": tips[:5],
        "emergency_fund": emergency, "next_month_goal": goal,
    }
