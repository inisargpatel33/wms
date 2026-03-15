from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
import mysql.connector

app = Flask(
    __name__,
    template_folder="../Frontend/landing",
    static_folder="../Frontend"
)
app.secret_key = "your_secret_key"

# Database configuration
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "swm"
}

def get_db_connection():
    """Helper function to get a fresh DB connection and cursor."""
    conn = mysql.connector.connect(**db_config, autocommit=True)
    return conn, conn.cursor(dictionary=True)

# --- ROUTES ---

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        conn, cursor = get_db_connection()
        try:
            cursor.execute("SELECT * FROM user WHERE email=%s", (email,))
            user = cursor.fetchone()

            if user:
                # Password must be hashed in DB for this to work!
                if check_password_hash(user['password'], password):
                    session['user_id'] = user['id']
                    session['fullname'] = user['fullname']
                    return redirect(url_for('dashboard')) # Redirects to the dashboard FUNCTION
                else:
                    flash("Invalid Password!", "error")
            else:
                flash("Email not registered!", "error")
        finally:
            cursor.close()
            conn.close()

        

    return render_template("login.html")

@app.route('/dashboard')
def dashboard():
    # 1. Check if user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # 2. Render your dashboard template
    # Make sure dash.html is inside your ../Frontend/landing folder
    return render_template("dash2.html", name=session['fullname'])

@app.route('/signup')
def signup():
    # If you have a signup.html, use render_template
    return render_template("signup.html")

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)