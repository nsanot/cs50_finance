from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from flask_session import Session
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
    global_balance = balance

    positions = db.execute("SELECT stock_symbol, stock_count FROM holdings WHERE user_id = ?", session["user_id"])

    for position in positions:
        response = lookup(position["stock_symbol"])

        if not response.get("success"):
            return apology(response.get("message"))

        global_balance += response["stock_info"]["price"] * position["stock_count"]
        position["stock_price"] = usd(response["stock_info"]["price"])
        position["position_price"] = usd(response["stock_info"]["price"] * position["stock_count"])

    table_headers = ("Symbol", "Count", "Price", "Total")

    return render_template(
        "index.html",
        balance=usd(balance),
        global_balance=usd(global_balance),
        table_headers=table_headers,
        positions=positions,
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # Сохраняю содержимое формы
        form = {
            "symbol": request.form.get("symbol"),
            "shares": request.form.get("shares", type=int),
        }

        # Проверяю, что форма не пустая
        for field, value in form.items():
            if not value:
                return apology(f"The '{field}' field cannot be empty.")

        # Запрашиваю информацию об акции
        response = lookup(form["symbol"])
        if not response.get("success"):
            return apology(response.get("message"))

        # Определяю переменные для читаемости
        user_id = session["user_id"]
        stock_symbol = response["stock_info"]["symbol"].upper()
        stock_price = response["stock_info"]["price"]
        stock_count = form["shares"]

        # Ищу пользователя по ид с сессии, сохраняю его текущий баланс
        user_cash = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]["cash"]

        # Проверяю хватает ли баланса для покупки
        balance_change = stock_price * stock_count
        if user_cash < balance_change:
            return apology("Insufficient funds.")

        # Сохраняю транзакцию
        db.execute(
            "INSERT INTO transactions (user_id, type, stock_symbol, stock_price, stock_count, balance_change, datetime) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            user_id,
            "BUY",
            stock_symbol,
            stock_price,
            stock_count,
            -balance_change
        )

        # Списываю баланс
        db.execute("UPDATE users SET cash = (cash - ?) WHERE id = ?", balance_change, user_id)

        # Обновляю портфель
        db.execute(
            "INSERT INTO holdings (user_id, stock_symbol, stock_count) VALUES (?, ?, ?)" \
            "ON CONFLICT (user_id, stock_symbol) DO UPDATE SET stock_count = stock_count + excluded.stock_count",
            user_id,
            stock_symbol,
            stock_count
        )

        # Возвращаю пользователя на главную страницу
        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    return apology("TODO")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password", '')
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("The 'symbol' field cannot be empty.")

        response = lookup(symbol)
        if not response.get("success"):
            return apology(response.get("message"))

        return render_template("quoted.html", stock_info=response["stock_info"])

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        # Сохраняю информацию с формы
        form = {
            "username": request.form.get("username", ""),
            "password": request.form.get("password", ""),
            "retype_password": request.form.get("confirmation", "")
        }

        # Проверяю, что поля формы не пустые
        for field, value in form.items():
            if not value:
                return apology(f"The '{field}' field cannot be empty")

        # Проверяю, что пароли совпадают
        if form["password"] != form["retype_password"]:
            return apology("Passwords do not match")

        lower_username = form["username"].lower()

        # Добавляю пользователя в базу
        try:
            db.execute(
                "INSERT INTO users (username, hash) VALUES (?, ?)",
                form["username"],
                generate_password_hash(form["password"]),
            )
        except ValueError:
            return apology(f"User '{form["username"]}' already registered.")

        # Нахожу в базе ид только что созданного пользователя, привязываю ид к сессии
        session["user_id"] = db.execute("SELECT id FROM users WHERE LOWER(username) = ?", lower_username)[0]["id"]

        # Перенаправляю на домашнюю страницу
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    return apology("TODO")
