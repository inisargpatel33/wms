from flask import Flask, render_template, request, Response, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from email_service import send_swm_email, get_burn_rate_template, get_goal_completed_template
import mysql.connector
import csv
import random
import io
import math
from datetime import datetime, timedelta
import re

import razorpay
import os
from flask_mail import Mail, Message
import sys
import logging

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# UTF-8 fix for Windows console (must be before any print with special chars)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ---------------------------------------------------------------------------
# RAZORPAY CONFIG
# ---------------------------------------------------------------------------
RAZORPAY_KEY_ID     = "rzp_test_SRa3Cn60azMF5E"
RAZORPAY_KEY_SECRET = "dobJbw8U5fBTv5D6kRwWHk6E"
client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# ---------------------------------------------------------------------------
# FLASK APP SETUP
# ---------------------------------------------------------------------------
base_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(base_dir, '../Frontend/landing'),
    static_folder=os.path.join(base_dir, '../Frontend')
)
app.secret_key = "supersecretkey"

app.config['MAIL_SERVER']   = 'smtp.gmail.com'
app.config['MAIL_PORT']     = 587
app.config['MAIL_USE_TLS']  = True
app.config['MAIL_USERNAME'] = 'eventmanagementsys01@gmail.com'
app.config['MAIL_PASSWORD'] = 'nuazzwirnwjwydba'

mail = Mail(app)

# ---------------------------------------------------------------------------
# DATABASE CONFIG
# ---------------------------------------------------------------------------
db_config = {
    "host":     "localhost",
    "user":     "root",
    "password": "",
    "database": "swm"
}

def get_db_connection():
    conn = mysql.connector.connect(**db_config, autocommit=True)
    return conn, conn.cursor(dictionary=True)

def generate_wallet_id(cursor):
    while True:
        wallet_id = random.randint(1000000000, 9999999999)
        cursor.execute("SELECT wallet_id FROM wallet WHERE wallet_id=%s", (wallet_id,))
        if cursor.fetchone() is None:
            return wallet_id

# ---------------------------------------------------------------------------
# HELPER: safe email sender — never crashes the calling route
# ---------------------------------------------------------------------------
def safe_send_email(to_email, subject, html_content):
    try:
        send_swm_email(to_email=to_email, subject=subject, html_content=html_content)
    except Exception as e:
        logger.warning("Email send failed (non-critical): %s", e)


# ==========================================
# LANDING PAGE
# ==========================================
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


# ==========================================
# GLOBAL BAN ENFORCER
# ==========================================
@app.before_request
def enforce_ban_hammer():
    if 'user_id' in session:
        if request.endpoint and request.endpoint not in ['static', 'login', 'logout']:
            conn, cursor = get_db_connection()
            try:
                cursor.execute("SELECT account_status FROM user WHERE id=%s", (session['user_id'],))
                current_user = cursor.fetchone()
                if current_user and current_user['account_status'] == 'suspended':
                    session.clear()
                    flash("Access Denied: Your account has been suspended by an Administrator.", "error")
                    return redirect(url_for('login'))
            except Exception as e:
                print("Ban Enforcer Error:", e)
            finally:
                if 'cursor' in locals():
                    cursor.close()
                    conn.close()


# ==========================================
# ADMIN DASHBOARD
# ==========================================
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn, cursor = get_db_connection()
    try:
        cursor.execute("SELECT role FROM user WHERE id=%s", (session['user_id'],))
        user_check = cursor.fetchone()

        if not user_check or user_check['role'] != 'admin':
            flash("Access Denied. You do not have administrator privileges.", "error")
            return redirect(url_for('dashboard'))

        cursor.execute("SELECT COUNT(*) as total_users FROM user")
        total_users = cursor.fetchone()['total_users']

        cursor.execute("SELECT SUM(balance) as t1 FROM wallet")
        main_total = float(cursor.fetchone()['t1'] or 0)

        cursor.execute("SELECT SUM(balance) as t2 FROM sub_wallet")
        sub_total = float(cursor.fetchone()['t2'] or 0)

        cursor.execute("SELECT SUM(current_balance) as t3 FROM savings_goals")
        goals_total = float(cursor.fetchone()['t3'] or 0)

        total_platform_assets = main_total + sub_total + goals_total

        cursor.execute("SELECT COUNT(*) as total_tx FROM transactions")
        total_transactions = cursor.fetchone()['total_tx']

        cursor.execute("""
            SELECT 
                u.id, u.fullname, u.email, u.role, u.account_status,
                (
                    COALESCE((SELECT SUM(balance) FROM wallet WHERE user_id = u.id), 0) +
                    COALESCE((SELECT SUM(balance) FROM sub_wallet WHERE user_id = u.id), 0)
                ) AS total_balance
            FROM user u
            WHERE u.role != 'admin'
            ORDER BY u.id DESC
        """)
        all_users = cursor.fetchall()

    except Exception as e:
        print("Admin Dashboard Error:", e)
        total_users, total_platform_assets, total_transactions, all_users = 0, 0, 0, []
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return render_template('admin_dashboard.html',
                           total_users=total_users,
                           total_assets=total_platform_assets,
                           total_transactions=total_transactions,
                           all_users=all_users)


# ==========================================
# ADMIN: MANAGE USERS
# ==========================================
@app.route('/manage_users')
def manage_users():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Access Denied.", "error")
        return redirect(url_for('login'))

    conn, cursor = get_db_connection()
    try:
        cursor.execute("""
            SELECT 
                u.id, u.fullname, u.email, u.role, u.account_status,
                (
                    COALESCE((SELECT SUM(balance) FROM wallet WHERE user_id = u.id), 0) +
                    COALESCE((SELECT SUM(balance) FROM sub_wallet WHERE user_id = u.id), 0)
                ) AS total_balance
            FROM user u
            WHERE u.role != 'admin'
            ORDER BY u.id DESC
        """)
        all_users = cursor.fetchall()
    except Exception as e:
        print("Manage Users Error:", e)
        all_users = []
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return render_template('manage_users.html', all_users=all_users)


@app.route('/make_me_admin')
def make_me_admin():
    print("FLASK IS LOOKING FOR HTML FILES IN:", app.template_folder)
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn, cursor = get_db_connection()
    try:
        cursor.execute("UPDATE user SET role = 'admin' WHERE id = %s", (session['user_id'],))
        conn.commit()
        return "SUCCESS! You are now the Admin. <br><br> <a href='/admin_dashboard'>Click here to enter the Command Center</a>"
    finally:
        cursor.close()
        conn.close()


# ==========================================
# ADMIN: SUSPEND / REACTIVATE USER
# ==========================================
@app.route('/toggle_user_status/<int:target_user_id>', methods=['POST'])
def toggle_user_status(target_user_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    if target_user_id == session['user_id']:
        flash("Safety Protocol: You cannot suspend your own admin account!", "error")
        return redirect(url_for('admin_dashboard'))

    conn, cursor = get_db_connection()
    try:
        cursor.execute("SELECT account_status, fullname FROM user WHERE id=%s", (target_user_id,))
        user = cursor.fetchone()

        if user:
            current_status = user.get('account_status', 'active')
            new_status = 'active' if current_status == 'suspended' else 'suspended'
            cursor.execute("UPDATE user SET account_status=%s WHERE id=%s", (new_status, target_user_id))
            conn.commit()

            if new_status == 'suspended':
                flash(f"{user['fullname']} has been suspended.", "error")
            else:
                flash(f"{user['fullname']} has been reactivated.", "success")

    except Exception as e:
        print("Error toggling user status:", e)
        flash("Database error occurred.", "error")
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return_to = request.form.get('return_to')
    if return_to == 'manage_users':
        return redirect(url_for('manage_users'))
    return redirect(url_for('admin_dashboard'))


# ==========================================
# GLOBAL BROADCAST SYSTEM
# ==========================================
@app.route('/set_global_alert', methods=['POST'])
def set_global_alert():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    message    = request.form.get('alert_message')
    is_clearing = request.form.get('clear')

    conn, cursor = get_db_connection()
    try:
        if is_clearing == 'true':
            cursor.execute("UPDATE system_settings SET global_alert = NULL WHERE id = 1")
            flash("Global alert cleared.", "success")
        else:
            cursor.execute("UPDATE system_settings SET global_alert = %s WHERE id = 1", (message,))
            flash("Broadcast sent to all users!", "success")
        conn.commit()
    except Exception as e:
        print("Broadcast Error:", e)
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return redirect(url_for('admin_dashboard'))


@app.context_processor
def inject_global_alert():
    alert_msg = None
    try:
        conn, cursor = get_db_connection()
        cursor.execute("SELECT global_alert FROM system_settings WHERE id = 1")
        result = cursor.fetchone()
        if result and result['global_alert']:
            alert_msg = result['global_alert']
    except Exception:
        pass
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()
    return dict(global_alert=alert_msg)


# ==========================================
# LOGIN
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email      = request.form.get('email')
        password   = request.form.get('password')
        login_type = request.form.get('login_type', 'user')

        conn, cursor = get_db_connection()
        try:
            cursor.execute("SELECT * FROM user WHERE email=%s", (email,))
            user = cursor.fetchone()

            if user and check_password_hash(user['password'], password):
                if user.get('account_status') == 'suspended':
                    flash("Access Denied: Your account has been suspended by an Administrator.", "error")
                    return redirect(url_for('login'))

                if login_type == 'admin' and user['role'] != 'admin':
                    flash("Access Denied: You do not have administrator privileges.", "error")
                    return redirect(url_for('login'))

                session['user_id'] = user['id']
                session['role']    = user['role']

                if login_type == 'admin':
                    return redirect(url_for('admin_dashboard'))
                return redirect(url_for('dashboard'))
            else:
                flash("Invalid email or password.", "error")

        except Exception as e:
            print("Login Error:", e)
            flash("An error occurred during login.", "error")
        finally:
            if 'cursor' in locals():
                cursor.close()
                conn.close()

    return render_template('login.html')


# ==========================================
# SIGNUP / REGISTER
# ==========================================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    return render_template("/signup.html")


@app.route('/register', methods=['POST'])
def register():
    fullname         = request.form['name']
    email            = request.form['email']
    password         = request.form['password']
    confirm_password = request.form['confirm']

    email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    if not re.match(email_pattern, email):
        flash("Invalid email format!", "error")
        return redirect(url_for('signup'))

    if password != confirm_password:
        flash("Passwords do not match!", "error")
        return redirect(url_for('signup'))

    if len(password) < 8:
        flash("Password must be at least 8 characters long!", "error")
        return redirect(url_for('signup'))

    if not re.search(r"[A-Z]", password):
        flash("Password must contain at least one uppercase letter!", "error")
        return redirect(url_for('signup'))

    if not re.search(r"[a-z]", password):
        flash("Password must contain at least one lowercase letter!", "error")
        return redirect(url_for('signup'))

    if not re.search(r"[0-9]", password):
        flash("Password must contain at least one number!", "error")
        return redirect(url_for('signup'))

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        flash("Password must contain at least one special character!", "error")
        return redirect(url_for('signup'))

    hashed_password = generate_password_hash(password)

    conn, cursor = get_db_connection()
    try:
        cursor.execute("SELECT * FROM user WHERE email=%s", (email,))
        if cursor.fetchone():
            flash("Email already registered!", "error")
            return redirect(url_for('signup'))

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user (fullname, email, password) VALUES (%s, %s, %s)",
            (fullname, email, hashed_password)
        )
        user_id = cursor.lastrowid

        wallet_id = generate_wallet_id(cursor)
        cursor.execute(
            "INSERT INTO wallet (wallet_id, user_id, balance) VALUES (%s, %s, %s)",
            (wallet_id, user_id, 0)
        )
        conn.commit()
        flash("Registration Successful! Wallet Created. Please Log In.", "success")
        return redirect(url_for('login'))

    except mysql.connector.Error as err:
        print("Database Error:", err)
        flash("Registration failed! Please try again.", "error")
        return redirect(url_for('signup'))
    finally:
        cursor.close()
        conn.close()


# ==========================================
# DASHBOARD
# ==========================================
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn, cursor = get_db_connection()
    try:
        cursor.execute("SELECT * FROM user WHERE id=%s", (session['user_id'],))
        user_data = cursor.fetchone()

        cursor.execute("SELECT * FROM wallet WHERE user_id=%s", (session['user_id'],))
        wallet_data = cursor.fetchone()

        cursor.execute("SELECT * FROM sub_wallet WHERE user_id=%s", (session['user_id'],))
        sub_wallets_data = cursor.fetchall()

        total_balance = float(wallet_data['balance']) if wallet_data else 0.0
        for sw in sub_wallets_data:
            total_balance += float(sw['balance'])

        cursor.execute(
            "SELECT SUM(amount) as total FROM transactions WHERE user_id=%s AND transaction_type='Payment'",
            (session['user_id'],)
        )
        spent_result = cursor.fetchone()
        total_spent = float(spent_result['total'] or 0)

        cursor.execute(
            "SELECT * FROM transactions WHERE user_id=%s ORDER BY timestamp DESC LIMIT 5",
            (session['user_id'],)
        )
        recent_transactions = cursor.fetchall()

        cursor.execute(
            "SELECT * FROM transactions WHERE user_id=%s ORDER BY timestamp DESC",
            (session['user_id'],)
        )
        all_transactions = cursor.fetchall()

        # Quick Insights
        insights = {"largest_purchase": None, "transaction_count": 0, "most_frequent_wallet": None}

        cursor.execute("""
            SELECT amount, wallet_name, timestamp 
            FROM transactions 
            WHERE user_id=%s AND transaction_type='Payment' 
            ORDER BY amount DESC LIMIT 1
        """, (session['user_id'],))
        largest_txn = cursor.fetchone()
        if largest_txn:
            insights["largest_purchase"] = {
                "amount": float(largest_txn['amount']),
                "wallet": largest_txn['wallet_name']
            }

        cursor.execute("""
            SELECT COUNT(*) as total_count, wallet_name 
            FROM transactions 
            WHERE user_id=%s AND transaction_type='Payment' AND wallet_name != 'Main Wallet'
            GROUP BY wallet_name 
            ORDER BY total_count DESC LIMIT 1
        """, (session['user_id'],))
        frequent_wallet = cursor.fetchone()
        if frequent_wallet:
            insights["transaction_count"]    = frequent_wallet['total_count']
            insights["most_frequent_wallet"] = frequent_wallet['wallet_name']

        # Envelope Health / Burn Rate
        envelope_health = []

        cursor.execute("SELECT name, balance FROM sub_wallet WHERE user_id=%s", (session['user_id'],))
        current_balances = {row['name']: float(row['balance']) for row in cursor.fetchall()}

        cursor.execute("""
            SELECT wallet_name, SUM(amount) as total_spent, MIN(timestamp) as first_date
            FROM transactions
            WHERE user_id=%s AND transaction_type='Payment' 
              AND wallet_name != 'Main Wallet' 
              AND wallet_name NOT LIKE 'Goal:%%'
            GROUP BY wallet_name
        """, (session['user_id'],))
        envelope_data = cursor.fetchall()

        for env in envelope_data:
            name  = env['wallet_name']
            spent = float(env['total_spent'] or 0)
            days_active = 1
            first_date  = env['first_date']

            if first_date:
                if isinstance(first_date, str):
                    try:
                        first_date = datetime.strptime(str(first_date).split('.')[0], '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        pass
                if isinstance(first_date, datetime):
                    delta = (datetime.now() - first_date).days
                    if delta > 0:
                        days_active = delta

            daily_burn = spent / days_active

            if name in current_balances:
                bal = current_balances[name]
                if daily_burn > 0 and bal > 0:
                    days_left = int(bal / daily_burn)
                    status = "warning" if days_left <= 14 else "healthy"
                    envelope_health.append({"name": name, "burn_rate": daily_burn, "days_left": days_left, "balance": bal, "status": status})
                elif bal <= 0 and spent > 0:
                    envelope_health.append({"name": name, "burn_rate": daily_burn, "days_left": 0, "balance": 0, "status": "critical"})

        for name, bal in current_balances.items():
            if not any(env.get('name') == name for env in envelope_health):
                if bal > 0:
                    envelope_health.append({"name": name, "burn_rate": 0, "days_left": 999, "balance": bal, "status": "untouched"})

    except Exception as e:
        print("Dashboard Error:", e)
        user_data, wallet_data, sub_wallets_data = {}, {}, []
        total_balance, total_spent, recent_transactions = 0, 0, []
        insights, envelope_health, all_transactions = {}, [], []
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return render_template("dash2.html",
                           user=user_data,
                           wallet=wallet_data,
                           sub_wallets=sub_wallets_data,
                           total_balance=total_balance,
                           total_spent=total_spent,
                           transactions=recent_transactions,
                           insights=insights,
                           all_transactions=all_transactions,
                           envelope_health=envelope_health)


# ==========================================
# CREATE SUB-WALLET
# ==========================================
@app.route('/create_sub_wallet', methods=['POST'])
def create_sub_wallet():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    wallet_name    = request.form.get('wallet_name')
    initial_amount = float(request.form.get('initial_amount', 0))

    conn, cursor = get_db_connection()
    try:
        cursor.execute("SELECT balance FROM wallet WHERE user_id=%s", (session['user_id'],))
        main_wallet = cursor.fetchone()

        if not main_wallet or float(main_wallet['balance']) < initial_amount:
            flash("Insufficient funds in Main Wallet!", "error")
            return redirect(url_for('dashboard'))

        cursor.execute("UPDATE wallet SET balance = balance - %s WHERE user_id=%s", (initial_amount, session['user_id']))
        cursor.execute("INSERT INTO sub_wallet (user_id, name, balance) VALUES (%s, %s, %s)", (session['user_id'], wallet_name, initial_amount))

        if initial_amount > 0:
            cursor.execute(
                "INSERT INTO transactions (user_id, amount, wallet_name, transaction_type) VALUES (%s, %s, %s, %s)",
                (session['user_id'], initial_amount, wallet_name, 'Allocation')
            )

        conn.commit()
        flash(f"Sub-wallet '{wallet_name}' created with Rs.{initial_amount}!", "success")

    except Exception as e:
        print("Error creating sub-wallet:", e)
        flash("Failed to create sub-wallet.", "error")
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return redirect(url_for('dashboard'))


# ==========================================
# ADD FUNDS TO SUB-WALLET
# ==========================================
@app.route('/add_funds/<int:sub_id>', methods=['POST'])
def add_funds(sub_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    amount = float(request.form.get('amount', 0))

    conn, cursor = get_db_connection()
    try:
        cursor.execute("SELECT balance FROM wallet WHERE user_id=%s", (session['user_id'],))
        main_wallet = cursor.fetchone()

        if not main_wallet or float(main_wallet['balance']) < amount:
            flash("Insufficient funds in Main Wallet!", "error")
            return redirect(url_for('dashboard'))

        cursor.execute("SELECT name FROM sub_wallet WHERE id=%s AND user_id=%s", (sub_id, session['user_id']))
        sub_wallet = cursor.fetchone()

        if not sub_wallet:
            flash("Sub-wallet not found!", "error")
            return redirect(url_for('dashboard'))

        sub_name = sub_wallet['name']
        cursor.execute("UPDATE wallet SET balance = balance - %s WHERE user_id=%s", (amount, session['user_id']))
        cursor.execute("UPDATE sub_wallet SET balance = balance + %s WHERE id=%s AND user_id=%s", (amount, sub_id, session['user_id']))
        cursor.execute(
            "INSERT INTO transactions (user_id, amount, wallet_name, transaction_type) VALUES (%s, %s, %s, %s)",
            (session['user_id'], amount, sub_name, 'Allocation')
        )
        conn.commit()
        flash(f"Added Rs.{amount} to {sub_name}!", "success")

    except Exception as e:
        print("Error adding funds:", e)
        flash("Failed to transfer funds.", "error")
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return redirect(url_for('dashboard'))


# ==========================================
# DELETE SUB-WALLET
# ==========================================
@app.route('/delete_sub_wallet/<int:sub_id>', methods=['POST'])
def delete_sub_wallet(sub_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn, cursor = get_db_connection()
    try:
        cursor.execute("SELECT balance, name FROM sub_wallet WHERE id=%s AND user_id=%s", (sub_id, session['user_id']))
        sub_wallet = cursor.fetchone()

        if sub_wallet:
            refund_amount = float(sub_wallet['balance'])
            sub_name      = sub_wallet['name']

            cursor.execute("UPDATE wallet SET balance = balance + %s WHERE user_id=%s", (refund_amount, session['user_id']))
            cursor.execute("DELETE FROM sub_wallet WHERE id=%s", (sub_id,))

            if refund_amount > 0:
                cursor.execute(
                    "INSERT INTO transactions (user_id, amount, wallet_name, transaction_type) VALUES (%s, %s, %s, %s)",
                    (session['user_id'], refund_amount, f"Main Wallet (from {sub_name})", 'Refund')
                )

            conn.commit()
            flash(f"Discarded '{sub_name}'. Rs.{refund_amount} returned to Main Wallet.", "success")
        else:
            flash("Sub-wallet not found.", "error")

    except Exception as e:
        print("Error deleting sub-wallet:", e)
        flash("Failed to discard sub-wallet.", "error")
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return redirect(url_for('dashboard'))


# ==========================================
# RAZORPAY: CREATE PAYMENT ORDER
# ==========================================
@app.route('/create_order', methods=['POST'])
def create_order():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    amount        = float(request.form.get('amount', 0))
    wallet_source = request.form.get('wallet_source')

    if amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400

    conn, cursor = get_db_connection()
    try:
        if wallet_source == 'main':
            cursor.execute("SELECT balance FROM wallet WHERE user_id=%s", (session['user_id'],))
            wallet = cursor.fetchone()
            if not wallet or float(wallet['balance']) < amount:
                return jsonify({"error": "Insufficient balance in Main Wallet!"}), 400
        else:
            sub_id = wallet_source.split('_')[1]
            cursor.execute("SELECT balance FROM sub_wallet WHERE id=%s AND user_id=%s", (sub_id, session['user_id']))
            sub = cursor.fetchone()
            if not sub or float(sub['balance']) < amount:
                return jsonify({"error": "Insufficient balance in Sub-Wallet!"}), 400
    except Exception as e:
        print("Balance Check Error:", e)
        return jsonify({"error": "Failed to verify balance."}), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    data  = {"amount": int(amount * 100), "currency": "INR", "payment_capture": "1"}
    order = client.order.create(data=data)

    return jsonify({
        "order_id":     order['id'],
        "amount":       order['amount'],
        "key":          RAZORPAY_KEY_ID,
        "wallet_source": wallet_source
    })


# ==========================================
# RAZORPAY: VERIFY PAYMENT & DEDUCT
# ==========================================
@app.route('/verify_payment', methods=['POST'])
def verify_payment():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    amount_spent  = float(request.form.get('amount', 0))
    wallet_source = request.form.get('wallet_source', 'main')

    conn, cursor = get_db_connection()
    try:
        # --- SCENARIO 1: MAIN WALLET (with Round-Up) ---
        if wallet_source == 'main':
            cursor.execute("SELECT balance FROM wallet WHERE user_id=%s", (session['user_id'],))
            current_bal = float(cursor.fetchone()['balance'])
            if amount_spent > current_bal:
                flash("Transaction Failed: Insufficient balance in Main Wallet!", "error")
                return redirect(url_for('wallets'))

            cursor.execute("UPDATE wallet SET balance = balance - %s WHERE user_id=%s", (amount_spent, session['user_id']))
            cursor.execute("""
                INSERT INTO transactions (user_id, wallet_name, transaction_type, amount) 
                VALUES (%s, %s, %s, %s)
            """, (session['user_id'], 'Main Wallet', 'Payment', amount_spent))

            # Round-Up logic
            next_hundred = math.ceil(amount_spent / 100.0) * 100
            spare_change = next_hundred - amount_spent

            if spare_change > 0:
                cursor.execute(
                    "SELECT id, name FROM savings_goals WHERE user_id=%s ORDER BY is_priority DESC, id ASC LIMIT 1",
                    (session['user_id'],)
                )
                priority_goal = cursor.fetchone()

                if priority_goal:
                    cursor.execute("UPDATE wallet SET balance = balance - %s WHERE user_id=%s", (spare_change, session['user_id']))
                    cursor.execute("UPDATE savings_goals SET current_balance = current_balance + %s WHERE id=%s", (spare_change, priority_goal['id']))

                    goal_label = f"Goal: {priority_goal['name']}"
                    cursor.execute("""
                        INSERT INTO transactions (user_id, wallet_name, transaction_type, amount) 
                        VALUES (%s, %s, %s, %s)
                    """, (session['user_id'], goal_label, 'Transfer', spare_change))

                    # Check if goal is completed
                    cursor.execute("SELECT fullname, email FROM user WHERE id=%s", (session['user_id'],))
                    user_info = cursor.fetchone()
                    cursor.execute("SELECT name, target_amount, current_balance FROM savings_goals WHERE id=%s", (priority_goal['id'],))
                    updated_goal = cursor.fetchone()

                    if updated_goal and float(updated_goal['current_balance']) >= float(updated_goal['target_amount']):
                        html_body = get_goal_completed_template(
                            user_name=user_info['fullname'],
                            goal_name=updated_goal['name'],
                            total_saved=float(updated_goal['current_balance'])
                        )
                        # FIXED: wrapped in safe_send_email so it never crashes the payment
                        safe_send_email(
                            to_email=user_info['email'],
                            subject=f"Goal Completed: {updated_goal['name']}!",
                            html_content=html_body
                        )
                        flash(f"Payment successful! Rs.{spare_change} automatically saved to '{priority_goal['name']}'.", "success")
                    else:
                        flash("Payment successful!", "success")
            else:
                flash("Payment successful! (Exact 100s, no round-up).", "success")

        # --- SCENARIO 2: SUB-WALLET (No Round-Up) ---
        else:
            sub_id = wallet_source.split('_')[1]
            cursor.execute("SELECT balance, name FROM sub_wallet WHERE id=%s AND user_id=%s", (sub_id, session['user_id']))
            sub_data = cursor.fetchone()

            if not sub_data or amount_spent > float(sub_data['balance']):
                flash("Transaction Failed: Insufficient balance in Sub-Wallet!", "error")
                return redirect(url_for('wallets'))

            sub_name = sub_data['name']
            cursor.execute("UPDATE sub_wallet SET balance = balance - %s WHERE id=%s AND user_id=%s", (amount_spent, sub_id, session['user_id']))
            cursor.execute("""
                INSERT INTO transactions (user_id, wallet_name, transaction_type, amount) 
                VALUES (%s, %s, %s, %s)
            """, (session['user_id'], sub_name, 'Payment', amount_spent))

            # Burn Rate Email Check
            cursor.execute("SELECT fullname, email FROM user WHERE id=%s", (session['user_id'],))
            user_info = cursor.fetchone()

            cursor.execute("SELECT balance FROM sub_wallet WHERE id=%s", (sub_id,))
            current_bal = float(cursor.fetchone()['balance'])

            cursor.execute("""
                SELECT SUM(amount) as total_spent, MIN(timestamp) as first_date
                FROM transactions WHERE user_id=%s AND transaction_type='Payment' AND wallet_name=%s
            """, (session['user_id'], sub_name))
            stats = cursor.fetchone()

            if stats and stats['total_spent'] and current_bal > 0:
                spent      = float(stats['total_spent'])
                first_date = stats['first_date']
                days_active = 1

                if isinstance(first_date, str):
                    try:
                        first_date = datetime.strptime(str(first_date).split('.')[0], '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        pass
                if isinstance(first_date, datetime):
                    delta = (datetime.now() - first_date).days
                    if delta > 0:
                        days_active = delta

                daily_burn = spent / days_active
                if daily_burn > 0:
                    days_left = int(current_bal / daily_burn)
                    if days_left <= 14:
                        html_body = get_burn_rate_template(
                            user_name=user_info['fullname'],
                            wallet_name=sub_name,
                            burn_rate=daily_burn,
                            days_left=days_left
                        )
                        # FIXED: wrapped in safe_send_email
                        safe_send_email(
                            to_email=user_info['email'],
                            subject=f"High Spend Alert: {sub_name}",
                            html_content=html_body
                        )

            flash("Payment successful from Sub-Wallet!", "success")

        conn.commit()

    except Exception as e:
        print("Payment Error:", e)
        conn.rollback()
        flash("Payment failed to process.", "error")
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return redirect(url_for('wallets'))


# ==========================================
# RAZORPAY: CREATE ADD FUNDS ORDER
# ==========================================
@app.route('/create_add_funds_order', methods=['POST'])
def create_add_funds_order():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    amount = float(request.form.get('amount', 0))
    if amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400

    data  = {"amount": int(amount * 100), "currency": "INR", "payment_capture": "1"}
    order = client.order.create(data=data)

    return jsonify({"order_id": order['id'], "amount": order['amount'], "key": RAZORPAY_KEY_ID})


# ==========================================
# RAZORPAY: VERIFY ADD FUNDS
# ==========================================
@app.route('/verify_add_funds', methods=['POST'])
def verify_add_funds():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    payment_id = request.form.get('razorpay_payment_id')
    order_id   = request.form.get('razorpay_order_id')
    signature  = request.form.get('razorpay_signature')
    amount     = float(request.form.get('amount', 0))

    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id':   order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature':  signature
        })

        conn, cursor = get_db_connection()
        cursor.execute("UPDATE wallet SET balance = balance + %s WHERE user_id=%s", (amount, session['user_id']))
        cursor.execute(
            "INSERT INTO transactions (user_id, amount, wallet_name, transaction_type) VALUES (%s,%s,%s,%s)",
            (session['user_id'], amount, 'Main Wallet', 'Deposit')
        )
        conn.commit()
        flash(f"Successfully added Rs.{amount} to Main Wallet!", "success")

    except razorpay.errors.SignatureVerificationError:
        flash("Verification failed! Money was not added.", "error")
    except Exception as e:
        print("Transaction Error:", e)
        flash("Failed to add funds.", "error")
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return redirect(url_for('dashboard'))


# ==========================================
# WALLETS & GOALS PAGE
# ==========================================
@app.route('/wallets')
def wallets():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn, cursor = get_db_connection()
    try:
        cursor.execute("SELECT fullname, email FROM user WHERE id=%s", (session['user_id'],))
        user_data = cursor.fetchone()

        cursor.execute("SELECT wallet_id, balance FROM wallet WHERE user_id=%s", (session['user_id'],))
        wallet_data = cursor.fetchone()

        cursor.execute("SELECT id, name, balance FROM sub_wallet WHERE user_id=%s", (session['user_id'],))
        sub_wallets_data = cursor.fetchall()

        cursor.execute("SELECT * FROM savings_goals WHERE user_id=%s ORDER BY is_priority DESC, id ASC", (session['user_id'],))
        goals_data = cursor.fetchall()

        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')

        for goal in goals_data:
            target  = float(goal.get('target_amount') or 0.0)
            current = float(goal.get('current_balance') or 0.0)

            goal['percent'] = min(int((current / target) * 100), 100) if target > 0 else 0

            remaining = target - current

            cursor.execute("""
                SELECT SUM(amount) as recent_saved
                FROM transactions
                WHERE user_id=%s AND transaction_type='Transfer'
                  AND wallet_name = %s AND timestamp >= %s
            """, (session['user_id'], f"Goal: {goal['name']}", thirty_days_ago))

            recent_data     = cursor.fetchone()
            saved_last_30   = float(recent_data['recent_saved'] if recent_data and recent_data['recent_saved'] else 0)

            if saved_last_30 > 0 and remaining > 0:
                daily_rate = saved_last_30 / 30
                days_left  = int(remaining / daily_rate)
                if days_left < 3650:
                    predicted_date   = datetime.now() + timedelta(days=days_left)
                    goal['prediction'] = predicted_date.strftime('%B %d, %Y')
                else:
                    goal['prediction'] = "Over 10 years at current rate"
            elif remaining <= 0:
                goal['prediction'] = "Goal Reached!"
            else:
                goal['prediction'] = "No recent savings to predict."

    except Exception as e:
        print("CRITICAL ERROR ON WALLETS PAGE:", e)
        user_data, wallet_data, sub_wallets_data, goals_data = {}, {}, [], []
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return render_template("wallet.html",
                           user=user_data,
                           wallet=wallet_data,
                           sub_wallets=sub_wallets_data,
                           goals=goals_data)


# ==========================================
# CREATE SAVINGS GOAL
# ==========================================
@app.route('/create_goal', methods=['POST'])
def create_goal():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    goal_name     = request.form.get('goal_name')
    target_amount = float(request.form.get('target_amount', 0))
    goal_icon     = request.form.get('goal_icon', 'stars')

    if target_amount <= 0 or not goal_name:
        flash("Invalid goal details.", "error")
        return redirect(url_for('wallets'))

    conn, cursor = get_db_connection()
    try:
        cursor.execute(
            "INSERT INTO savings_goals (user_id, name, target_amount, current_balance, icon) VALUES (%s, %s, %s, %s, %s)",
            (session['user_id'], goal_name, target_amount, 0.0, goal_icon)
        )
        conn.commit()
        flash(f"Goal '{goal_name}' created successfully!", "success")
    except Exception as e:
        print("Error creating goal:", e)
        flash("Failed to create savings goal.", "error")
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return redirect(url_for('wallets'))


# ==========================================
# DELETE SAVINGS GOAL
# ==========================================
@app.route('/delete_goal/<int:goal_id>', methods=['POST'])
def delete_goal(goal_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn, cursor = get_db_connection()
    try:
        cursor.execute("SELECT current_balance, name FROM savings_goals WHERE id=%s AND user_id=%s", (goal_id, session['user_id']))
        goal = cursor.fetchone()

        if goal:
            if float(goal.get('current_balance') or 0) > 0:
                cursor.execute("UPDATE wallet SET balance = balance + %s WHERE user_id=%s", (goal['current_balance'], session['user_id']))
            cursor.execute("DELETE FROM savings_goals WHERE id=%s", (goal_id,))
            conn.commit()
            flash(f"Goal '{goal['name']}' discarded. Funds refunded to Main Wallet.", "success")
    except Exception as e:
        print("Error deleting goal:", e)
        flash("Could not delete goal.", "error")
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return redirect(url_for('wallets'))


# ==========================================
# MAKE GOAL PRIORITY
# ==========================================
@app.route('/make_priority/<int:goal_id>', methods=['POST'])
def make_priority(goal_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn, cursor = get_db_connection()
    try:
        cursor.execute("UPDATE savings_goals SET is_priority = FALSE WHERE user_id=%s", (session['user_id'],))
        cursor.execute("UPDATE savings_goals SET is_priority = TRUE WHERE id=%s AND user_id=%s", (goal_id, session['user_id']))
        conn.commit()
        flash("Priority updated successfully!", "success")
    except Exception as e:
        print("Error updating priority:", e)
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return redirect(url_for('wallets'))


# ==========================================
# DISABLE SAVINGS (KILL SWITCH)
# ==========================================
@app.route('/disable_savings', methods=['POST'])
def disable_savings():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn, cursor = get_db_connection()
    try:
        cursor.execute("SELECT SUM(current_balance) as total_saved FROM savings_goals WHERE user_id=%s", (session['user_id'],))
        result      = cursor.fetchone()
        total_saved = float(result['total_saved'] or 0)

        if total_saved > 0:
            cursor.execute("UPDATE wallet SET balance = balance + %s WHERE user_id=%s", (total_saved, session['user_id']))
            cursor.execute("""
                INSERT INTO transactions (user_id, wallet_name, transaction_type, amount) 
                VALUES (%s, %s, %s, %s)
            """, (session['user_id'], 'Savings Refund', 'Transfer', total_saved))

        cursor.execute("DELETE FROM savings_goals WHERE user_id=%s", (session['user_id'],))
        conn.commit()
        flash(f"Savings Feature Disabled. Rs.{total_saved} refunded to Main Wallet.", "success")

    except Exception as e:
        print("Error disabling savings:", e)
        conn.rollback()
        flash("Failed to disable savings.", "error")
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return redirect(url_for('wallets'))


# ==========================================
# PAY FROM GOAL
# ==========================================
@app.route('/pay_goal/<int:goal_id>', methods=['POST'])
def pay_goal(goal_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    amount_spent = float(request.form.get('amount_spent', 0))

    conn, cursor = get_db_connection()
    try:
        cursor.execute("SELECT * FROM savings_goals WHERE id=%s AND user_id=%s", (goal_id, session['user_id']))
        goal = cursor.fetchone()

        current_balance = float(goal['current_balance'])
        was_priority = bool(goal.get('is_priority'))

        if amount_spent > current_balance:
            flash("You cannot spend more than the total saved in this goal!", "error")
            return redirect(url_for('wallets'))

        leftover_change = current_balance - amount_spent

        cursor.execute("""
            INSERT INTO transactions (user_id, wallet_name, transaction_type, amount) 
            VALUES (%s, %s, %s, %s)
        """, (session['user_id'], f"Purchase: {goal['name']}", 'Payment', amount_spent))

        if leftover_change > 0:
            cursor.execute("""
                SELECT id, name FROM savings_goals 
                WHERE user_id=%s AND id != %s 
                ORDER BY is_priority DESC, id ASC LIMIT 1
            """, (session['user_id'], goal_id))
            next_goal = cursor.fetchone()

            if next_goal:
                cursor.execute("UPDATE savings_goals SET current_balance = current_balance + %s WHERE id=%s", (leftover_change, next_goal['id']))
                flash(f"Purchase successful! Rs.{leftover_change:.2f} rolled over to '{next_goal['name']}'.", "success")
            else:
                cursor.execute("UPDATE wallet SET balance = balance + %s WHERE user_id=%s", (leftover_change, session['user_id']))
                flash(f"Purchase successful! Rs.{leftover_change:.2f} returned to Main Wallet.", "success")
        else:
            flash("Purchase successful! You spent the exact amount saved.", "success")

        # Remove completed goal from active savings goals, as requested
        cursor.execute("DELETE FROM savings_goals WHERE id=%s", (goal_id,))

        if was_priority:
            cursor.execute("UPDATE savings_goals SET is_priority = FALSE WHERE user_id=%s", (session['user_id'],))
            cursor.execute("SELECT id FROM savings_goals WHERE user_id=%s ORDER BY id ASC LIMIT 1", (session['user_id'],))
            promoted_goal = cursor.fetchone()
            if promoted_goal:
                cursor.execute("UPDATE savings_goals SET is_priority = TRUE WHERE id=%s", (promoted_goal['id'],))

        # Celebration email — FIXED: uses safe_send_email
        cursor.execute("SELECT email, fullname FROM user WHERE id=%s", (session['user_id'],))
        user = cursor.fetchone()
        if user and goal:
            html_content = get_goal_completed_template(
                user_name=user['fullname'],
                goal_name=goal['name'],
                total_saved=float(goal['target_amount'])
            )
            safe_send_email(user['email'], "Goal Achieved!", html_content)

        conn.commit()

    except Exception as e:
        print("Goal Payment Error:", e)
        conn.rollback()
        flash("Something went wrong while processing your goal payment.", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('wallets'))


# ==========================================
# VERIFY GOAL PAYMENT (Razorpay)
# ==========================================
@app.route('/verify_goal_payment', methods=['POST'])
def verify_goal_payment():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    payment_id   = request.form.get('razorpay_payment_id')
    order_id     = request.form.get('razorpay_order_id')
    signature    = request.form.get('razorpay_signature')
    goal_id      = request.form.get('goal_id')
    amount_spent = float(request.form.get('amount_spent', 0))

    try:
        client.utility.verify_payment_signature({
            'razorpay_order_id':   order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature':  signature
        })

        conn, cursor = get_db_connection()

        cursor.execute("SELECT * FROM savings_goals WHERE id=%s AND user_id=%s", (goal_id, session['user_id']))
        goal = cursor.fetchone()

        if not goal:
            flash("Goal not found.", "error")
            return redirect(url_for('wallets'))

        current_balance = float(goal['current_balance'])
        was_priority = bool(goal.get('is_priority'))
        leftover_change = current_balance - amount_spent

        cursor.execute("""
            INSERT INTO transactions (user_id, wallet_name, transaction_type, amount) 
            VALUES (%s, %s, %s, %s)
        """, (session['user_id'], f"Goal Purchase: {goal['name']}", 'Payment', amount_spent))

        if leftover_change > 0:
            cursor.execute("""
                SELECT id, name FROM savings_goals 
                WHERE user_id=%s AND id != %s 
                ORDER BY is_priority DESC, id ASC LIMIT 1
            """, (session['user_id'], goal_id))
            next_goal = cursor.fetchone()

            if next_goal:
                cursor.execute("UPDATE savings_goals SET current_balance = current_balance + %s WHERE id=%s", (leftover_change, next_goal['id']))
                flash(f"Payment successful! Rs.{leftover_change:.2f} auto-transferred to '{next_goal['name']}'.", "success")
            else:
                cursor.execute("UPDATE wallet SET balance = balance + %s WHERE user_id=%s", (leftover_change, session['user_id']))
                flash(f"Payment successful! Rs.{leftover_change:.2f} returned to Main Wallet.", "success")
        else:
            flash("Payment successful! You spent the exact amount saved.", "success")

        # Remove completed goal from active savings goals, as requested
        cursor.execute("DELETE FROM savings_goals WHERE id=%s", (goal_id,))

        if was_priority:
            cursor.execute("UPDATE savings_goals SET is_priority = FALSE WHERE user_id=%s", (session['user_id'],))
            cursor.execute("SELECT id FROM savings_goals WHERE user_id=%s ORDER BY id ASC LIMIT 1", (session['user_id'],))
            promoted_goal = cursor.fetchone()
            if promoted_goal:
                cursor.execute("UPDATE savings_goals SET is_priority = TRUE WHERE id=%s", (promoted_goal['id'],))
        # Celebration email — FIXED: uses safe_send_email
        cursor.execute("SELECT email, fullname FROM user WHERE id=%s", (session['user_id'],))
        user = cursor.fetchone()
        if user and goal:
            html_content = get_goal_completed_template(
                user_name=user['fullname'],
                goal_name=goal['name'],
                total_saved=float(goal['target_amount'])
            )
            safe_send_email(user['email'], "Goal Achieved!", html_content)

        conn.commit()

    except razorpay.errors.SignatureVerificationError:
        flash("Razorpay Verification failed! Payment was not recorded.", "error")
    except Exception as e:
        print("Goal Verification Error:", e)
        if 'conn' in locals():
            conn.rollback()
        flash("Something went wrong while processing your goal.", "error")
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return redirect(url_for('wallets'))


# ==========================================
# ANALYSIS PAGE
# ==========================================
@app.route('/analysis')
def analysis():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_data        = {}
    total_net_worth  = 0
    total_spent      = 0
    auto_saved       = 0
    envelope_health  = []
    sub_wallets      = []
    spent_trend      = {"pct": 0, "dir": "flat"}
    saved_trend      = {"pct": 0, "dir": "flat"}
    chart_data       = {
        "assets_labels": [], "assets_values": [],
        "expense_labels": [], "expense_values": [],
        "expense_deleted_flags": []
    }

    conn, cursor = get_db_connection()
    try:
        days_filter = request.args.get('days', 30, type=int)
        cutoff_date = (datetime.now() - timedelta(days=days_filter)).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute("SELECT fullname FROM user WHERE id=%s", (session['user_id'],))
        user_data = cursor.fetchone()

        cursor.execute("SELECT balance FROM wallet WHERE user_id=%s", (session['user_id'],))
        main_wallet = cursor.fetchone()
        main_bal    = float(main_wallet['balance'] if main_wallet else 0)

        cursor.execute("SELECT SUM(balance) as total FROM sub_wallet WHERE user_id=%s", (session['user_id'],))
        sub_wallet_total = float(cursor.fetchone()['total'] or 0)

        cursor.execute("SELECT SUM(current_balance) as total FROM savings_goals WHERE user_id=%s", (session['user_id'],))
        savings_total = float(cursor.fetchone()['total'] or 0)

        total_net_worth = main_bal + sub_wallet_total + savings_total

        cursor.execute("SELECT name, balance FROM sub_wallet WHERE user_id=%s", (session['user_id'],))
        current_balances = {row['name']: float(row['balance']) for row in cursor.fetchall()}
        sub_wallets = [{"name": name, "balance": bal} for name, bal in current_balances.items()]

        # Expense Breakdown
        cursor.execute("""
            SELECT wallet_name, SUM(amount) as total_spent 
            FROM transactions 
            WHERE user_id=%s 
              AND transaction_type='Payment'
              AND wallet_name NOT LIKE 'Purchased: %%' 
              AND wallet_name NOT LIKE 'Goal: %%'
              AND wallet_name NOT IN (SELECT name FROM savings_goals WHERE user_id=%s)
              AND timestamp >= %s
            GROUP BY wallet_name
        """, (session['user_id'], session['user_id'], cutoff_date))
        expenses = cursor.fetchall()

        expense_labels        = []
        expense_values        = []
        expense_deleted_flags = []

        if expenses:
            for exp in expenses:
                w_name = exp['wallet_name']
                expense_labels.append(w_name)
                expense_values.append(float(exp['total_spent']))
                expense_deleted_flags.append(w_name != 'Main Wallet' and w_name not in current_balances)
        else:
            expense_labels        = ["No Data"]
            expense_values        = [0]
            expense_deleted_flags = [False]

        # All-time total spent
        cursor.execute("""
            SELECT SUM(amount) as all_time_spent 
            FROM transactions 
            WHERE user_id=%s 
              AND transaction_type='Payment'
              AND wallet_name NOT LIKE 'Purchased: %%' 
              AND wallet_name NOT LIKE 'Goal: %%'
              AND wallet_name NOT IN (SELECT name FROM savings_goals WHERE user_id=%s)
        """, (session['user_id'], session['user_id']))
        total_spent = float(cursor.fetchone()['all_time_spent'] or 0)

        # Auto-saved (all time)
        cursor.execute("""
            SELECT SUM(amount) as total_saved 
            FROM transactions 
            WHERE user_id=%s AND transaction_type='Transfer' AND wallet_name LIKE 'Goal:%%'
        """, (session['user_id'],))
        auto_saved = float(cursor.fetchone()['total_saved'] or 0)

        # MoM Trends
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        sixty_days_ago  = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute("""SELECT SUM(amount) as total FROM transactions 
            WHERE user_id=%s AND transaction_type='Payment' 
            AND wallet_name NOT LIKE 'Purchased: %%' AND wallet_name NOT LIKE 'Goal: %%'
            AND wallet_name NOT IN (SELECT name FROM savings_goals WHERE user_id=%s)
            AND timestamp >= %s""", (session['user_id'], session['user_id'], thirty_days_ago))
        spent_last_30 = float(cursor.fetchone()['total'] or 0)

        cursor.execute("""SELECT SUM(amount) as total FROM transactions 
            WHERE user_id=%s AND transaction_type='Payment'
            AND wallet_name NOT LIKE 'Purchased: %%' AND wallet_name NOT LIKE 'Goal: %%'
            AND wallet_name NOT IN (SELECT name FROM savings_goals WHERE user_id=%s)
            AND timestamp >= %s AND timestamp < %s""",
            (session['user_id'], session['user_id'], sixty_days_ago, thirty_days_ago))
        spent_prev_30 = float(cursor.fetchone()['total'] or 0)

        cursor.execute("""SELECT SUM(amount) as total FROM transactions 
            WHERE user_id=%s AND transaction_type='Transfer' AND wallet_name LIKE 'Goal:%%' AND timestamp >= %s""",
            (session['user_id'], thirty_days_ago))
        saved_last_30 = float(cursor.fetchone()['total'] or 0)

        cursor.execute("""SELECT SUM(amount) as total FROM transactions 
            WHERE user_id=%s AND transaction_type='Transfer' AND wallet_name LIKE 'Goal:%%'
            AND timestamp >= %s AND timestamp < %s""",
            (session['user_id'], sixty_days_ago, thirty_days_ago))
        saved_prev_30 = float(cursor.fetchone()['total'] or 0)

        def get_trend(current, previous):
            if previous == 0:
                return {"pct": 100 if current > 0 else 0, "dir": "up" if current > 0 else "flat"}
            diff = current - previous
            pct  = abs((diff / previous) * 100)
            return {"pct": pct, "dir": "up" if diff > 0 else "down" if diff < 0 else "flat"}

        spent_trend = get_trend(spent_last_30, spent_prev_30)
        saved_trend = get_trend(saved_last_30, saved_prev_30)

        # Envelope Burn Rate
        cursor.execute("""
            SELECT t.wallet_name, SUM(t.amount) as total_spent, MIN(t.timestamp) as first_date
            FROM transactions t
            INNER JOIN sub_wallet s ON t.wallet_name = s.name AND t.user_id = s.user_id
            WHERE t.user_id=%s AND t.transaction_type='Payment' AND t.timestamp >= s.created_at
            GROUP BY t.wallet_name
        """, (session['user_id'],))
        envelope_data = cursor.fetchall()

        for env in envelope_data:
            name        = env['wallet_name']
            spent       = float(env['total_spent'] or 0)
            days_active = 1
            first_date  = env['first_date']

            if first_date:
                if isinstance(first_date, str):
                    try:
                        first_date = datetime.strptime(str(first_date).split('.')[0], '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        pass
                if isinstance(first_date, datetime):
                    delta = (datetime.now() - first_date).days
                    if delta > 0:
                        days_active = delta

            daily_burn = spent / days_active

            if name in current_balances:
                bal = current_balances[name]
                if daily_burn > 0 and bal > 0:
                    days_left = int(bal / daily_burn)

                    if days_left < 5:
                        envelope_health.append({"name": name, "burn_rate": daily_burn, "days_left": days_left, "balance": bal, "status": "warning"})
                        alert_key = f"burn_alert_sent_{name}"
                        if alert_key not in session:
                            cursor.execute("SELECT email, fullname FROM user WHERE id=%s", (session['user_id'],))
                            user_details = cursor.fetchone()
                            if user_details:
                                html_content = get_burn_rate_template(
                                    user_name=user_details['fullname'],
                                    wallet_name=name,
                                    burn_rate=daily_burn,
                                    days_left=days_left
                                )
                                # FIXED: uses safe_send_email
                                safe_send_email(user_details['email'], f"SWM Alert: High Spend Rate on {name}", html_content)
                                session[alert_key] = True

                    elif days_left > 15:
                        envelope_health.append({"name": name, "burn_rate": daily_burn, "days_left": days_left, "balance": bal, "status": "healthy"})
                    else:
                        envelope_health.append({"name": name, "burn_rate": daily_burn, "days_left": days_left, "balance": bal, "status": "moderate"})

                elif bal <= 0 and spent > 0:
                    envelope_health.append({"name": name, "burn_rate": daily_burn, "days_left": 0, "balance": 0, "status": "critical"})

        for name, bal in current_balances.items():
            if not any(env.get('name') == name for env in envelope_health):
                if bal > 0:
                    envelope_health.append({"name": name, "burn_rate": 0, "days_left": 999, "balance": bal, "status": "untouched"})

        chart_data = {
            "assets_labels":        ["Main Wallet", "Sub-Wallets"],
            "assets_values":        [main_bal, sub_wallet_total],
            "expense_labels":       expense_labels,
            "expense_values":       expense_values,
            "expense_deleted_flags": expense_deleted_flags
        }

    except Exception as e:
        print("Analysis Error:", e)
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return render_template("analysis.html",
                           user=user_data,
                           net_worth=total_net_worth,
                           total_spent=total_spent,
                           auto_saved=auto_saved,
                           chart_data=chart_data,
                           envelope_health=envelope_health,
                           sub_wallets=sub_wallets,
                           spent_trend=spent_trend,
                           saved_trend=saved_trend)


# ==========================================
# TRANSACTION HISTORY
# ==========================================
@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn, cursor = get_db_connection()
    try:
        cursor.execute("SELECT fullname FROM user WHERE id=%s", (session['user_id'],))
        user_data = cursor.fetchone()
        cursor.execute("SELECT * FROM transactions WHERE user_id=%s ORDER BY timestamp DESC", (session['user_id'],))
        all_transactions = cursor.fetchall()
    except Exception as e:
        print("History Error:", e)
        user_data, all_transactions = {}, []
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return render_template("history.html", user=user_data, transactions=all_transactions)


# ==========================================
# PROFILE
# ==========================================
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn, cursor = get_db_connection()
    try:
        cursor.execute("SELECT * FROM user WHERE id=%s", (session['user_id'],))
        user_data = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) as tx_count FROM transactions WHERE user_id=%s", (session['user_id'],))
        tx_data  = cursor.fetchone()
        tx_count = tx_data['tx_count'] if tx_data else 0
    except Exception as e:
        print("Profile Error:", e)
        user_data, tx_count = {}, 0
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return render_template("profile.html", user=user_data, tx_count=tx_count)


# ==========================================
# UPDATE PROFILE
# ==========================================
@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    new_name  = request.form.get('fullname')
    new_email = request.form.get('email')

    conn, cursor = get_db_connection()
    try:
        cursor.execute("UPDATE user SET fullname=%s, email=%s WHERE id=%s", (new_name, new_email, session['user_id']))
        conn.commit()
        flash("Profile updated successfully!", "success")
    except Exception as e:
        print("Update Profile Error:", e)
        flash("Error updating profile.", "error")
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return redirect(url_for('profile'))


# ==========================================
# DOWNLOAD LEDGER
# ==========================================
@app.route('/download_ledger', methods=['GET'])
def download_ledger():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    timeframe = request.args.get('timeframe', 'all')
    user_id   = session['user_id']

    conn, cursor = get_db_connection()
    try:
        base_query      = "SELECT timestamp, wallet_name, transaction_type, amount FROM transactions WHERE user_id = %s"
        params          = [user_id]
        timeframe_label = "All Time"

        if timeframe == '1m':
            base_query      += " AND timestamp >= NOW() - INTERVAL 1 MONTH"
            timeframe_label  = "Last 30 Days"
        elif timeframe == '12m':
            base_query      += " AND timestamp >= NOW() - INTERVAL 1 YEAR"
            timeframe_label  = "Last 12 Months"

        base_query += " ORDER BY timestamp DESC"
        cursor.execute(base_query, tuple(params))
        transactions = cursor.fetchall()

        total_inflow  = sum(float(tx['amount']) for tx in transactions if tx['transaction_type'] != 'Payment')
        total_outflow = sum(float(tx['amount']) for tx in transactions if tx['transaction_type'] == 'Payment')

        summary = {
            "total_count":  len(transactions),
            "total_inflow":  total_inflow,
            "total_outflow": total_outflow,
            "net_change":    total_inflow - total_outflow
        }

    except Exception as e:
        print("Ledger Download Error:", e)
        return "An error occurred while generating your ledger.", 500
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return render_template('pdf.html', transactions=transactions, summary=summary, timeframe_label=timeframe_label)


# ==========================================
# FORGOT PASSWORD
# ==========================================
@app.route('/forgot-password')
def forgot_password_page():
    return render_template('forget.html')


@app.route('/send-otp', methods=['POST'])
def send_otp():
    data  = request.get_json()
    email = data.get('email')

    conn, cursor = get_db_connection()
    cursor.execute("SELECT * FROM user WHERE email=%s", (email,))
    if not cursor.fetchone():
        return {"status": "error", "message": "Email not registered"}

    otp = str(random.randint(100000, 999999))
    session['reset_email'] = email
    session['otp']         = otp

    try:
        msg        = Message('OTP Verification', sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body   = f"Your OTP is: {otp}"
        mail.send(msg)
    except Exception as e:
        print("OTP email failed:", e)
        return {"status": "error", "message": "Failed to send OTP email. Check mail config."}

    return {"status": "success", "message": "OTP sent"}


@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data     = request.get_json()
    user_otp = data.get('otp')

    if user_otp == session.get('otp'):
        session['otp_verified'] = True
        return {"status": "success", "message": "OTP verified"}
    return {"status": "error", "message": "Invalid OTP"}


@app.route('/reset-password', methods=['POST'])
def reset_password():
    if not session.get('otp_verified'):
        return {"status": "error", "message": "Unauthorized"}

    data     = request.get_json()
    password = data.get('password')
    confirm  = data.get('confirm')

    if password != confirm:
        return {"status": "error", "message": "Passwords do not match"}

    hashed_password = generate_password_hash(password)
    email           = session.get('reset_email')

    conn, cursor = get_db_connection()
    cursor.execute("UPDATE user SET password=%s WHERE email=%s", (hashed_password, email))
    conn.commit()
    session.clear()

    return {"status": "success", "message": "Password reset successful"}


# ==========================================
# LOGOUT
# ==========================================
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been securely logged out.", "success")
    return redirect(url_for('signup'))


# ==========================================
# RUN SERVER
# ==========================================
if __name__ == "__main__":
    app.run(debug=True, port=5000)