from flask import Flask, request, render_template
import mysql.connector
from werkzeug.security import generate_password_hash

app = Flask(
    __name__,
    template_folder="../Frontend/landing",
    static_folder="../Frontend"
)

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="swm"
)

cursor = db.cursor()

@app.route('/')
def signup():
    return render_template('signup.html')

@app.route('/register', methods=['POST'])
def register():
    fullname = request.form['name']
    email = request.form['email']
    password = request.form['password']
    confirm_password = request.form['confirm']

    if password != confirm_password:
        return "Passwords do not match!"

    hashed_password = generate_password_hash(password)

    try:
        cursor.execute(
    "INSERT INTO `user` (fullname, email, password) VALUES (%s, %s, %s)",
    (fullname, email, hashed_password)
)
        db.commit()
        return "Registration Successful!"
    except mysql.connector.Error:
        return "Email already exists!"

if __name__ == '__main__':
    app.run(debug=True)