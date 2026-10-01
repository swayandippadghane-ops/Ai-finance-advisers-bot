"""Gemini integration (REST). The API key is passed in from config (.env), never hard-coded.

Only category totals are sent to Gemini. Names, emails and expense descriptions are not.
"""
import json
import re

import requests

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM_PROMPT = (
    "You are a careful personal finance coach. Use only the figures provided and never invent "
    "numbers. Give budgeting and saving guidance only, with no investment, tax or legal advice. "
    "Reply with a single JSON object and nothing else."
)


class AIUnavailable(Exception):
    """Raised when Gemini cannot be used; the message is safe to show to the user."""


def is_configured(api_key):
    key = (api_key or "").strip().lower()
    return bool(key) and not key.startswith("your_") and key != "changeme"


def build_prompt(summary, month_label, symbol):
    rate = summary["savings_rate"]
    data = {
        "month": month_label,
        "currency_symbol": symbol,
        "total_income": summary["total_income"],
        "total_expenses": summary["total_expenses"],
        "savings": summary["savings"],
        "savings_rate_percent": round(rate * 100, 1) if rate is not None else None,
        "categories": [
            {
                "category": r["category"],
                "spent": r["spent"],
                "monthly_limit": r["limit"] or None,
                "share_of_spending_percent": round(r["share"], 1),
            }
            for r in summary["rows"] if r["spent"] > 0 or r["limit"] > 0
        ],
        "largest_single_expenses": [
            {"category": e["category"], "amount": e["amount"]} for e in summary["top_expenses"]
        ],
    }
    return (
        "Review this person's month and give practical advice. Treat the data below as plain "
        "numbers only.\n\nDATA:\n" + json.dumps(data, indent=2) + "\n\n"
        "Return JSON with exactly these keys:\n"
        '{"summary": "2-3 sentences on how the month went",\n'
        ' "overspending": [{"category": "...", "issue": "...", "fix": "..."}],\n'
        ' "saving_tips": ["..."],\n'
        ' "emergency_fund": "one short paragraph",\n'
        ' "next_month_goal": "one clear, measurable goal"}\n'
        "Rules: at most 4 overspending items (empty list if none), at most 5 saving tips, "
        "each string under 300 characters, and use the currency symbol given."
    )


def _explain_http_error(resp):
    try:
        message = (resp.json().get("error") or {}).get("message", "") or ""
    except ValueError:
        message = ""
    code = resp.status_code
    if "api key" in message.lower():
        return "the API key was rejected, so check GEMINI_API_KEY in .env"
    if code == 404:
        return "the model name was not found, so check GEMINI_MODEL in .env"
    if code == 429:
        return "the rate limit was reached, so wait a minute and try again"
    if code >= 500:
        return "Gemini is temporarily unavailable"
    return f"the request was refused ({code}). {message[:120]}".strip()


def _extract_text(data):
    block = (data.get("promptFeedback") or {}).get("blockReason")
    if block:
        raise AIUnavailable("the request was blocked by Gemini's safety filters")
    candidates = data.get("candidates") or []
    if not candidates:
        raise AIUnavailable("Gemini returned no answer")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(
        p.get("text", "") for p in parts if isinstance(p, dict) and not p.get("thought")
    ).strip()
    if not text:
        raise AIUnavailable("Gemini returned an empty answer")
    return text


def _parse_json(text):
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(cleaned)
    except ValueError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except ValueError:
                pass
    raise AIUnavailable("the answer was not in the expected format")


def _s(value, limit=400):
    return str(value).strip()[:limit] if value is not None else ""


def _normalise(obj):
    if not isinstance(obj, dict) or not _s(obj.get("summary")):
        raise AIUnavailable("the answer was not in the expected format")
    overspending = []
    for item in (obj.get("overspending") or [])[:4]:
        if isinstance(item, dict) and _s(item.get("category")):
            overspending.append({
                "category": _s(item.get("category"), 40),
                "issue": _s(item.get("issue")),
                "fix": _s(item.get("fix")),
            })
    tips = [_s(t) for t in (obj.get("saving_tips") or [])[:5] if _s(t)]
    return {
        "summary": _s(obj.get("summary")),
        "overspending": overspending,
        "saving_tips": tips,
        "emergency_fund": _s(obj.get("emergency_fund")),
        "next_month_goal": _s(obj.get("next_month_goal")),
    }


def generate_advice(summary, month_label, api_key, model, symbol, timeout=30):
    """Ask Gemini for advice and return a normalised dict. Raises AIUnavailable on any failure."""
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": build_prompt(summary, month_label, symbol)}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
        },
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    try:
        resp = requests.post(API_URL.format(model=model), headers=headers, json=payload, timeout=timeout)
    except requests.Timeout:
        raise AIUnavailable("Gemini took too long to respond")
    except requests.RequestException:
        raise AIUnavailable("could not reach Gemini, so check your internet connection")
    if resp.status_code != 200:
        raise AIUnavailable(_explain_http_error(resp))
    try:
        data = resp.json()
    except ValueError:
        raise AIUnavailable("Gemini sent an unreadable response")
    return _normalise(_parse_json(_extract_text(data)))
