from flask import Flask, jsonify, render_template,url_for, redirect, session,request
import mysql.connector

app = Flask(
    __name__,
    template_folder="../Frontend/landing",
    static_folder="../Frontend"
)

# Database connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="swm"
)

@app.route("/profile")
def profile():

    userid = 9   # testing user

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

# Optional homepage (avoids 404 error)
@app.route("/")
def home():
    return redirect(url_for('profile'))

@app.route("/update_profile", methods=["POST"])
def update_profile():

    data = request.get_json()

    fullname = data["fullname"]
    email = data["email"]

    userid = 9   # later you will use session

    cursor = db.cursor()

    query = "UPDATE user SET fullname=%s,email=%s WHERE id=%s"

    cursor.execute(query,(fullname,email,userid))

    db.commit()

    cursor.close()

    return jsonify({"message":"Profile Updated Successfully"})

if __name__ == "__main__":
    app.run(debug=True)