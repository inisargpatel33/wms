from flask import Flask, render_template, session, redirect, url_for
import mysql.connector

app = Flask(
    __name__,
    template_folder="../Frontend/landing",
    static_folder="../Frontend"
)

app.secret_key = "your_secret_key"


def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="swm"
    )


@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    conn, cursor = get_db_connection()

    cursor.execute(
        "SELECT wallet_id, balance FROM wallet WHERE user_id=%s",
        (user_id,)
    )

    wallet = cursor.fetchone()

    cursor.close()
    conn.close()

    if wallet:
        wallet_id = wallet['wallet_id']
        balance = wallet['balance']
    else:
        wallet_id = "Not Available"
        balance = 0

    return render_template(
        "dash.html",
        name=session['fullname'],
        wallet_id=wallet_id,
        balance=balance
    )

if __name__ == "__main__":
    app.run(debug=True)