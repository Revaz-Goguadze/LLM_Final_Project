from flask import Flask, request

app = Flask(__name__)


@app.route("/search")
def search():
    query = request.args.get("q", "")
    # BUG: XSS vulnerability - user input directly in HTML
    return f"<h1>Search results for: {query}</h1>"


@app.route("/profile")
def profile():
    name = request.args.get("name", "")
    # BUG: XSS - reflected user input
    return f"<div class='profile'>Welcome, {name}!</div>"
