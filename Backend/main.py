from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from email_service import send_swm_email, get_burn_rate_template, get_goal_completed_template
import mysql.connector
import random
import math
from datetime import datetime, timedelta

import razorpay
import os


# test key
RAZORPAY_KEY_ID = "rzp_test_SRa3Cn60azMF5E"
RAZORPAY_KEY_SECRET = "dobJbw8U5fBTv5D6kRwWHk6E"
client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))



# Get the base directory (where main.py is)
base_dir = os.path.dirname(os.path.abspath(__file__))



# Get the base directory of your project
base_dir = os.path.dirname(os.path.abspath(__file__))
# Change static_folder to point to the main Frontend folder
# Get the base directory of your project


app = Flask(__name__, 
            template_folder=os.path.join(base_dir, '../Frontend/landing'), # Looks here for HTML
            static_folder=os.path.join(base_dir, '../Frontend')            # Looks here for img, css, js
)# app = Flask(
#     __name__,
#     template_folder="../Frontend/landing",
#     static_folder="../Frontend"
# )
app.secret_key = "supersecretkey"

# --- DATABASE CONFIGURATION ---
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

def generate_wallet_id(cursor):
    """Helper to generate a unique 10-digit wallet ID."""
    while True:
        wallet_id = random.randint(1000000000, 9999999999)
        cursor.execute("SELECT wallet_id FROM wallet WHERE wallet_id=%s", (wallet_id,))
        if cursor.fetchone() is None:
            return wallet_id

# --- ROUTES ---

# ==========================================
# LANDING PAGE (SWM Homepage)
# ==========================================
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    # Tell Flask to look inside the 'landing' sub-folder
    return render_template('index.html')

# @app.route('/')
# def index():
#     return redirect(url_for('login'))

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
                if check_password_hash(user['password'], password):
                    session['user_id'] = user['id']
                    session['fullname'] = user['fullname']
                    flash("Login successful!", "success")
                    return redirect(url_for('dashboard'))
                else:
                    flash("Invalid Password!", "error")
            else:
                flash("Email not registered!", "error")
        finally:
            cursor.close()
            conn.close()

    return render_template("login.html")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    # Allow POST here to avoid 405 if a form accidentally posts to /signup.
    # The signup page is always simply rendered.
    return render_template("/signup.html")

import re

@app.route('/register', methods=['POST'])
def register():
    fullname = request.form['name']
    email = request.form['email']
    password = request.form['password']
    confirm_password = request.form['confirm']

    # 📧 Email Format Validation
    email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    if not re.match(email_pattern, email):
        flash("Invalid email format!", "error")
        return redirect(url_for('signup'))

    # 🔒 Password Match Check
    if password != confirm_password:
        flash("Passwords do not match!", "error")
        return redirect(url_for('signup'))

    # 🔒 Password Strength Validation
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
# DASHBOARD PAGE
# ==========================================
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn, cursor = get_db_connection()
    try:
        # 1. Get User
        cursor.execute("SELECT * FROM user WHERE id=%s", (session['user_id'],))
        user_data = cursor.fetchone()

        # 2. Get Main Wallet
        cursor.execute("SELECT * FROM wallet WHERE user_id=%s", (session['user_id'],))
        wallet_data = cursor.fetchone()

        # 3. Get Sub Wallets
        cursor.execute("SELECT * FROM sub_wallet WHERE user_id=%s", (session['user_id'],))
        sub_wallets_data = cursor.fetchall()

        # Calculate Total Balance
        total_balance = float(wallet_data['balance']) if wallet_data else 0.0
        for sw in sub_wallets_data:
            total_balance += float(sw['balance'])

        # Calculate Total Spent
        cursor.execute("SELECT SUM(amount) as total FROM transactions WHERE user_id=%s AND transaction_type='Payment'", (session['user_id'],))
        spent_result = cursor.fetchone()
        total_spent = float(spent_result['total'] or 0)

        # 4. Get Recent Transactions
        cursor.execute("SELECT * FROM transactions WHERE user_id=%s ORDER BY timestamp DESC LIMIT 5", (session['user_id'],))
        recent_transactions = cursor.fetchall()
        
        cursor.execute("SELECT * FROM transactions WHERE user_id=%s ORDER BY timestamp DESC", (session['user_id'],))
        all_transactions = cursor.fetchall()

        # ==========================================
        # 🚀 DASHBOARD QUICK INSIGHTS
        # ==========================================
        insights = {
            "largest_purchase": None,
            "transaction_count": 0,
            "most_frequent_wallet": None
        }

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
            insights["transaction_count"] = frequent_wallet['total_count']
            insights["most_frequent_wallet"] = frequent_wallet['wallet_name']

        # ==========================================
        # 🚀 HEALTH WARNINGS (BURN RATE) - UPGRADED
        # ==========================================
        envelope_health = []
        
        cursor.execute("SELECT name, balance FROM sub_wallet WHERE user_id=%s", (session['user_id'],))
        current_balances = {row['name']: float(row['balance']) for row in cursor.fetchall()}

        cursor.execute("""
            SELECT wallet_name, SUM(amount) as total_spent, MIN(timestamp) as first_date
            FROM transactions
            WHERE user_id=%s AND transaction_type='Payment' AND wallet_name != 'Main Wallet' AND wallet_name NOT LIKE 'Goal:%%'
            GROUP BY wallet_name
        """, (session['user_id'],))
        envelope_data = cursor.fetchall()

        for env in envelope_data:
            name = env['wallet_name']
            spent = float(env['total_spent'] or 0)
            
            days_active = 1 
            first_date = env['first_date']
            
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
                    if days_left <= 14:
                        envelope_health.append({
                            "name": name, "burn_rate": daily_burn, "days_left": days_left, "balance": bal, "status": "warning"
                        })
                    else:
                        envelope_health.append({
                            "name": name, "burn_rate": daily_burn, "days_left": days_left, "balance": bal, "status": "healthy"
                        })
                elif bal <= 0 and spent > 0:
                    envelope_health.append({
                        "name": name, "burn_rate": daily_burn, "days_left": 0, "balance": 0, "status": "critical"
                    })

        # Also grab sub-wallets that have money but NO spending yet
        for name, bal in current_balances.items():
            if not any(env.get('name') == name for env in envelope_health):
                if bal > 0:
                    envelope_health.append({
                        "name": name, "burn_rate": 0, "days_left": 999, "balance": bal, "status": "untouched"
                    })

    except Exception as e:
        print("Dashboard Error:", e)
        user_data, wallet_data, sub_wallets_data, total_balance, total_spent, recent_transactions, insights, envelope_health = {}, {}, [], 0, 0, [], {}, []
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    # NOTE: Changed health_warnings to envelope_health below!
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
# 1. CREATE SUB-WALLET (Now with History Logging)
# ==========================================
@app.route('/create_sub_wallet', methods=['POST'])
def create_sub_wallet():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    wallet_name = request.form.get('wallet_name')
    initial_amount = float(request.form.get('initial_amount', 0))

    conn, cursor = get_db_connection()
    try:
        # Check main wallet balance
        cursor.execute("SELECT balance FROM wallet WHERE user_id=%s", (session['user_id'],))
        main_wallet = cursor.fetchone()

        if not main_wallet or float(main_wallet['balance']) < initial_amount:
            flash("Insufficient funds in Main Wallet!", "error")
            return redirect(url_for('dashboard'))

        # Deduct from main wallet
        cursor.execute("UPDATE wallet SET balance = balance - %s WHERE user_id=%s", (initial_amount, session['user_id']))

        # Create sub wallet
        cursor.execute("INSERT INTO sub_wallet (user_id, name, balance) VALUES (%s, %s, %s)", (session['user_id'], wallet_name, initial_amount))

        # ✅ NEW: Log the allocation in Transaction History
        if initial_amount > 0:
            cursor.execute(
                "INSERT INTO transactions (user_id, amount, wallet_name, transaction_type) VALUES (%s, %s, %s, %s)",
                (session['user_id'], initial_amount, wallet_name, 'Allocation')
            )

        conn.commit()
        flash(f"Sub-wallet '{wallet_name}' created with ₹{initial_amount}!", "success")

    except Exception as e:
        print("Error creating sub-wallet:", e)
        flash("Failed to create sub-wallet.", "error")
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return redirect(url_for('dashboard'))


# ==========================================
# 2. ADD FUNDS TO SUB-WALLET (Now with History Logging)
# ==========================================
@app.route('/add_funds/<int:sub_id>', methods=['POST'])
def add_funds(sub_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    amount = float(request.form.get('amount', 0))

    conn, cursor = get_db_connection()
    try:
        # Check main wallet balance
        cursor.execute("SELECT balance FROM wallet WHERE user_id=%s", (session['user_id'],))
        main_wallet = cursor.fetchone()

        if not main_wallet or float(main_wallet['balance']) < amount:
            flash("Insufficient funds in Main Wallet!", "error")
            return redirect(url_for('dashboard'))

        # Get Sub-wallet name for the transaction log
        cursor.execute("SELECT name FROM sub_wallet WHERE id=%s AND user_id=%s", (sub_id, session['user_id']))
        sub_wallet = cursor.fetchone()
        
        if not sub_wallet:
            flash("Sub-wallet not found!", "error")
            return redirect(url_for('dashboard'))
        
        sub_name = sub_wallet['name']

        # Transfer the money
        cursor.execute("UPDATE wallet SET balance = balance - %s WHERE user_id=%s", (amount, session['user_id']))
        cursor.execute("UPDATE sub_wallet SET balance = balance + %s WHERE id=%s AND user_id=%s", (amount, sub_id, session['user_id']))

        # ✅ NEW: Log the addition in Transaction History
        cursor.execute(
            "INSERT INTO transactions (user_id, amount, wallet_name, transaction_type) VALUES (%s, %s, %s, %s)",
            (session['user_id'], amount, sub_name, 'Allocation')
        )

        conn.commit()
        flash(f"Added ₹{amount} to {sub_name}!", "success")

    except Exception as e:
        print("Error adding funds:", e)
        flash("Failed to transfer funds.", "error")
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return redirect(url_for('dashboard'))


# ==========================================
# 3. DELETE/DISCARD SUB-WALLET (Now with History Logging)
# ==========================================
@app.route('/delete_sub_wallet/<int:sub_id>', methods=['POST'])
def delete_sub_wallet(sub_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn, cursor = get_db_connection()
    try:
        # Get sub-wallet balance and name before deleting
        cursor.execute("SELECT balance, name FROM sub_wallet WHERE id=%s AND user_id=%s", (sub_id, session['user_id']))
        sub_wallet = cursor.fetchone()

        if sub_wallet:
            refund_amount = float(sub_wallet['balance'])
            sub_name = sub_wallet['name']

            # Add balance back to main wallet
            cursor.execute("UPDATE wallet SET balance = balance + %s WHERE user_id=%s", (refund_amount, session['user_id']))

            # Delete the sub-wallet
            cursor.execute("DELETE FROM sub_wallet WHERE id=%s", (sub_id,))

            # ✅ NEW: Log the refund in Transaction History
            if refund_amount > 0:
                cursor.execute(
                    "INSERT INTO transactions (user_id, amount, wallet_name, transaction_type) VALUES (%s, %s, %s, %s)",
                    (session['user_id'], refund_amount, f"Main Wallet (from {sub_name})", 'Refund')
                )

            conn.commit()
            flash(f"Discarded '{sub_name}'. ₹{refund_amount} returned to Main Wallet.", "success")
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
# PART 1: INITIATE RAZORPAY ORDER
# ==========================================
@app.route('/create_order', methods=['POST'])
def create_order():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    amount = float(request.form.get('amount', 0))
    wallet_source = request.form.get('wallet_source')

    if amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400

    # Razorpay requires the amount in Paise (Multiply by 100)
    data = {
        "amount": int(amount * 100),
        "currency": "INR",
        "payment_capture": "1"
    }
    
    # Create the order in Razorpay
    order = client.order.create(data=data)

    # Send order details back to HTML so the Razorpay popup can open
    return jsonify({
        "order_id": order['id'],
        "amount": order['amount'],
        "key": RAZORPAY_KEY_ID,
        "wallet_source": wallet_source
    })

# ==========================================
# PART 2: VERIFY & DEDUCT (Your exact DB logic!)
# ==========================================
# ==========================================
# PROCESS PAYMENT & ROUND-UP SAVINGS
# ==========================================
# ==========================================
# PROCESS PAYMENT & ROUND-UP SAVINGS
# ==========================================
@app.route('/verify_payment', methods=['POST'])
def verify_payment():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    amount_spent = float(request.form.get('amount', 0))
    wallet_source = request.form.get('wallet_source', 'main')

    conn, cursor = get_db_connection()
    try:
        # --- SCENARIO 1: PAYING FROM MAIN WALLET (Applies Round-Up) ---
        if wallet_source == 'main':
            # 1. Deduct the exact payment from Main Wallet
            cursor.execute("UPDATE wallet SET balance = balance - %s WHERE user_id=%s", (amount_spent, session['user_id']))
            
            # 2. Log the normal payment expense (REMOVED 'description')
            cursor.execute("""
                INSERT INTO transactions (user_id, wallet_name, transaction_type, amount) 
                VALUES (%s, %s, %s, %s)
            """, (session['user_id'], 'Main Wallet', 'Payment', amount_spent))

            # ==========================================
            # 🚀 THE ROUND-UP MAGIC LOGIC
            # ==========================================
            # Calculate next hundred (e.g., spent 240 -> ceil(2.4) * 100 = 300)
            next_hundred = math.ceil(amount_spent / 100.0) * 100
            spare_change = next_hundred - amount_spent

            if spare_change > 0:
                # Find their Priority 1 Goal (or the first goal they created)
                cursor.execute("SELECT id, name FROM savings_goals WHERE user_id=%s ORDER BY is_priority DESC, id ASC LIMIT 1", (session['user_id'],))
                priority_goal = cursor.fetchone()

                if priority_goal:
                    # Deduct the spare change from Main Wallet
                    cursor.execute("UPDATE wallet SET balance = balance - %s WHERE user_id=%s", (spare_change, session['user_id']))
                    
                   # Add it to the Priority Goal!
                    cursor.execute("UPDATE savings_goals SET current_balance = current_balance + %s WHERE id=%s", (spare_change, priority_goal['id']))
                    
                    # Log the auto-transfer with the Goal's name!
                    goal_label = f"Goal: {priority_goal['name']}"
                    cursor.execute("""
                        INSERT INTO transactions (user_id, wallet_name, transaction_type, amount) 
                        VALUES (%s, %s, %s, %s)
                    """, (session['user_id'], goal_label, 'Transfer', spare_change))                    

                    # ==========================================
                    # 📩 EMAIL CHECK: DID WE JUST FINISH THE GOAL?
                    # ==========================================
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
                        send_swm_email(to_email=user_info['email'], subject=f"Goal Completed: {updated_goal['name']}! 🎉", html_content=html_body)
                        flash(f"Payment successful! ₹{spare_change} automatically saved to '{priority_goal['name']}'.", "success")
                    else:
                        flash("Payment successful!", "success")
            else:
                flash("Payment successful! (Exact 100s, no round-up).", "success")

        # --- SCENARIO 2: PAYING FROM A SUB-WALLET (No Round-Up) ---
        else:
            sub_id = wallet_source.split('_')[1]
            cursor.execute("UPDATE sub_wallet SET balance = balance - %s WHERE id=%s AND user_id=%s", (amount_spent, sub_id, session['user_id']))
            
            cursor.execute("SELECT name FROM sub_wallet WHERE id=%s", (sub_id,))
            sub_name = cursor.fetchone()['name']
            
          # Log the normal payment expense (REMOVED 'description')
            cursor.execute("""
                INSERT INTO transactions (user_id, wallet_name, transaction_type, amount) 
                VALUES (%s, %s, %s, %s)
            """, (session['user_id'], sub_name, 'Payment', amount_spent))
            
            # ==========================================
            # 📩 EMAIL CHECK: IS THIS ENVELOPE BURNING TOO FAST?
            # ==========================================
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
                spent = float(stats['total_spent'])
                first_date = stats['first_date']
                days_active = 1
                
                if isinstance(first_date, str):
                    try: first_date = datetime.strptime(str(first_date).split('.')[0], '%Y-%m-%d %H:%M:%S')
                    except: pass
                if isinstance(first_date, datetime):
                    delta = (datetime.now() - first_date).days
                    if delta > 0: days_active = delta
                
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
                        send_swm_email(to_email=user_info['email'], subject=f"⚠️ High Spend Alert: {sub_name}", html_content=html_body)

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
# PART 3: INITIATE "ADD FUNDS" ORDER
# ==========================================
@app.route('/create_add_funds_order', methods=['POST'])
def create_add_funds_order():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    amount = float(request.form.get('amount', 0))

    if amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400

    # Razorpay requires the amount in Paise
    data = {
        "amount": int(amount * 100),
        "currency": "INR",
        "payment_capture": "1"
    }
    
    order = client.order.create(data=data)

    return jsonify({
        "order_id": order['id'],
        "amount": order['amount'],
        "key": RAZORPAY_KEY_ID
    })

# ==========================================
# PART 4: VERIFY & ADD MONEY TO DATABASE
# ==========================================
@app.route('/verify_add_funds', methods=['POST'])
def verify_add_funds():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    payment_id = request.form.get('razorpay_payment_id')
    order_id = request.form.get('razorpay_order_id')
    signature = request.form.get('razorpay_signature')
    amount = float(request.form.get('amount', 0))

    try:
        # 1. VERIFY RAZORPAY SIGNATURE
        client.utility.verify_payment_signature({
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        })

        # 2. IF SUCCESSFUL, ADD MONEY TO MAIN WALLET
        conn, cursor = get_db_connection()

        # Update balance
        cursor.execute("UPDATE wallet SET balance = balance + %s WHERE user_id=%s", (amount, session['user_id']))

        # Insert transaction as a 'Deposit' (This will show up as Green/+ in your HTML!)
        cursor.execute(
            "INSERT INTO transactions (user_id, amount, wallet_name, transaction_type) VALUES (%s,%s,%s,%s)",
            (session['user_id'], amount, 'Main Wallet', 'Deposit')
        )
        conn.commit()
        flash(f"Successfully added ₹{amount} to Main Wallet!", "success")

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
# SET MONTHLY BUDGET
# ==========================================
@app.route('/set_budget', methods=['POST'])
def set_budget():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    new_budget = request.form.get('new_budget', type=float)
    
    if new_budget and new_budget > 0:
        # Save it to their current session
        session['monthly_budget'] = new_budget
        flash(f"Monthly budget updated to ₹{new_budget:,.0f}!", "success")
    else:
        flash("Invalid budget amount.", "error")
        
    return redirect(url_for('dashboard'))


# ==========================================
# 1. WALLETS & GOALS PAGE ROUTE
# ==========================================
# ==========================================
# 1. WALLETS & GOALS PAGE ROUTE
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

        # Fetch the goals
       # Change this line inside def wallets():
        cursor.execute("SELECT * FROM savings_goals WHERE user_id=%s ORDER BY is_priority DESC, id ASC", (session['user_id'],))
        goals_data = cursor.fetchall()

        # BULLETPROOF MATH: Safely handle None or missing values
        for goal in goals_data:
            # Safely convert to float, defaulting to 0.0 if something is weird
            target = float(goal.get('target_amount') or 0.0)
            current = float(goal.get('current_balance') or 0.0)
            
            if target > 0:
                percent = (current / target) * 100
                goal['percent'] = min(int(percent), 100) # Cap at 100%
            else:
                goal['percent'] = 0

    except Exception as e:
        print("CRITICAL ERROR ON WALLETS PAGE:", e) # This will print in red in your terminal if it fails!
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
# 2. CREATE SAVINGS GOAL ROUTE
# ==========================================
@app.route('/create_goal', methods=['POST'])
def create_goal():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    goal_name = request.form.get('goal_name')
    target_amount = float(request.form.get('target_amount', 0))
    goal_icon = request.form.get('goal_icon', 'stars')

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
    if 'user_id' not in session: return redirect(url_for('login'))
    conn, cursor = get_db_connection()
    try:
        # Check if goal exists and has money in it
        cursor.execute("SELECT current_balance, name FROM savings_goals WHERE id=%s AND user_id=%s", (goal_id, session['user_id']))
        goal = cursor.fetchone()
        
        if goal:
            # If there is money in the goal, refund it to the Main Wallet!
            if float(goal.get('current_balance') or 0) > 0:
                cursor.execute("UPDATE wallet SET balance = balance + %s WHERE user_id=%s", (goal['current_balance'], session['user_id']))
            
            # Delete the goal
            cursor.execute("DELETE FROM savings_goals WHERE id=%s", (goal_id,))
            conn.commit()
            flash(f"Goal '{goal['name']}' discarded. Funds refunded to Main Wallet.", "success")
    except Exception as e:
        print("Error deleting goal:", e)
        flash("Could not delete goal.", "error")
    finally:
        if 'cursor' in locals(): cursor.close(); conn.close()
    return redirect(url_for('wallets'))

# ==========================================
# MAKE GOAL PRIORITY 1
# ==========================================
@app.route('/make_priority/<int:goal_id>', methods=['POST'])
def make_priority(goal_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    conn, cursor = get_db_connection()
    try:
        # Step 1: Remove priority from all goals for this user
        cursor.execute("UPDATE savings_goals SET is_priority = FALSE WHERE user_id=%s", (session['user_id'],))
        # Step 2: Set the selected goal as the new priority
        cursor.execute("UPDATE savings_goals SET is_priority = TRUE WHERE id=%s AND user_id=%s", (goal_id, session['user_id']))
        conn.commit()
        flash("Priority updated successfully!", "success")
    except Exception as e:
        print("Error updating priority:", e)
    finally:
        if 'cursor' in locals(): cursor.close(); conn.close()
    return redirect(url_for('wallets'))


# ==========================================
# DISABLE SAVINGS FEATURE (KILL SWITCH)
# ==========================================# ==========================================
# DISABLE SAVINGS FEATURE (KILL SWITCH)
# ==========================================
@app.route('/disable_savings', methods=['POST'])
def disable_savings():
    if 'user_id' not in session: 
        return redirect(url_for('login'))
        
    conn, cursor = get_db_connection()
    try:
        # 1. Calculate how much total money is stored in all savings goals
        cursor.execute("SELECT SUM(current_balance) as total_saved FROM savings_goals WHERE user_id=%s", (session['user_id'],))
        result = cursor.fetchone()
        total_saved = float(result['total_saved'] or 0)
        
        # 2. If there is money, instantly refund it to the Main Wallet AND log it
        if total_saved > 0:
            # Add to Main Wallet
            cursor.execute("UPDATE wallet SET balance = balance + %s WHERE user_id=%s", (total_saved, session['user_id']))
            
            # LOG THE TRANSACTION IN HISTORY
            cursor.execute("""
                INSERT INTO transactions (user_id, wallet_name, transaction_type, amount) 
                VALUES (%s, %s, %s, %s)
            """, (session['user_id'], 'Savings Refund', 'Transfer', total_saved))
            
        # 3. Delete all goals to completely "disable" the feature
        cursor.execute("DELETE FROM savings_goals WHERE user_id=%s", (session['user_id'],))
        conn.commit()
        
        flash(f"Savings Feature Disabled. ₹{total_saved} refunded to Main Wallet.", "success")
    except Exception as e:
        print("Error disabling savings:", e)
        conn.rollback() # Failsafe
        flash("Failed to disable savings.", "error")
    finally:
        if 'cursor' in locals(): 
            cursor.close()
            conn.close()
            
    return redirect(url_for('wallets'))




    
 # ==========================================
# ANALYSIS & CHARTS PAGE
# ==========================================
@app.route('/analysis')
def analysis():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn, cursor = get_db_connection()
    
    try:
        days_filter = request.args.get('days', 30, type=int)
        cutoff_date = (datetime.now() - timedelta(days=days_filter)).strftime('%Y-%m-%d 00:00:00')
        
        # 1. Get User info
        cursor.execute("SELECT fullname FROM user WHERE id=%s", (session['user_id'],))
        user_data = cursor.fetchone()

        # 2. Get Balances for Asset Allocation Chart
        cursor.execute("SELECT balance FROM wallet WHERE user_id=%s", (session['user_id'],))
        main_wallet = cursor.fetchone()
        main_bal = float(main_wallet['balance'] if main_wallet else 0)

        cursor.execute("SELECT SUM(balance) as total FROM sub_wallet WHERE user_id=%s", (session['user_id'],))
        sub_wallet_total = float(cursor.fetchone()['total'] or 0)

        cursor.execute("SELECT SUM(current_balance) as total FROM savings_goals WHERE user_id=%s", (session['user_id'],))
        savings_total = float(cursor.fetchone()['total'] or 0)

        total_net_worth = main_bal + sub_wallet_total + savings_total

        # 3. Get Expense Breakdown 
        cursor.execute("""
        SELECT wallet_name, SUM(amount) as total_spent 
        FROM transactions 
        WHERE user_id=%s 
        AND transaction_type='Payment'
        AND (wallet_name = 'Main Wallet' OR wallet_name IN (SELECT name FROM sub_wallet WHERE user_id=%s))
        AND timestamp >= %s
        GROUP BY wallet_name
        """, (session['user_id'], session['user_id'], cutoff_date))
        expenses = cursor.fetchall()
        
        expense_labels = [exp['wallet_name'] for exp in expenses] if expenses else ["No Data"]
        expense_values = [float(exp['total_spent']) for exp in expenses] if expenses else [0]
        total_spent = sum(expense_values)

        # 4. Get Total Auto-Saved
        cursor.execute("""
            SELECT SUM(amount) as total_saved 
            FROM transactions 
            WHERE user_id=%s 
              AND transaction_type='Transfer' 
              AND wallet_name LIKE 'Goal:%%'
              AND timestamp >= %s
        """, (session['user_id'], cutoff_date))
        auto_saved_data = cursor.fetchone()
        auto_saved = float(auto_saved_data['total_saved'] if auto_saved_data and auto_saved_data['total_saved'] else 0)
       # ==========================================
        # 5. 🚀 BULLETPROOF ENVELOPE BURN RATE
        # ==========================================
        envelope_health = []
        
        cursor.execute("SELECT name, balance FROM sub_wallet WHERE user_id=%s", (session['user_id'],))
        current_balances = {row['name']: float(row['balance']) for row in cursor.fetchall()}

        cursor.execute("""
            SELECT wallet_name, SUM(amount) as total_spent, MIN(timestamp) as first_date
            FROM transactions
            WHERE user_id=%s AND transaction_type='Payment' AND wallet_name != 'Main Wallet' AND wallet_name NOT LIKE 'Goal:%%'
            GROUP BY wallet_name
        """, (session['user_id'],))
        envelope_data = cursor.fetchall()

        for env in envelope_data:
            name = env['wallet_name']
            spent = float(env['total_spent'] or 0)
            
            days_active = 1 
            first_date = env['first_date']
            
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
                    if days_left <= 14:
                        envelope_health.append({
                            "name": name, "burn_rate": daily_burn, "days_left": days_left, "balance": bal, "status": "warning"
                        })
                    else:
                        envelope_health.append({
                            "name": name, "burn_rate": daily_burn, "days_left": days_left, "balance": bal, "status": "healthy"
                        })
                elif bal <= 0 and spent > 0:
                    envelope_health.append({
                        "name": name, "burn_rate": daily_burn, "days_left": 0, "balance": 0, "status": "critical"
                    })

        # Also grab sub-wallets that have money but NO spending yet
        for name, bal in current_balances.items():
            if not any(env.get('name') == name for env in envelope_health):
                if bal > 0:
                    envelope_health.append({
                        "name": name, "burn_rate": 0, "days_left": 999, "balance": bal, "status": "untouched"
                    })
                    
        # ==========================================
        # 6. PACKAGE CHART DATA (This is what got deleted!)
        # ==========================================
        chart_data = {
            "assets_labels": ["Main Wallet", "Sub-Wallets", "Savings Goals"],
            "assets_values": [main_bal, sub_wallet_total, savings_total],
            "expense_labels": expense_labels,
            "expense_values": expense_values
        }

    except Exception as e:
        print("Analysis Error:", e)
        user_data = {}
        total_net_worth = 0
        total_spent = 0
        auto_saved = 0
        chart_data = {}
        envelope_health = []
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
                          envelope_health=envelope_health)
    
    
    
# ==========================================
# TRANSACTION HISTORY PAGE
# ==========================================
@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn, cursor = get_db_connection()
    try:
        cursor.execute("SELECT fullname FROM user WHERE id=%s", (session['user_id'],))
        user_data = cursor.fetchone()

        # Get ALL transactions, not just the top 5
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
# USER PROFILE PAGE
# ==========================================
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn, cursor = get_db_connection()
    try:
        # Get full user details (adjust column names like 'email' if your DB uses different names)
        cursor.execute("SELECT * FROM user WHERE id=%s", (session['user_id'],))
        user_data = cursor.fetchone()
        
        # Count total transactions for a fun profile stat
        cursor.execute("SELECT COUNT(*) as tx_count FROM transactions WHERE user_id=%s", (session['user_id'],))
        tx_data = cursor.fetchone()
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
# UPDATE PROFILE ROUTE
# ==========================================
@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    new_name = request.form.get('fullname')
    new_email = request.form.get('email')
    
    conn, cursor = get_db_connection()
    try:
        # Update the user's name and email in the database
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
            
    # Refresh the page to show the new details!
    return redirect(url_for('profile'))
        
        
        
        
        
@app.route('/pay_goal/<int:goal_id>', methods=['POST'])
def pay_goal(goal_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Get the amount the user actually spent from the new modal!
    amount_spent = float(request.form.get('amount_spent', 0))

    conn, cursor = get_db_connection()
    try:
        cursor.execute("SELECT * FROM savings_goals WHERE id=%s AND user_id=%s", (goal_id, session['user_id']))
        goal = cursor.fetchone()

        current_balance = float(goal['current_balance'])

        # Safety Check: Did they try to spend more than they saved?
        if amount_spent > current_balance:
            flash("You cannot spend more than the total saved in this goal!", "error")
            return redirect(url_for('wallets'))

        # 🔥 THE MATH LOGIC 🔥
        leftover_change = current_balance - amount_spent

        # 1. Log the actual expense transaction (e.g., spending ₹88)
        cursor.execute("""
            INSERT INTO transactions (user_id, wallet_name, transaction_type, amount) 
            VALUES (%s, %s, %s, %s)
        """, (session['user_id'], f"Purchase: {goal['name']}", 'Payment', amount_spent))

        # 2. Handle the leftover change (e.g., the extra ₹12)
        if leftover_change > 0:
            # Look for the next goal
            cursor.execute("""
                SELECT id, name FROM savings_goals 
                WHERE user_id=%s AND id != %s 
                ORDER BY is_priority DESC, id ASC LIMIT 1
            """, (session['user_id'], goal_id))
            next_goal = cursor.fetchone()

            if next_goal:
                cursor.execute("UPDATE savings_goals SET current_balance = current_balance + %s WHERE id=%s", (leftover_change, next_goal['id']))
                flash(f"Purchase successful! The leftover ₹{leftover_change:.2f} was rolled over to '{next_goal['name']}'.", "success")
            else:
                cursor.execute("UPDATE wallet SET balance = balance + %s WHERE user_id=%s", (leftover_change, session['user_id']))
                flash(f"Purchase successful! No other goals found, so your extra ₹{leftover_change:.2f} was safely returned to your Main Wallet.", "success")
        else:
            flash(f"Purchase successful! You spent the exact amount saved.", "success")

        # 3. Delete the completed goal card forever
        cursor.execute("DELETE FROM savings_goals WHERE id=%s", (goal_id,))
        
        conn.commit()
    except Exception as e:
        print("Goal Payment Error:", e)
        conn.rollback()
        flash("Something went wrong while processing your goal payment.", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('wallets'))


    
    
@app.route('/verify_goal_payment', methods=['POST'])
def verify_goal_payment():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    payment_id = request.form.get('razorpay_payment_id')
    order_id = request.form.get('razorpay_order_id')
    signature = request.form.get('razorpay_signature')
    
    goal_id = request.form.get('goal_id')
    amount_spent = float(request.form.get('amount_spent', 0))

    try:
        # 1. VERIFY THE RAZORPAY SIGNATURE (Security First!)
        client.utility.verify_payment_signature({
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        })

        # 2. IF VERIFIED, DO THE ROLLOVER MATH
        conn, cursor = get_db_connection()
        
        cursor.execute("SELECT * FROM savings_goals WHERE id=%s AND user_id=%s", (goal_id, session['user_id']))
        goal = cursor.fetchone()

        if not goal:
            flash("Goal not found.", "error")
            return redirect(url_for('wallets'))

        current_balance = float(goal['current_balance'])
        leftover_change = current_balance - amount_spent

        # Log the actual payment out
        cursor.execute("""
            INSERT INTO transactions (user_id, wallet_name, transaction_type, amount) 
            VALUES (%s, %s, %s, %s)
        """, (session['user_id'], f"Goal Purchase: {goal['name']}", 'Payment', amount_spent))

        # Handle the Leftover Change
        if leftover_change > 0:
            # Find the next priority goal
            cursor.execute("""
                SELECT id, name FROM savings_goals 
                WHERE user_id=%s AND id != %s 
                ORDER BY is_priority DESC, id ASC LIMIT 1
            """, (session['user_id'], goal_id))
            next_goal = cursor.fetchone()

            if next_goal:
                cursor.execute("UPDATE savings_goals SET current_balance = current_balance + %s WHERE id=%s", (leftover_change, next_goal['id']))
                flash(f"Payment successful! You had ₹{leftover_change:.2f} leftover, which was auto-transferred to '{next_goal['name']}'.", "success")
            else:
                cursor.execute("UPDATE wallet SET balance = balance + %s WHERE user_id=%s", (leftover_change, session['user_id']))
                flash(f"Payment successful! You had ₹{leftover_change:.2f} leftover, which was returned to your Main Wallet.", "success")
        else:
            flash(f"Payment successful! You spent the exact amount saved.", "success")

        # Delete the completed goal
        cursor.execute("DELETE FROM savings_goals WHERE id=%s", (goal_id,))
        
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


        
        
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)