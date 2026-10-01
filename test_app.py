"""End-to-end smoke tests. Run from the project folder with:

    python -m unittest discover -s tests -t . -v
"""
import unittest
from datetime import date
from unittest import mock

from app import create_app
from services import dates


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SECRET_KEY": "test-secret",
            "GEMINI_API_KEY": "",
        })
        self.client = self.app.test_client()
        self.month = dates.current_month()
        self.today = date.today().isoformat()

    # ---- helpers
    def token(self):
        self.client.get("/login")
        with self.client.session_transaction() as sess:
            return sess["_csrf"]

    def post(self, url, data=None, **kwargs):
        payload = dict(data or {})
        payload["csrf_token"] = self.token()
        return self.client.post(url, data=payload, **kwargs)

    def register(self, email="asha@example.com", name="Asha Rao"):
        return self.post("/register", {
            "name": name, "email": email,
            "password": "Passw0rd1", "confirm_password": "Passw0rd1",
        }, follow_redirects=True)

    def add_income(self, amount="60000"):
        return self.post("/income/add", {"amount": amount, "source": "Salary", "date": self.today,
                                         "month": self.month, "back": "dashboard"}, follow_redirects=True)

    def add_expense(self, amount, category="Food", note="Lunch"):
        return self.post("/expenses/add", {"amount": amount, "category": category, "description": note,
                                           "date": self.today, "month": self.month, "back": "dashboard"},
                         follow_redirects=True)

    # ---- tests
    def test_pages_require_login(self):
        for url in ("/dashboard", "/income", "/expenses", "/budget", "/recommendations", "/report"):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302, url)
            self.assertIn("/login", resp.headers["Location"])

    def test_register_login_logout(self):
        resp = self.register()
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Hello, Asha", resp.data)
        self.post("/logout")
        self.assertEqual(self.client.get("/dashboard").status_code, 302)
        bad = self.post("/login", {"email": "asha@example.com", "password": "wrong-pass1"})
        self.assertEqual(bad.status_code, 401)
        good = self.post("/login", {"email": "ASHA@example.com", "password": "Passw0rd1"},
                         follow_redirects=True)
        self.assertIn(b"Hello, Asha", good.data)

    def test_registration_validation(self):
        resp = self.post("/register", {"name": "A", "email": "nope", "password": "short",
                                       "confirm_password": "other"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn(b"valid email", resp.data)
        self.register()
        self.post("/logout")
        dup = self.register()
        self.assertIn(b"already exists", dup.data)

    def test_csrf_is_enforced(self):
        self.client.get("/login")
        resp = self.client.post("/login", data={"email": "a@b.co", "password": "x"})
        self.assertEqual(resp.status_code, 400)

    def test_open_redirect_blocked(self):
        self.register()
        self.post("/logout")
        resp = self.post("/login?next=//evil.example", {"email": "asha@example.com",
                                                          "password": "Passw0rd1",
                                                          "next": "//evil.example"})
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("evil.example", resp.headers["Location"])

    def test_income_expense_totals_and_validation(self):
        self.register()
        self.add_income("60000")
        self.add_expense("18000", "Rent", "Rent")
        resp = self.add_expense("2500.50", "Food")
        self.assertIn("20,500".encode(), resp.data)       # 18000 + 2500.5 rounded
        self.assertIn("39,500".encode(), resp.data)       # savings
        for bad in ("-5", "abc", "0", ""):
            resp = self.add_expense(bad)
            self.assertIn(b"Expense amount", resp.data)
        resp = self.add_expense("100", "NotACategory")
        self.assertIn(b"valid category", resp.data)

    def test_edit_and_delete_expense_and_isolation(self):
        self.register()
        self.add_expense("500", "Food", "Snack")
        page = self.client.get("/expenses")
        self.assertIn(b"Snack", page.data)
        self.post("/expenses/1/edit", {"amount": "750", "category": "Shopping",
                                       "date": self.today, "description": "Gadget"})
        self.assertIn(b"Gadget", self.client.get("/expenses").data)
        # a second user cannot touch the first user's data
        self.post("/logout")
        self.register("other@example.com", "Other Person")
        self.assertEqual(self.client.get("/expenses/1/edit").status_code, 404)
        self.assertEqual(self.post("/expenses/1/delete").status_code, 404)
        self.post("/logout")
        self.post("/login", {"email": "asha@example.com", "password": "Passw0rd1"})
        self.post("/expenses/1/delete")
        self.assertNotIn(b"Gadget", self.client.get("/expenses").data)

    def test_budget_generation_and_overspending(self):
        self.register()
        resp = self.post("/budget/generate", {"month": self.month}, follow_redirects=True)
        self.assertIn(b"Add income", resp.data)
        self.add_income("50000")
        resp = self.post("/budget/generate", {"month": self.month}, follow_redirects=True)
        self.assertIn(b"Suggested budget created", resp.data)
        self.post("/budget/save", {"month": self.month, "limit_Shopping": "1000"})
        self.add_expense("4000", "Shopping", "Shoes")
        dash = self.client.get("/dashboard")
        self.assertIn(b"Overspending alerts", dash.data)
        self.assertIn(b"Over budget", dash.data)

    def test_budget_rejects_bad_limit(self):
        self.register()
        resp = self.post("/budget/save", {"month": self.month, "limit_Food": "abc"}, follow_redirects=True)
        self.assertIn(b"Food limit must be a number", resp.data)

    def test_recommendations_fallback_without_key(self):
        self.register()
        empty = self.post("/recommendations/generate", {"month": self.month}, follow_redirects=True)
        self.assertIn(b"Add some income or expenses", empty.data)
        self.add_income("40000")
        self.add_expense("45000", "Shopping")
        resp = self.post("/recommendations/generate", {"month": self.month}, follow_redirects=True)
        self.assertIn(b"No Gemini API key", resp.data)
        self.assertIn(b"Built-in advice", resp.data)
        self.assertIn(b"Overspending areas", resp.data)

    def test_recommendations_with_mocked_gemini(self):
        self.app.config["GEMINI_API_KEY"] = "AIzaFakeKeyForTests"
        self.register()
        self.add_income("40000")
        self.add_expense("5000", "Food")
        body = {"candidates": [{"content": {"parts": [{"text":
            '{"summary":"A calm month overall.","overspending":[],"saving_tips":["Cook at home"],'
            '"emergency_fund":"Build three months.","next_month_goal":"Save 20%."}'}]}}]}
        fake = mock.Mock(status_code=200)
        fake.json.return_value = body
        with mock.patch("services.ai.requests.post", return_value=fake):
            resp = self.post("/recommendations/generate", {"month": self.month}, follow_redirects=True)
        self.assertIn(b"A calm month overall.", resp.data)
        self.assertIn(b"Generated by Gemini AI", resp.data)

    def test_gemini_failure_falls_back(self):
        self.app.config["GEMINI_API_KEY"] = "AIzaFakeKeyForTests"
        self.register()
        self.add_income("40000")
        self.add_expense("5000", "Food")
        fake = mock.Mock(status_code=429)
        fake.json.return_value = {}
        with mock.patch("services.ai.requests.post", return_value=fake):
            resp = self.post("/recommendations/generate", {"month": self.month}, follow_redirects=True)
        self.assertIn(b"Gemini advice was unavailable", resp.data)
        self.assertIn(b"Built-in advice", resp.data)

    def test_report_and_csv(self):
        self.register()
        self.add_income("40000")
        self.add_expense("1200", "Food", "=HYPERLINK(\"x\")")
        report = self.client.get("/report")
        self.assertEqual(report.status_code, 200)
        self.assertIn(b"Financial summary", report.data)
        csv_resp = self.client.get("/report.csv")
        self.assertEqual(csv_resp.status_code, 200)
        self.assertEqual(csv_resp.mimetype, "text/csv")
        self.assertIn(b"'=HYPERLINK", csv_resp.data)  # formula injection neutralised

    def test_error_pages_and_health(self):
        self.assertEqual(self.client.get("/nope").status_code, 404)
        self.assertIn(b"does not exist", self.client.get("/nope").data)
        self.assertEqual(self.client.get("/healthz").get_json(), {"status": "ok"})
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_invalid_month_falls_back(self):
        self.register()
        self.assertEqual(self.client.get("/dashboard?month=garbage").status_code, 200)
        self.assertEqual(self.client.get("/dashboard?month=2026-13").status_code, 200)


if __name__ == "__main__":
    unittest.main()
