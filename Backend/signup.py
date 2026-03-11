from flask import Flask, request, render_template, redirect, url_for, flash
import mysql.connector
from werkzeug.security import generate_password_hash
import random

app = Flask(
    __name__,
    template_folder="../Frontend/landing",
    static_folder="../Frontend"
)

app.secret_key = "supersecretkey"


# ---------------- DATABASE CONNECTION ----------------
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="swm"
)

cursor = db.cursor()


# ---------------- GENERATE UNIQUE 10 DIGIT WALLET ID ----------------
def generate_wallet_id():
    while True:
        wallet_id = random.randint(1000000000, 9999999999)

        cursor.execute(
            "SELECT wallet_id FROM wallet WHERE wallet_id=%s",
            (wallet_id,)
        )

        if cursor.fetchone() is None:
            return wallet_id


# ---------------- SIGNUP PAGE ----------------
@app.route('/')
def signup():
    return render_template('signup.html')


# ---------------- REGISTER LOGIC ----------------
@app.route('/register', methods=['POST'])
def register():

    fullname = request.form['name']
    email = request.form['email']
    password = request.form['password']
    confirm_password = request.form['confirm']

    # Password validation
    if password != confirm_password:
        flash("Passwords do not match!", "error")
        return redirect(url_for('signup'))

    hashed_password = generate_password_hash(password)

    try:
        # Insert user
        cursor.execute(
            "INSERT INTO user (fullname, email, password) VALUES (%s, %s, %s)",
            (fullname, email, hashed_password)
        )
        db.commit()

        # Get new user id
        user_id = cursor.lastrowid

        # Generate wallet id
        wallet_id = generate_wallet_id()

        # Create wallet linked with user
        cursor.execute(
            "INSERT INTO wallet (wallet_id, user_id, balance) VALUES (%s, %s, %s)",
            (wallet_id, user_id, 0)
        )
        db.commit()

        flash("Registration Successful! Wallet Created.", "success")
        return redirect(url_for('login'))

    except mysql.connector.Error as err:
        print("Database Error:", err)
        flash("Registration failed!", "error")
        return redirect(url_for('signup'))


# ---------------- LOGIN PAGE ----------------
@app.route('/login')
def login():
    return render_template("login.html")


# ---------------- RUN SERVER ----------------
if __name__ == '__main__':
    app.run(debug=True)