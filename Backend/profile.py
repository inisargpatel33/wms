from flask import Flask, jsonify, render_template, url_for, redirect, session, request
import mysql.connector

app = Flask(
    __name__,
    template_folder="../Frontend/landing",
    static_folder="../Frontend"
)

app.secret_key = "secretkey"

# Database connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="swm"
)

@app.route("/")
def home():
    return redirect(url_for("profile"))


@app.route("/profile")
def profile():

    # TEMP login for testing
    session['user_id'] = 9

    userid = session['user_id']

    cursor = db.cursor(dictionary=True)

    query = """
    SELECT user.fullname, user.email, wallet.wallet_id
    FROM user
    JOIN wallet ON user.id = wallet.user_id
    WHERE user.id = %s
    """

    cursor.execute(query, (userid,))
    user = cursor.fetchone()

    cursor.close()

    return render_template("profile.html", user=user)


@app.route("/update_profile", methods=["POST"])
def update_profile():

    if 'user_id' not in session:
        user_id=9

    user_id = session['user_id']

    data = request.get_json()

    fullname = data['fullname']
    email = data['email']

    cursor = db.cursor()

    query = "UPDATE user SET fullname=%s, email=%s WHERE id=%s"

    cursor.execute(query, (fullname, email, user_id))

    db.commit()

    cursor.close()

    return jsonify({"message": "Profile Updated Successfully"})


if __name__ == "__main__":
    app.run(debug=True)