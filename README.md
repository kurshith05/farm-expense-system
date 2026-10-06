# Farm Expense Management System

Flask (Python) + HTML/CSS/JS + Postgres database hosted on Supabase. Deployed on Vercel from GitHub.

## Run on your own Windows computer (VS Code)
1. Install Python 3.10+ (tick **Add Python to PATH**). Open the folder that contains `app.py` in VS Code.
2. Terminal: `python -m venv venv` then `venv\Scripts\activate` then `pip install -r requirements.txt`
3. Create your Supabase database first (see `DEPLOY.md`, Part 1).
4. Copy `.env.example` to `.env` (`copy .env.example .env`) and fill in `SECRET_KEY` and `DATABASE_URL`.
5. Create the tables once: `python app.py initdb`
6. Start: `python app.py`, then open http://127.0.0.1:5000
7. Stop: press **Ctrl + C** in the terminal.

## Files
- `app.py` - backend: login, validation, database queries, dashboard, reports, CSV export.
- `schema.sql` - Postgres tables (users, expenses, settings). Money is stored as integer cents.
- `templates/` - HTML pages. `base.html` has the header bar and sidebar.
- `public/css/style.css`, `public/js/app.js` - styling and small scripts (Vercel serves `public/`).
- `requirements.txt` - Python packages. `.env.example` - template for secret settings.
- `DEPLOY.md` - Supabase + GitHub + Vercel steps. `.gitignore` - keeps `.env` and `venv` off GitHub.

## Manual test checklist
- Register; same email again (rejected); wrong password (rejected); log in and out (power icon, top right).
- Add expense (success message); amount 0, empty description, bad date (rejected).
- Edit, then delete (confirmation appears). Dashboard figures change after each.
- Manage Expenses: search, date range, category, crop together; count and total update; Export CSV matches.
- Budget & Reports: save budget/revenue; negative values rejected; 80% warning and over-100% warning; category summary; Print / Save as PDF.
- Settings: change name and password; add/remove [SAMPLE] data (real records untouched).
- Register a second user: they see none of the first user's data, and `/expenses/1/edit` gives "Not Found".

## Known limits
- No password reset (needs email sending to be configured) - future improvement.
- Supabase free projects pause after about a week of inactivity; restore from the Supabase dashboard.
