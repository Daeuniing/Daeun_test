import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


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
    user_id = session["user_id"]
    transactions = db.execute("SELECT symbol, SUM(shares)AS shares, price FROM transactions WHERE user_id=? GROUP BY symbol", user_id)
    cash_db=db.execute("SELECT cash FROM users WHERE id=?", user_id)
    cash = cash_db[0]["cash"]

    return render_template("index.html", database=transactions, cash=cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        item=lookup(symbol)

        if not symbol:
            return apology ("please enter a symbol")
        elif not item:
            return apology("Invalid symbol")

        try:
            shares = int(request.form.get("shares"))
        except:
            return apology ("Shares are integer")

        if shares <= 0:
            return apology ("Shares should be bigger than zero")
        user_id = session["user_id"]
        cash = db.execute("SELECT cash FROM users WHERE id=?", user_id)[0]["cash"]

        item_name = item["name"]
        item_price = item["price"]
        total_price = item_price * shares

        if cash < total_price:
            return apology("You need more cash to buy")
        else:
            db.execute("UPDATE users SET cash=? WHERE id=?", cash - total_price, user_id)
            db.execute("INSERT INTO transactions(user_id, name, shares, price, type, symbol) VALUES (?,?,?,?,?,?)",
            user_id, item_name, shares, item_price, "buy", symbol)

        return redirect('/')
    else:
        render_template("buy.html")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]
    transactions= db.execute("SELECT * FROM transactions WHERE user_id = ?", id=user_id)
    return render_template("history.html", transactions = transactions)

@app.route("/add_cash", methods=["GET", "POST"])
@login_required
def cash():
    """Add cash area"""
    if request.method == "GET":
        return render_template("add.html")
    else:
        new_cash = int(request.form.get("new_cash"))
        if not new_cash:
            return apology("You need to fulfill")

        user_id = session["user_id"]
        user_cash_db = db.execute("SELECT cash FROM users WHERE id =:id", id=user_id)
        user_cash = user_cash_db[0]["cash"]

        uptd_cash = user_cash + new_cash

        #update
        db.execute("UPDATE users SET cash=? WHERE id=?", uptd_cash, user_id)
        return redirect("/")



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password")

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
    if request.method == "GET":
        return render_template("quote.html")

    else:
        symbol = request.form.get("symbol")

        if not symbol:
            return apology("We need symbol")

        stock = lookup(symbol.upper())

        if stock == None:
            return apology("Symbol doesn't exist")
        return render_template("quoted.html", name=stock["name"],price=stock["price"],symbol=stock["symbol"])


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        login = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not login or not password or not confirmation:
            return apology("You must fill all the fields!")

        if password != confirmation:
            return apology("Passwords don't match")

        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        if len(rows) != 0:
            return apology("This username is taken")

        db.execute("INSERT INTO users (username, hash, cash) VALUES(?, ?, 10000)", login, generate_password_hash(password))

        return redirect("/")
    return render_template("register.html")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        user_id = session["user_id"]
        symbol= request.form.get("symbol")
        shares = int(request.form.get("shares"))

        if shares <= 0:
            return apology ("shares should be integer")

        item_price = lookup(symbol)["price"]
        item_name = lookup(symbol)["name"]

        shares_owned = db.execute("SELECT shares FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol", user_id, symbol)[0]["shares"]

        if shares_owned < shares:
            return apology ("You don't have enough shares")

        current_cash = db.execute("SELECT cash FROM users WHERE id=?", user_id)[0]["cash"]
        db.execute("UPDATE users SET cash = ? WHERE id = ?", current_cash + price, user_id)
        db.execute("INSERT INTO transactions(user_id, name, shares, price, type, symbol) VALUES (?,?,?,?,?,?)",
            user_id, item_name, -shares, item_price, "sell", symbol)

        return redirect("/")
    else:
        user_id = session["user_id"]
        symbols = db.execute("SELECT symbol FROM transaction WHERE user_id = ? GROUP BY symbol", user_id)
        return render_template("sell.html", symbols=symbols)