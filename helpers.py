import json
from functools import wraps

import requests
from flask import redirect, render_template, session


def apology(message, code=400):
    """Render message as an apology to user."""

    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''"),
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""
    symbol = symbol.upper()
    url = f"https://finance.cs50.io/quote?symbol={symbol}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

    except requests.exceptions.RequestException as err:
        response = getattr(err, "response", None)
        if (response is not None) and (400 <= response.status_code < 500):
            return {"success": False, "message": "Invalid symbol"}

        print(f'Ошибка requests: {err}')
        return {"success": False, "message": "Failed to connect to the server."}

    try:
        quote_data = response.json()

        if not quote_data["companyName"] or not quote_data["latestPrice"]:
            return {"success": False, "message": "The server returned an unexpected response."}

        return {
            "success": True,
            "stock_info": {
                "name": quote_data["companyName"],
                "price": quote_data["latestPrice"],
                "symbol": symbol,
            }
        }
    except (json.decoder.JSONDecodeError, KeyError) as err:
        print(f"Parsing error: {type(err).__name__}. Response text: {response.text}")
        return {"success": False, "message": "The server returned an unexpected response."}


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"
