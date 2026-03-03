from flask import Flask, request, render_template, redirect, url_for, flash
import mysql.connector
from werkzeug.security import generate_password_hash

app = Flask(
    __name__,
    template_folder="../Frontend/landing",
    static_folder="../Frontend"
)

app.secret_key = "supersecretkey"   # Required for flash messages


# ---------------- DATABASE CONNECTION ----------------
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="swm"
)

cursor = db.cursor()


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

    # Check password match
    if password != confirm_password:
        flash("Passwords do not match!", "error")
        return redirect(url_for('signup'))

    hashed_password = generate_password_hash(password)

    try:
        cursor.execute(
            "INSERT INTO user (fullname, email, password) VALUES (%s, %s, %s)",
            (fullname, email, hashed_password)
        )
        db.commit()

        flash("Registration Successful! Please login.", "success")
        return redirect(url_for('login'))

    except mysql.connector.Error:
        flash("Email already exists!", "error")
        return redirect(url_for('signup'))


# ---------------- LOGIN PAGE ----------------
@app.route('/login')
def login():
    return render_template("login.html")


# ---------------- RUN SERVER ----------------
if __name__ == '__main__':
    app.run(debug=True)