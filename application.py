import os

from flask import Flask, session, render_template, request,jsonify, url_for, redirect
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
import requests
import sys

app = Flask(__name__)

if __name__ == '__main__':
    app.run()
    
# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

app.config['JSON_SORT_KEYS'] = False

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/login")
def login():
    return render_template("login.html")
    
@app.route("/register")
def register():
    session.clear()
    return render_template("register.html")
     
@app.route("/success", methods=["POST"])
def success():
    session["username"]= request.form.get("username")
    session["password"] = request.form.get("password")
    first_name= request.form.get("first")
    last_name=request.form.get("last")
    email=request.form.get("email")
    
    if db.execute("SELECT username FROM users WHERE username = :username", {"username": session["username"]}).rowcount != 0:
        return render_template("register.html",i=1)
    
    db.execute("INSERT INTO users (username, password, first_name, last_name, email) VALUES (:username, :password,:first_name, :last_name, :email)",
            {"username": session["username"], "password": session["password"], "first_name": first_name, "last_name": last_name, "email": email})
    db.commit()
    return render_template("register.html",i=2)
    
@app.route("/", methods=["POST", "GET"])
def home():
    if request.method=="POST":
        session["username"]= request.form.get("username")
        session["password"] = request.form.get("password")
        
        if db.execute("SELECT * FROM users WHERE username = :username AND password = :password", {"username": session["username"], "password": session["password"]}).rowcount == 0:
            return render_template("login.html",i=1)
        
    if session.get("username") is None:
        return redirect(url_for('login'))
            
    name = db.execute("SELECT first_name,last_name, username FROM users WHERE username = :username AND password = :password", {"username": session["username"], "password": session["password"]}).fetchone()
    db.commit()
    return render_template("home.html", name = name)
   
@app.route("/logout",methods=["POST","GET"])
def logout():
    session.clear()
    return render_template("login.html",i=2)

@app.route("/search", methods=["POST"])
def search():
    search="%"+request.form.get("search")+"%"
    search=string.capwords(search)
    
    book= db.execute("SELECT * FROM books WHERE isbn LIKE :search OR author LIKE :search OR book_title LIKE :search", {"search": search}).fetchall()
    i=db.execute("SELECT * FROM books WHERE isbn LIKE :search OR author LIKE :search OR book_title LIKE :search", {"search": search}).rowcount
    
    name = db.execute("SELECT first_name,last_name, username FROM users WHERE username = :username AND password = :password", {"username": session["username"], "password": session["password"]}).fetchone()
    
    if db.execute("SELECT * FROM books WHERE isbn LIKE :search OR author LIKE :search OR book_title LIKE :search", {"search": search}).rowcount == 0:
        return render_template("home.html", i=1, name=name)
        
    db.commit()
    return render_template("search.html",books=book, result=request.form.get("search"),i=i,name=name)
    
@app.route("/history")
def history():
    review= db.execute("SELECT * FROM books JOIN reviews ON books.isbn= reviews.isbn WHERE reviews.username= :username", {"username": session["username"]}).fetchall()
    
    i=db.execute("SELECT * FROM reviews WHERE username LIKE :username", {"username": session["username"]}).rowcount
    
    name = db.execute("SELECT first_name,last_name, username FROM users WHERE username = :username AND password = :password", {"username": session["username"], "password": session["password"]}).fetchone()
    
    db.commit()
    return render_template("history.html",reviews= review ,i=i,name=name)
    
@app.route("/book/<string:isbn>")
def book(isbn):
    res=requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "lZcggDlBX1KLb21GtzXeKw", "isbns": isbn})
    if res.status_code != 200:
        raise Exception("ERROR: API request unsuccessful.")
    
    grapi=res.json()
    avg=grapi["books"][0]["average_rating"]
    total=grapi["books"][0]["work_ratings_count"]
    
    row=db.execute("SELECT COUNT(*) FROM reviews JOIN users ON users.username= reviews.username WHERE isbn= :isbn", {"isbn": isbn}).rowcount
    
    book= db.execute("SELECT * FROM books WHERE isbn= :isbn", {"isbn": isbn}).fetchone()
    review = db.execute("SELECT * FROM reviews JOIN users ON users.username= reviews.username WHERE isbn= :isbn", {"isbn": isbn}).fetchall()
    
    name = db.execute("SELECT first_name,last_name, username FROM users WHERE username = :username AND password = :password", {"username": session["username"], "password": session["password"]}).fetchone()
    
    db.commit()
    return render_template("book.html", book=book, review=review, avg=avg, total=total, title=book.book_title, name=name,row=row)
    
@app.route("/reviewstatus/<string:isbn>", methods=["POST"])
def reviewstatus(isbn):
    rating=request.form.get("inlineRadioOptions")
    review=request.form.get("review")
    
    name = db.execute("SELECT first_name,last_name, username FROM users WHERE username = :username AND password = :password", {"username": session["username"], "password": session["password"]}).fetchone()
    
    if db.execute("SELECT * FROM reviews WHERE username LIKE :username AND isbn LIKE :isbn", {"username": session["username"], "isbn": isbn}).rowcount != 0:
        return render_template("book.html", i=1, name=name, title="Error", isbn=isbn)
        
    db.execute("INSERT INTO reviews (isbn, username, review, rating) VALUES (:isbn, :username, :review, :rating)",
    {"isbn": isbn, "username": session["username"], "review": review, "rating": rating})
    db.commit()
    return render_template("book.html",i=2, name=name,title= "Success", isbn=isbn)

@app.route("/api/<string:isbn>")
def book_api(isbn):
    book= db.execute("SELECT * FROM books WHERE isbn= :isbn", {"isbn": isbn}).fetchone()
    if book is None:
        return jsonify({"Error": "No book as such available"}), 404
        
    res=requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "lZcggDlBX1KLb21GtzXeKw", "isbns": isbn})
    grapi=res.json()
    
    avg=grapi["books"][0]["average_rating"]
    total=grapi["books"][0]["work_ratings_count"]
    
    return jsonify({
        "title": book.book_title,
        "author": book.author,
        "year": book.year,
        "isbn": book.isbn,
        "review_count": avg ,
        "average_score": total
    })
