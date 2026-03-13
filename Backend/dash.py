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


@app.route('/')
def home():
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():

    # TEMPORARY testing (remove after login system)
    if 'user_id' not in session:
        session['user_id'] = 9

    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT user.fullname, wallet.wallet_id, wallet.balance
    FROM user
    JOIN wallet ON user.id = wallet.user_id
    WHERE user.id = %s
    """

    cursor.execute(query, (user_id,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    if not user:
        user = {
            "fullname": "Unknown",
            "wallet_id": "Not Available",
            "balance": 0
        }

    return render_template("dash2.html", user=user)

@app.route('/profile')
def profile():

    if 'user_id' not in session:
        return redirect(url_for('dashboard'))

    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT user.fullname, user.email, wallet.wallet_id, wallet.balance
    FROM user
    JOIN wallet ON user.id = wallet.user_id
    WHERE user.id = %s
    """

    cursor.execute(query, (user_id,))
    user = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template("profile.html", user=user)

from flask import request, jsonify

@app.route("/update_profile", methods=["POST"])
def update_profile():

    if 'user_id' not in session:
        user_id = 9   # TEMPORARY testing (remove after login system)

    user_id = session['user_id']

    data = request.get_json()

    fullname = data['fullname']
    email = data['email']

    conn = get_db_connection()
    cursor = conn.cursor()

    query = "UPDATE user SET fullname=%s, email=%s WHERE id=%s"

    cursor.execute(query,(fullname,email,user_id))

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message":"Profile Updated Successfully"})

if __name__ == "__main__":
    app.run(debug=True)