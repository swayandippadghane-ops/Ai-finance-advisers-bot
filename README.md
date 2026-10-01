# Personal Finance Advisor Bot

An AI-powered personal finance web app built with **Flask, SQLAlchemy (SQLite), Jinja2, HTML/CSS/JavaScript and the Gemini API**.

Users register, record income, log expenses by category, get a budget built from their own numbers, see overspending flagged, and receive saving advice from Gemini AI. A monthly report can be printed or exported to CSV.

## Features

- Registration, login and logout with hashed passwords, CSRF protection and a login attempt limiter
- Dashboard with income, expenses, savings, savings rate, a spending donut chart and budget bars
- Income tracking (several sources per month) and expense tracking in 9 categories: Food, Rent, Transport, Education, Shopping, Entertainment, Utilities, Healthcare, Other
- Budget planner: one click builds a 50/30/20 budget from your income and recent spending; every limit is editable
- Overspending alerts per category with saving suggestions
- Gemini AI advice (overspending areas, saving tips, emergency fund, next-month goal), with automatic built-in fallback if no key is set or Gemini is unavailable
- Monthly report with month-over-month comparison, print/PDF and CSV export
- Input validation on every form, friendly error pages, responsive layout with dark mode

## Project structure

```
finance_advisor/
├── app.py              Flask app factory (run this)
├── config.py           Settings read from .env
├── extensions.py       SQLAlchemy instance
├── models.py           User, Income, Expense, Budget, Recommendation
├── routes/             auth.py (login/register) and main.py (everything else)
├── services/           finance.py (calculations), ai.py (Gemini), validation.py, dates.py
├── templates/          Jinja2 pages
├── static/             css/style.css and js/app.js
├── tests/              End-to-end tests
├── seed_demo.py        Creates a demo account with sample data
├── requirements.txt    Python packages
├── .env.example        Template for your secrets
└── .gitignore          Keeps .env and the database out of Git
```

## Run it in VS Code

1. Install **Python 3.10 or newer** from python.org (on Windows tick "Add python.exe to PATH").
2. In VS Code choose **File > Open Folder** and open the `finance_advisor` folder.
3. Open the terminal with **Ctrl+`** and create a virtual environment.

   Windows (PowerShell):
   ```
   python -m venv venv
   venv\Scripts\Activate.ps1
   ```
   If PowerShell blocks the script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and try again.

   macOS / Linux:
   ```
   python3 -m venv venv
   source venv/bin/activate
   ```
4. When VS Code asks, select the interpreter inside `venv` (or press **Ctrl+Shift+P**, choose **Python: Select Interpreter**).
5. Install the packages:
   ```
   pip install -r requirements.txt
   ```
6. Create your settings file by copying the template:

   Windows: `copy .env.example .env`   macOS / Linux: `cp .env.example .env`

   Open `.env` and set:
   - `SECRET_KEY` to a long random string. Generate one with
     `python -c "import secrets; print(secrets.token_hex(32))"`
   - `GEMINI_API_KEY` to your key from https://aistudio.google.com/apikey (optional: the app works without it using built-in advice)
7. Start the app:
   ```
   python app.py
   ```
8. Open http://127.0.0.1:5000 in your browser. The database file (`instance/finance.db`) is created automatically.

### Try it with sample data

```
python seed_demo.py
```
Then log in with `demo@example.com` and `Demo@1234`.

### Run the tests

```
python -m unittest discover -s tests -t . -v
```

## Gemini setup and privacy

The key is read only from `.env` (never from the code). The default model is `gemini-3.5-flash`; if Google retires it, set `GEMINI_MODEL` in `.env` to a current model name. Only category totals are sent to Gemini. Names, emails and expense notes are never sent.

## Upload to GitHub

1. Make sure `.env` is not tracked: `git status` must not list it (it is in `.gitignore`).
2. Create an empty repository on github.com (no README, no .gitignore), for example `personal-finance-advisor-bot`.
3. In the VS Code terminal:
   ```
   git init
   git add .
   git commit -m "Personal Finance Advisor Bot"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/personal-finance-advisor-bot.git
   git push -u origin main
   ```
   (VS Code's **Source Control** panel does the same with its Commit and Publish Branch buttons.)
4. If a key was ever pushed by mistake, delete it in Google AI Studio and create a new one.

## Public demo

### Option A: ngrok (quickest, runs from your laptop)

1. Install ngrok from ngrok.com and run `ngrok config add-authtoken YOUR_TOKEN` once.
2. Keep `python app.py` running, and in a second terminal run `ngrok http 5000`.
3. Copy the `https://...ngrok-free.app` address it shows and use it as your demo link. In `.env` set `SESSION_COOKIE_SECURE=1` and restart the app.

The link works only while your computer, the app and ngrok are all running.

### Option B: Render (stays online)

1. Push the project to GitHub (above).
2. On render.com choose **New > Web Service** and connect the repository.
3. Build command: `pip install -r requirements.txt`
   Start command: `gunicorn "app:create_app()" --workers 1 --threads 4`
4. Under **Environment** add `SECRET_KEY`, `GEMINI_API_KEY`, `GEMINI_MODEL` and `SESSION_COOKIE_SECURE=1`.
5. Deploy and use the `https://....onrender.com` address as your demo link.

On Render's free plan the SQLite file is wiped on each redeploy and restart. That is fine for a demo; for permanent data use a managed Postgres database, add `psycopg2-binary` to `requirements.txt` and set `DATABASE_URL`.

## Troubleshooting

- **"No module named flask_sqlalchemy"**: the virtual environment is not active or step 5 was skipped.
- **Advice says "Built-in advice"**: `GEMINI_API_KEY` is missing in `.env`, or Gemini returned an error; the message on screen says which.
- **Logged out after every restart**: set `SECRET_KEY` in `.env`.
- **Port 5000 busy** (macOS AirPlay): run with `PORT=5001 python app.py` (PowerShell: `$env:PORT=5001; python app.py`).
- **Start fresh**: stop the app and delete the `instance` folder.

Advice in this app is general budgeting guidance, not professional financial advice.
