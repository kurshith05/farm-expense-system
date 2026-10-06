"""Farm Expense Management System - Flask backend (Stage 1)."""
import csv, io, os, re, sys
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps

import psycopg
from dotenv import load_dotenv
from flask import (Flask, Response, abort, flash, g, redirect,
                   render_template, request, session, url_for)
from flask_wtf.csrf import CSRFProtect
from psycopg.rows import dict_row
from werkzeug.security import check_password_hash, generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE, ".env"))   # reads SECRET_KEY from the .env file (local use)
PRODUCTION = os.environ.get("PRODUCTION") == "1" or bool(os.environ.get("VERCEL"))  # True on the live server
DATABASE_URL = os.environ.get("DATABASE_URL")      # Supabase (Postgres) connection string

app = Flask(__name__, static_folder="public", static_url_path="")  # Vercel serves public/
if PRODUCTION and not os.environ.get("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY must be set on the live server.")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or os.urandom(24).hex()
app.config["SESSION_COOKIE_SECURE"] = PRODUCTION   # cookies only over HTTPS when live
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
CSRFProtect(app)                   # every POST form must contain csrf_token

CATEGORIES = ["Seeds", "Fertilizer", "Pesticide", "Fuel", "Labour",
              "Equipment", "Transportation", "Others"]
PAYMENTS = ["Cash", "Bank Transfer", "Card", "E-wallet"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------- database helpers ----------
def get_db():
    if "db" not in g:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not set. Add it to your .env file (see README).")
        # prepare_threshold=None is needed for Supabase's connection pooler
        g.db = psycopg.connect(DATABASE_URL, row_factory=dict_row, prepare_threshold=None)
    return g.db

@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db:
        db.close()

def init_db():
    """Create the tables in the database (run once: python app.py initdb)."""
    with psycopg.connect(DATABASE_URL, prepare_threshold=None) as db:
        with open(os.path.join(BASE, "schema.sql")) as f:
            db.execute(f.read())

@app.template_filter("rm")
def rm(cents):                     # 12345 -> "RM 123.45"
    return f"RM {cents / 100:,.2f}"


# ---------- login protection ----------
def login_required(view):
    @wraps(view)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapper


# ---------- register / login / logout ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        if not name or not EMAIL_RE.match(email) or len(pw) < 8:
            flash("Enter your name, a valid email, and a password of at least 8 characters.", "error")
        else:
            db = get_db()
            if db.execute("SELECT 1 FROM users WHERE email=%s", (email,)).fetchone():
                flash("That email is already registered. Try logging in.", "error")
            else:
                db.execute("INSERT INTO users(name,email,password_hash) VALUES(%s,%s,%s)",
                           (name, email, generate_password_hash(pw)))
                db.commit()
                flash("Account created. You can log in now.", "success")
                return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = get_db().execute("SELECT * FROM users WHERE email=%s", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"], session["user_name"] = user["id"], user["name"]
            session["user_email"] = user["email"]
            return redirect(url_for("dashboard"))
        flash("Incorrect email or password.", "error")
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))

@app.route("/")
def home():
    return redirect(url_for("dashboard" if "user_id" in session else "login"))


# ---------- expense validation ----------
def read_expense_form(form):
    """Return (clean_values, errors). Money is converted to integer cents."""
    errors, v = [], {}
    v["category"] = form.get("category", "")
    v["description"] = form.get("description", "").strip()
    v["expense_date"] = form.get("expense_date", "")
    v["crop"] = form.get("crop", "").strip()
    v["payment_method"] = form.get("payment_method", "")
    v["amount"] = form.get("amount", "").strip()
    if v["category"] not in CATEGORIES: errors.append("Choose a category.")
    if not v["description"]: errors.append("Description is required.")
    if v["payment_method"] not in PAYMENTS: errors.append("Choose a payment method.")
    try:
        datetime.strptime(v["expense_date"], "%Y-%m-%d")
    except ValueError:
        errors.append("Enter a valid transaction date.")
    try:
        amt = Decimal(v["amount"])
        if not amt.is_finite() or amt <= 0 or amt > Decimal("100000000"):
            raise InvalidOperation
        v["amount_cents"] = int((amt * 100).to_integral_value())
    except InvalidOperation:
        errors.append("Amount must be a number greater than 0.")
    return v, errors

def get_own_expense(expense_id):
    """Ownership check: only returns the row if it belongs to the logged-in user."""
    row = get_db().execute("SELECT * FROM expenses WHERE id=%s AND user_id=%s",
                           (expense_id, session["user_id"])).fetchone()
    if row is None:
        abort(404)
    return row


# ---------- add / edit / delete ----------
@app.route("/expenses/add", methods=["GET", "POST"])
@login_required
def add_expense():
    values = {"expense_date": date.today().isoformat()}
    if request.method == "POST":
        values, errors = read_expense_form(request.form)
        if errors:
            for e in errors: flash(e, "error")
        else:
            db = get_db()
            db.execute("""INSERT INTO expenses(user_id,category,description,amount_cents,
                          expense_date,crop,payment_method) VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                       (session["user_id"], values["category"], values["description"],
                        values["amount_cents"], values["expense_date"], values["crop"],
                        values["payment_method"]))
            db.commit()
            flash("Expense saved.", "success")
            return redirect(url_for("add_expense"))
    return render_template("expense_form.html", v=values, editing=False,
                           categories=CATEGORIES, payments=PAYMENTS)

@app.route("/expenses/<int:expense_id>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(expense_id):
    row = get_own_expense(expense_id)
    values = dict(row, amount=f"{row['amount_cents'] / 100:.2f}")
    if request.method == "POST":
        values, errors = read_expense_form(request.form)
        if errors:
            for e in errors: flash(e, "error")
        else:
            db = get_db()
            db.execute("""UPDATE expenses SET category=%s,description=%s,amount_cents=%s,
                          expense_date=%s,crop=%s,payment_method=%s WHERE id=%s AND user_id=%s""",
                       (values["category"], values["description"], values["amount_cents"],
                        values["expense_date"], values["crop"], values["payment_method"],
                        expense_id, session["user_id"]))
            db.commit()
            flash("Expense updated.", "success")
            return redirect(url_for("manage"))
    return render_template("expense_form.html", v=values, editing=True,
                           categories=CATEGORIES, payments=PAYMENTS)

@app.route("/expenses/<int:expense_id>/delete", methods=["POST"])
@login_required
def delete_expense(expense_id):
    get_own_expense(expense_id)
    db = get_db()
    db.execute("DELETE FROM expenses WHERE id=%s AND user_id=%s", (expense_id, session["user_id"]))
    db.commit()
    flash("Expense deleted.", "success")
    return redirect(url_for("manage"))


# ---------- manage: search, filters, CSV ----------
def filtered_expenses():
    """Build one parameterised query from the filters (used by page and CSV)."""
    f = {k: request.args.get(k, "").strip() for k in ("q", "start", "end", "category", "crop")}
    sql, params = "SELECT * FROM expenses WHERE user_id=%s", [session["user_id"]]
    if f["q"]:        sql += " AND description ILIKE %s";  params.append(f"%{f['q']}%")
    if f["start"]:    sql += " AND expense_date >= %s";   params.append(f["start"])
    if f["end"]:      sql += " AND expense_date <= %s";   params.append(f["end"])
    if f["category"]: sql += " AND category = %s";        params.append(f["category"])
    if f["crop"]:     sql += " AND crop ILIKE %s";         params.append(f"%{f['crop']}%")
    rows = get_db().execute(sql + " ORDER BY expense_date DESC, id DESC", params).fetchall()
    return rows, f

@app.route("/expenses")
@login_required
def manage():
    rows, f = filtered_expenses()
    total = sum(r["amount_cents"] for r in rows)
    return render_template("manage.html", rows=rows, f=f, total=total, categories=CATEGORIES)

@app.route("/expenses/export.csv")
@login_required
def export_csv():
    rows, _ = filtered_expenses()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Date", "Category", "Description", "Crop", "Payment method", "Amount (RM)"])
    for r in rows:
        # Prefix risky cells so Excel does not run them as formulas
        desc = ("'" + r["description"]) if r["description"][:1] in "=+-@" else r["description"]
        w.writerow([r["expense_date"], r["category"], desc, r["crop"],
                    r["payment_method"], f"{r['amount_cents'] / 100:.2f}"])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=expenses.csv"})


# ---------- settings: profile, password, budget & revenue ----------
def money_to_cents(text):
    """Non-negative money text -> integer cents, or None if invalid."""
    try:
        d = Decimal(text.strip())
        if not d.is_finite() or d < 0 or d > Decimal("1000000000"):
            return None
        return int((d * 100).to_integral_value())
    except (InvalidOperation, AttributeError):
        return None

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    db, uid = get_db(), session["user_id"]
    if request.method == "POST":
        action = request.form.get("action")
        if action == "profile":
            name = request.form.get("name", "").strip()
            if not name:
                flash("Name cannot be empty.", "error")
            else:
                db.execute("UPDATE users SET name=%s WHERE id=%s", (name, uid))
                db.commit()
                session["user_name"] = name
                flash("Profile updated.", "success")
        elif action == "password":
            user = db.execute("SELECT * FROM users WHERE id=%s", (uid,)).fetchone()
            new = request.form.get("new_password", "")
            if not check_password_hash(user["password_hash"], request.form.get("current_password", "")):
                flash("Current password is incorrect.", "error")
            elif len(new) < 8:
                flash("New password must be at least 8 characters.", "error")
            else:
                db.execute("UPDATE users SET password_hash=%s WHERE id=%s",
                           (generate_password_hash(new), uid))
                db.commit()
                flash("Password changed.", "success")
        elif action == "sample_add":
            today = date.today()
            for days, cat, desc, cents, crop, pay in SAMPLE:
                db.execute("""INSERT INTO expenses(user_id,category,description,amount_cents,
                              expense_date,crop,payment_method) VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                           (uid, cat, "[SAMPLE] " + desc, cents,
                            (today - timedelta(days=days)).isoformat(), crop, pay))
            db.commit()
            flash("Sample expenses added. Each one starts with [SAMPLE].", "success")
        elif action == "sample_remove":
            db.execute("DELETE FROM expenses WHERE user_id=%s AND description LIKE '[SAMPLE]%%'", (uid,))
            db.commit()
            flash("Sample expenses removed. Your real records were not touched.", "success")
        return redirect(url_for("settings"))
    user = db.execute("SELECT name,email FROM users WHERE id=%s", (uid,)).fetchone()
    n = db.execute("SELECT COUNT(*) AS n FROM expenses WHERE user_id=%s AND description LIKE '[SAMPLE]%%'",
                   (uid,)).fetchone()["n"]
    return render_template("settings.html", user=user, sample_count=n)


# ---------- sample data (optional, always labelled) ----------
SAMPLE = [  # (days ago, category, description, cents, crop, payment)
    (1, "Seeds", "Paddy seed 50kg", 18500, "Paddy", "Cash"),
    (2, "Fertilizer", "NPK fertilizer 10 bags", 42000, "Paddy", "Bank Transfer"),
    (3, "Labour", "Weeding workers", 30000, "Chilli", "Cash"),
    (4, "Fuel", "Diesel for tractor", 12000, "Paddy", "Card"),
    (6, "Pesticide", "Insecticide spray", 15500, "Chilli", "E-wallet"),
    (8, "Transportation", "Lorry to market", 9000, "Corn", "Cash"),
    (11, "Equipment", "Sprayer repair", 21000, "Corn", "Bank Transfer"),
    (13, "Seeds", "Corn seed", 8000, "Corn", "Cash"),
]


# ---------- dashboard and budget helpers ----------
def get_budget(uid):
    r = get_db().execute("SELECT budget_cents, revenue_cents FROM settings WHERE user_id=%s",
                         (uid,)).fetchone()
    return (r["budget_cents"], r["revenue_cents"]) if r else (0, 0)

def budget_status(total, budget):
    """Budget used (%) and a warning level. A zero budget is handled safely."""
    pct = round(total / budget * 100, 1) if budget > 0 else None
    level = "none" if pct is None else "over" if pct > 100 else "warn" if pct >= 80 else "ok"
    return pct, level

def all_total(uid):
    return get_db().execute("SELECT CAST(COALESCE(SUM(amount_cents),0) AS BIGINT) AS total FROM expenses WHERE user_id=%s",
                            (uid,)).fetchone()["total"]

@app.route("/dashboard")
@login_required
def dashboard():
    db, uid = get_db(), session["user_id"]
    budget, revenue = get_budget(uid)
    total = all_total(uid)
    pct, level = budget_status(total, budget)
    cats = db.execute("""SELECT category, CAST(SUM(amount_cents) AS BIGINT) AS t FROM expenses WHERE user_id=%s
                         GROUP BY category ORDER BY t DESC""", (uid,)).fetchall()
    days = db.execute("""SELECT expense_date AS d, CAST(SUM(amount_cents) AS BIGINT) AS t FROM expenses WHERE user_id=%s
                         GROUP BY expense_date ORDER BY d DESC LIMIT 14""", (uid,)).fetchall()[::-1]
    recent = db.execute("SELECT * FROM expenses WHERE user_id=%s ORDER BY expense_date DESC, id DESC LIMIT 5",
                        (uid,)).fetchall()
    # Line chart points (SVG coordinates) for the daily spending trend
    W, H, PX, PT, PB = 400, 190, 30, 15, 25
    maxday = max([d["t"] for d in days], default=1)
    points = []
    for i, d in enumerate(days):
        x = W / 2 if len(days) == 1 else PX + i * (W - 2 * PX) / (len(days) - 1)
        y = PT + (H - PT - PB) * (1 - d["t"] / maxday)
        points.append({"x": round(x, 1), "y": round(y, 1), "d": d["d"], "t": d["t"]})
    line = " ".join(f'{p["x"]},{p["y"]}' for p in points)
    count = db.execute("SELECT COUNT(*) AS n FROM expenses WHERE user_id=%s", (uid,)).fetchone()["n"]
    return render_template("dashboard.html", budget=budget, revenue=revenue, total=total,
                           remaining=budget - total, pct=pct, level=level, cats=cats,
                           points=points, line=line, maxday=maxday, count=count,
                           remaining_pct=round(100 - pct, 1) if pct is not None else None,
                           recent=recent)

@app.route("/reports", methods=["GET", "POST"])
@login_required
def reports():
    db, uid = get_db(), session["user_id"]
    if request.method == "POST":
        b = money_to_cents(request.form.get("budget", ""))
        r = money_to_cents(request.form.get("revenue", ""))
        if b is None or r is None:
            flash("Budget and revenue must be numbers that are 0 or more.", "error")
        else:
            db.execute("""INSERT INTO settings(user_id,budget_cents,revenue_cents) VALUES(%s,%s,%s)
                          ON CONFLICT(user_id) DO UPDATE SET
                          budget_cents=excluded.budget_cents, revenue_cents=excluded.revenue_cents""",
                       (uid, b, r))
            db.commit()
            flash("Budget and revenue saved.", "success")
        return redirect(url_for("reports"))
    f = {k: request.args.get(k, "").strip() for k in ("start", "end", "crop")}
    sql, params = "FROM expenses WHERE user_id=%s", [uid]
    if f["start"]: sql += " AND expense_date >= %s"; params.append(f["start"])
    if f["end"]:   sql += " AND expense_date <= %s"; params.append(f["end"])
    if f["crop"]:  sql += " AND crop ILIKE %s";       params.append(f"%{f['crop']}%")
    rows = db.execute("SELECT category, COUNT(*) AS n, CAST(SUM(amount_cents) AS BIGINT) AS t " + sql +
                      " GROUP BY category ORDER BY t DESC", params).fetchall()
    budget, revenue = get_budget(uid)
    pct, level = budget_status(all_total(uid), budget)
    return render_template("reports.html", rows=rows, f=f, budget=budget, revenue=revenue,
                           budget_text=f"{budget / 100:.2f}", revenue_text=f"{revenue / 100:.2f}",
                           pct=pct, level=level, all_total=all_total(uid),
                           count=sum(r["n"] for r in rows), total=sum(r["t"] for r in rows),
                           today=date.today().isoformat())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "initdb":
        init_db()
        print("Database tables are ready.")
    else:
        app.run(debug=not PRODUCTION)
