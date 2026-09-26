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
    # Сохраняю баланс пользователя
    balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
    global_balance = balance

    # Смотрю позиции пользователя
    position_table = db.execute("SELECT stock_symbol, stock_count FROM holdings WHERE user_id = ?", session["user_id"])

    # Если есть позиции, формирую таблицу с информацией
    for position in position_table:
        response = lookup(position["stock_symbol"])

        if not response.get("success"):
            return apology(response.get("message"))

        global_balance += response["stock_info"]["price"] * position["stock_count"]
        position["stock_price"] = usd(response["stock_info"]["price"])
        position["total_price"] = usd(response["stock_info"]["price"] * position["stock_count"])

    return render_template(
        "index.html",
        balance=usd(balance),
        global_balance=usd(global_balance),
        position_table=position_table,
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
    transaction_table = db.execute("SELECT type, stock_symbol, stock_price, stock_count, datetime FROM transactions WHERE user_id = ?", session["user_id"])

    if transaction_table:
        for transaction in transaction_table:
            transaction["stock_price"] = usd(transaction["stock_price"])

    return render_template("history.html", transaction_table=transaction_table)


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
        if not request.form.get("symbol"):
            return apology("The 'symbol' field cannot be empty.")

        response = lookup(symbol)
        if not response.get("success"):
            return apology(response.get("message"))

        response["stock_info"]["price"] = usd(response["stock_info"]["price"])

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

        # Проверяю, что username свободен
        lower_username = form["username"].lower()
        already_exists = db.execute("SELECT id FROM users WHERE LOWER(username) = ?", lower_username)
        if already_exists:
            return apology(f"User '{form["username"]}' already registered.")

        # Создаю пользователя
        db.execute(
            "INSERT INTO users (username, hash) VALUES (?, ?)",
            form["username"],
            generate_password_hash(form["password"]),
        )

        # Нахожу в базе ид только что созданного пользователя, привязываю его ид к его сессии
        session["user_id"] = db.execute("SELECT id FROM users WHERE LOWER(username) = ?", lower_username)[0]["id"]

        # Перенаправляю на домашнюю страницу
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    position_table = db.execute("SELECT stock_symbol, stock_count FROM holdings WHERE user_id = ?", session["user_id"])
    portfolio = {pos["stock_symbol"]: pos["stock_count"] for pos in position_table}

    if request.method == "POST":
        # Получаю значения формы
        stock_symbol = request.form.get("symbol", "").upper()
        sell_amount = request.form.get("count", type=int)

        # Проверяю, что пользователь холдит акцию, которую хочет продать
        if stock_symbol not in portfolio:
            return apology(f"You do not own shares with the symbol '{stock_symbol}'")

        hold_amount = portfolio[stock_symbol]

        # Обрабатываю кол-во к продаже
        if not sell_amount or sell_amount < 1:
            return apology("Fill in the 'count' field with a positive integer greater than 0")
        elif sell_amount > hold_amount:
            return apology(f"You cannot sell more than you have. You have: {hold_amount}")

        # Запрашиваю инфу по акции
        response = lookup(stock_symbol)
        if not response.get("success"):
            return apology(response.get("message"))

        user_id = session["user_id"]
        stock_price = response["stock_info"]["price"]
        balance_change = stock_price * sell_amount

        # Обрабатываю продажу
        db.execute(
            "INSERT INTO transactions (user_id, type, stock_symbol, stock_price, stock_count, balance_change, datetime) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
            user_id,
            "SELL",
            stock_symbol,
            stock_price,
            sell_amount,
            +balance_change
        )

        db.execute("UPDATE users SET cash = (cash + ?) WHERE id = ?", balance_change, user_id)

        if sell_amount == hold_amount:
            db.execute("DELETE FROM holdings WHERE stock_symbol = ? AND user_id = ?", stock_symbol, user_id)
        else:
            db.execute(
                "UPDATE holdings SET stock_count = (stock_count - ?) WHERE user_id = ? AND stock_symbol = ?",
                sell_amount,
                user_id,
                stock_symbol
            )

        # Возвращаю пользователя на главную странциу
        return redirect("/")

    else:
        return render_template("sell.html", own_symbols=portfolio.keys())
