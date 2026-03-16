from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
import mysql.connector
import random

import razorpay


# test key
RAZORPAY_KEY_ID = "rzp_test_SRa3Cn60azMF5E"
RAZORPAY_KEY_SECRET = "dobJbw8U5fBTv5D6kRwWHk6E"
client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))


app = Flask(
    __name__,
    template_folder="../Frontend/landing",
    static_folder="../Frontend"
)
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
    return render_template("signup.html")

@app.route('/register', methods=['POST'])
def register():
    fullname = request.form['name']
    email = request.form['email']
    password = request.form['password']
    confirm_password = request.form['confirm']

    if password != confirm_password:
        flash("Passwords do not match!", "error")
        return redirect(url_for('signup'))

    hashed_password = generate_password_hash(password)
    
    conn, cursor = get_db_connection()
    try:
        # Check if email already exists
        cursor.execute("SELECT * FROM user WHERE email=%s", (email,))
        if cursor.fetchone():
            flash("Email already registered!", "error")
            return redirect(url_for('signup'))

        # Insert new user (Note: using execute with a standard tuple, not dictionary)
        cursor = conn.cursor() # Get a standard cursor to access lastrowid easily
        cursor.execute(
            "INSERT INTO user (fullname, email, password) VALUES (%s, %s, %s)",
            (fullname, email, hashed_password)
        )
        user_id = cursor.lastrowid

        # Generate wallet id and create wallet
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
        
        
        
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash("Please log in to access the dashboard.", "error")
        return redirect(url_for('login'))
    
    conn, cursor = get_db_connection()

    try:
        cursor.execute("SELECT * FROM user WHERE id=%s", (session['user_id'],))
        user_data = cursor.fetchone()

        cursor.execute("SELECT * FROM wallet WHERE user_id=%s", (session['user_id'],))
        wallet_data = cursor.fetchone()

        cursor.execute(
            "SELECT * FROM sub_wallet WHERE user_id=%s ORDER BY created_at DESC",
            (session['user_id'],)
        )
        sub_wallets_data = cursor.fetchall()

        # ---- wealth calculation ----
        main_balance = float(wallet_data['balance'])
        sub_total = sum(float(sw['balance']) for sw in sub_wallets_data)
        total_wealth = main_balance + sub_total

        for sw in sub_wallets_data:
            sw['percent'] = round((float(sw['balance']) / total_wealth) * 100) if total_wealth > 0 else 0

        main_percent = round((main_balance / total_wealth) * 100) if total_wealth > 0 else 100

        # ---- recent transactions ----
        
        # Fetch optimized transaction history
      # 1. Fetch ALL transactions (No weird SQL formatting)
        cursor.execute("""
            SELECT amount, wallet_name, transaction_type, timestamp
            FROM transactions 
            WHERE user_id = %s 
            ORDER BY timestamp DESC
        """, (session['user_id'],))
        
        all_tx = cursor.fetchall()

        # 2. Safely format the time using Python
        for tx in all_tx:
            # Check if it's a valid timestamp object
            if hasattr(tx['timestamp'], 'strftime'):
                tx['time_only'] = tx['timestamp'].strftime('%I:%M %p')  # e.g., 10:45 AM
                tx['date_only'] = tx['timestamp'].strftime('%b %d, %Y') # e.g., Mar 16, 2026
            else:
                tx['time_only'] = ""
                tx['date_only'] = ""

        # 3. Split the data: Top 5 for the dashboard, everything else for "View All"
        recent_transactions = all_tx[:5]
        
        # --- CALCULATIONS FOR FOOTER STATS ---
        # 1. Total Income (Sum of all Deposits)
        cursor.execute("SELECT SUM(amount) as total_income FROM transactions WHERE user_id=%s AND transaction_type='Deposit'", (session['user_id'],))
        inc_row = cursor.fetchone()
        income = float(inc_row['total_income']) if inc_row and inc_row['total_income'] else 0.0

        # 2. Total Expenses (Sum of all Payments)
        cursor.execute("SELECT SUM(amount) as total_expense FROM transactions WHERE user_id=%s AND transaction_type='Payment'", (session['user_id'],))
        exp_row = cursor.fetchone()
        expense = float(exp_row['total_expense']) if exp_row and exp_row['total_expense'] else 0.0

        # 3. Total Transactions Count (Replacing Tax)
        cursor.execute("SELECT COUNT(*) as tx_count FROM transactions WHERE user_id=%s", (session['user_id'],))
        tx_row = cursor.fetchone()
        tx_count = int(tx_row['tx_count']) if tx_row and tx_row['tx_count'] else 0
        
        
        # --- DYNAMIC MONTHLY BUDGET LOGIC ---
        # 1. Set your monthly limit here (e.g., ₹10,000 for the portfolio)
        # Check if the user set a custom budget, otherwise default to 10000
        MONTHLY_LIMIT = float(session.get('monthly_budget', 10000.0))
        
        # 2. Use the total expense we calculated earlier
        current_month_expense = expense 
        
        # 3. Calculate percentages
        if MONTHLY_LIMIT > 0:
            budget_percent = int((current_month_expense / MONTHLY_LIMIT) * 100)
        else:
            budget_percent = 0
            
        # Cap the circle at 100% so it doesn't break the UI if they overspend
        ui_percent = budget_percent if budget_percent <= 100 else 100
            
        budget_remaining = MONTHLY_LIMIT - current_month_expense
        if budget_remaining < 0:
            budget_remaining = 0
            
        # 4. SVG Circle Math (Total circumference of your circle is 471)
        circle_offset = 471 - (471 * (ui_percent / 100))
        # ------------------------------------


                              
        
        
        return render_template("dash2.html", 
                               user=user_data, 
                               wallet=wallet_data, 
                               sub_wallets=sub_wallets_data, 
                               main_percent=main_percent,
                               total_wealth=total_wealth,
                               transactions=recent_transactions,  # Only 5 items
                               all_transactions=all_tx,  # Every single item!
                               income=income,          # NEW
                               expense=expense,        # NEW
                               tx_count=tx_count,
                                monthly_limit=MONTHLY_LIMIT,             # NEW
                               current_month_expense=current_month_expense, # NEW
                               budget_percent=budget_percent,           # NEW
                               budget_remaining=budget_remaining,       # NEW
                               circle_offset=circle_offset)             # NEW
        

    except mysql.connector.Error as err:
        print("Database Error:", err)
        flash("Error loading dashboard data.", "error")
        return redirect(url_for('login'))

    finally:
        cursor.close()
        conn.close()
        
        
        
              
        
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
@app.route('/verify_payment', methods=['POST'])
def verify_payment():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Get Razorpay data sent by the frontend
    payment_id = request.form.get('razorpay_payment_id')
    order_id = request.form.get('razorpay_order_id')
    signature = request.form.get('razorpay_signature')
    
    # Get the original amount and wallet choice
    amount = float(request.form.get('amount', 0))
    wallet_source = request.form.get('wallet_source')

    try:
        # 1. VERIFY RAZORPAY SIGNATURE (Security Check)
        client.utility.verify_payment_signature({
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        })

        # 2. IF SUCCESSFUL, RUN YOUR EXACT DATABASE MATH
        source_name = ""
        conn, cursor = get_db_connection()

        if wallet_source == 'main':
            cursor.execute("SELECT balance FROM wallet WHERE user_id=%s", (session['user_id'],))
            row = cursor.fetchone()
            if not row or float(row['balance']) < amount:
                flash("Insufficient funds in Main Wallet!", "error")
                return redirect(url_for('dashboard'))
            cursor.execute("UPDATE wallet SET balance = balance - %s WHERE user_id=%s", (amount, session['user_id']))
            source_name = "Main Wallet"

        else:
            sub_id = int(wallet_source.split('_')[1])
            cursor.execute("SELECT balance, name FROM sub_wallet WHERE id=%s AND user_id=%s", (sub_id, session['user_id']))
            row = cursor.fetchone()
            if not row or float(row['balance']) < amount:
                flash("Insufficient funds in Sub Wallet!", "error")
                return redirect(url_for('dashboard'))
            cursor.execute("UPDATE sub_wallet SET balance = balance - %s WHERE id=%s", (amount, sub_id))
            source_name = row['name']

        # Insert transaction
        cursor.execute(
            "INSERT INTO transactions (user_id, amount, wallet_name, transaction_type) VALUES (%s,%s,%s,%s)",
            (session['user_id'], amount, source_name, 'Payment')
        )
        conn.commit()
        flash(f"Paid ₹{amount} from {source_name} via Razorpay!", "success")

    except razorpay.errors.SignatureVerificationError:
        flash("Payment verification failed! Money was not deducted.", "error")
    except Exception as e:
        print("Transaction Error:", e)
        flash("Transaction failed.", "error")
    finally:
        if 'cursor' in locals():
            cursor.close()
            conn.close()

    return redirect(url_for('dashboard'))

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


        
        
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)