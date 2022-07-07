import os
import datetime

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from decimal import *

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    # set appropriate variables
    currentuser = session["user_id"]
    stocks = db.execute(
        "SELECT symbol, name, SUM(shares) AS totalshares FROM transactions WHERE user = :currentuser GROUP BY symbol HAVING totalshares > 0", currentuser=currentuser)
    user = db.execute("SELECT cash FROM users WHERE id = :currentuser", currentuser=currentuser)
    cash = user[0]["cash"]
    stockvalue = 0
    # dict to store data on stocks
    stockdata = {}
    for stock in stocks:
        stockvalue += (stock["totalshares"] * lookup(stock["symbol"])["price"])
        stockdata[stock["symbol"]] = lookup(stock["symbol"])
    total = stockvalue + cash
    # return index/portfolio page
    return render_template("index.html", stockdata=stockdata, stocks=stocks, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    # store data if post method
    if request.method == "POST":
        # ensure symbol and shares entered
        if not request.form.get("symbol"):
            return apology("must provide symbol")
        elif not request.form.get("shares"):
            return apology("must provide shares")
        # ensure symbol exists
        stocks = lookup(request.form.get("symbol"))
        if not stocks:
            return apology("enter valid symbol")
        # ensure shares is an integer
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("number of shares must be an integer")
        # ensure shares is positive
        if not shares > 0:
            return apology("number of shares must be positive")

        # check if current user has enough cash
        currentuser = session["user_id"]
        user = db.execute("SELECT cash FROM users WHERE id = :currentuser", currentuser=currentuser)
        cash = user[0]["cash"]
        price = stocks["price"]
        enough = cash >= (shares * price)
        # return apology if can't afford
        if not enough:
            return apology("can't afford")
        # if enough money
        else:
            # record purchase data in purchases table
            symbol = stocks["symbol"]
            name = stocks["name"]
            transacted = datetime.datetime.now()
            db.execute("INSERT INTO transactions (symbol, shares, price, name, transacted, user) VALUES (:symbol, :shares, :price, :name, :transacted, :user)",
                       symbol=symbol, shares=shares, price=price, name=name, transacted=transacted, user=currentuser)
            # subtract from current cash in users table
            cash -= (shares * price)
            db.execute("UPDATE users SET cash = :cash WHERE id = :currentuser", cash=cash, currentuser=currentuser)
            # success, redirect
            flash("Bought!")
            return redirect("/")
    # return website if get method
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    # get data from transactions table
    currentuser = session["user_id"]
    transactions = db.execute(
        "SELECT symbol, shares, price, transacted FROM transactions WHERE user = :currentuser", currentuser=currentuser)
    # return site
    return render_template("history.html", transactions=transactions)


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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
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
    # post method to retrieve info from user's symbol input
    if request.method == "POST":
        symbol = request.form.get("symbol")
        # if invalid symbol
        if not lookup(symbol):
            return apology("enter valid symbol")
        # valid symbol
        else:
            # store stock name, price, symbol and pass into quoted.html
            stocks = lookup(symbol)
            name = stocks["name"]
            price = stocks["price"]
            stocksymbol = stocks["symbol"]
            return render_template("quoted.html", name=name, price=price, stocksymbol=stocksymbol)
    # get method
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)
        # ensure username does not exist
        elif len(db.execute("SELECT * FROM users WHERE username = :username",
                            username=request.form.get("username"))) != 0:
            return apology("username already exists", 403)
        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        # ensure password/confirmation match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords must match", 403)

        # insert username, hashed password into db
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=request.form.get("username"),
                   hash=generate_password_hash(request.form.get("password")))

        # success
        session["user_id"] = request.form.get("username")

        # Redirect user to home page
        return redirect("/")

    # reached via GET (as via clicking a link or redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    # store data if post method
    if request.method == "POST":
        # ensure symbol and shares entered
        if not request.form.get("symbol"):
            return apology("must provide symbol")
        elif not request.form.get("shares"):
            return apology("must provide shares")
        # ensure shares is an integer
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("number of shares must be an integer")
        # ensure shares is positive
        if not shares > 0:
            return apology("number of shares must be positive")

        # check if current user has enough shares/doesn't own any
        currentuser = session["user_id"]
        stocks = db.execute("SELECT name, symbol, SUM(shares) AS totalshares FROM transactions WHERE user = :currentuser AND symbol = :symbol GROUP BY symbol HAVING totalshares > 0",
                            currentuser=currentuser, symbol=request.form.get("symbol"))
        if not stocks:
            return apology("no shares owned")
        currentshares = stocks[0]["totalshares"]
        if shares > currentshares:
            return apology("too many shares")

        # update transactions table
        symbol = stocks[0]["symbol"]
        name = stocks[0]["name"]
        price = lookup(stocks[0]["symbol"])["price"]
        transacted = datetime.datetime.now()
        db.execute("INSERT INTO transactions (symbol, shares, price, name, transacted, user) VALUES (:symbol, :shares, :price, :name, :transacted, :user)",
                   symbol=symbol, shares=-(shares), price=price, name=name, transacted=transacted, user=currentuser)
        # subtract from current cash in users table
        user = db.execute("SELECT cash FROM users WHERE id = :currentuser", currentuser=currentuser)
        cash = user[0]["cash"]
        cash += (shares * price)
        db.execute("UPDATE users SET cash = :cash WHERE id = :currentuser", cash=cash, currentuser=currentuser)

        # success, redirect
        flash("Sold!")
        return redirect("/")

    # return website if get method
    else:
        # list of symbols owned
        currentuser = session["user_id"]
        stocks = db.execute(
            "SELECT symbol FROM transactions WHERE user = :currentuser GROUP BY symbol HAVING SUM(shares) > 0", currentuser=currentuser)
        return render_template("sell.html", stocks=stocks)

# personal touch - allows user to deposit more cash into account
@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    # when reached via POST
    if request.method == "POST":

        # check for value entered
        if not request.form.get("amount"):
            return apology("must enter deposit amount")

        # check for numeric value entered
        try:
            getcontext().prec = 2
            amount = Decimal(request.form.get("amount"))
        except:
            return apology("invalid deposit")
        # ensure deposit is positive
        if not amount > 0:
            return apology("deposit amount must be positive")

        # update user's cash
        currentuser = session["user_id"]
        user = db.execute("SELECT cash FROM users WHERE id = :currentuser", currentuser=currentuser)
        cash = user[0]["cash"]
        deposit = float(amount)
        cash += deposit
        db.execute("UPDATE users SET cash = :cash WHERE id = :currentuser", cash=cash, currentuser=currentuser)

        #success, redirect
        flash("Deposited!")
        return redirect("/")

    # when reached via GET
    else:
        return render_template("deposit.html")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
