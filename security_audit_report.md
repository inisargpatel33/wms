# Static Application Security Audit Report

Date: 2026-08-02
Project: WMS

## Scope reviewed

- Backend/main.py
- Backend/email_service.py
- Frontend/script.js
- Relevant frontend templates under Frontend/landing

## Executive summary

The application contains several serious security issues that should be treated as high priority. The most critical findings are a privilege escalation endpoint, hardcoded secrets, missing CSRF protection on state-changing requests, and a client-side DOM XSS issue. I did not find evidence of SQL injection, command injection, or path traversal in the reviewed code paths; the backend uses parameterized queries for database access.

## Findings

### 1. Privilege Escalation / Broken Access Control - Critical

- Location: [Backend/main.py](Backend/main.py) around the make_me_admin route
- Vulnerability Type: Broken Access Control / Privilege Escalation
- Exploit Scenario: Any authenticated user can invoke the /make_me_admin endpoint and self-promote to admin because the server trusts the current session and performs a direct role update without any additional authorization checks.
- Remediation:
  - Remove the self-service admin promotion route entirely.
  - If admin creation is required, implement a separate, restricted administrative workflow that only allows an existing super-admin to grant the role.
  - Re-check the user's role from the database on every privileged action instead of trusting session values alone.

Example secure pattern:

```python
@app.route('/make_me_admin')
def make_me_admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Only allow existing super-admins to promote others.
    conn, cursor = get_db_connection()
    try:
        cursor.execute("SELECT role FROM user WHERE id=%s", (session['user_id'],))
        user = cursor.fetchone()
        if not user or user['role'] != 'super_admin':
            flash("Forbidden", "error")
            return redirect(url_for('dashboard'))
    finally:
        cursor.close()
        conn.close()

    # Then perform a controlled promotion flow.
```

### 2. Hardcoded Secrets and Weak Secret Management - High

- Location: [Backend/main.py](Backend/main.py) and [Backend/email_service.py](Backend/email_service.py)
- Vulnerability Type: Hardcoded Credentials / Secret Management
- Exploit Scenario: An attacker who obtains the source code, a backup, or repository history can recover payment API credentials, email credentials, and Flask session secrets. This can lead to unauthorized access to payment services, email sending, and session tampering.
- Remediation:
  - Move secrets to environment variables or a secret manager.
  - Rotate all exposed credentials immediately.
  - Use a strong random secret for Flask session signing.

Secure example:

```python
import os
from dotenv import load_dotenv

load_dotenv()

RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET')
app.secret_key = os.environ['FLASK_SECRET_KEY']
app.config['MAIL_PASSWORD'] = os.environ['MAIL_PASSWORD']
```

### 3. Missing CSRF Protection on State-Changing Routes - High

- Location: [Backend/main.py](Backend/main.py) for POST handlers such as create_sub_wallet, delete_sub_wallet, toggle_user_status, set_global_alert, create_goal, delete_goal, disable_savings, and payment verification routes
- Vulnerability Type: Cross-Site Request Forgery (CSRF)
- Exploit Scenario: A malicious website can cause a logged-in victim to submit a form to an internal state-changing endpoint (for example, deleting a savings goal or creating a wallet transfer) because the app does not appear to implement CSRF tokens or validation.
- Remediation:
  - Enable CSRF protection in Flask using Flask-WTF or a similar library.
  - Require a CSRF token on every POST form and API request that changes server state.
  - Prefer SameSite cookie settings for session cookies.

Secure example:

```python
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect(app)
app.config['WTF_CSRF_TIME_LIMIT'] = None
```

### 4. Stored/Reflected DOM XSS via Unsafe HTML Injection - High

- Location: [Frontend/script.js](Frontend/script.js)
- Vulnerability Type: Cross-Site Scripting (XSS)
- Exploit Scenario: A user can enter a value such as `<img src=x onerror=alert(1)>` into the category name or emoji field. The script later inserts the value into innerHTML, causing the browser to execute attacker-controlled markup.
- Remediation:
  - Never use innerHTML with untrusted input.
  - Create elements programmatically and set textContent instead.
  - If markup is required, sanitize with a library such as DOMPurify before insertion.

Secure example:

```javascript
const name = categoryNameInput.value.trim();
const emoji = categoryEmojiInput.value.trim();

const left = document.createElement("div");
left.className = "left";
left.textContent = `${emoji} ${name}`;

accountDiv.appendChild(left);
```

### 5. Payment Amount Tampering / Broken Financial Integrity - High

- Location: [Backend/main.py](Backend/main.py) in the payment verification handlers
- Vulnerability Type: Insecure Business Logic / Payment Tampering
- Exploit Scenario: The server verifies the Razorpay signature but then trusts the amount supplied in the verify_payment request to deduct funds from the user's wallet. An attacker can potentially submit a different amount after a valid order/payment verification and cause the server to debit more than intended.
- Remediation:
  - Store the original order amount server-side when creating the order.
  - Verify that the amount submitted to /verify_payment or /verify_goal_payment matches the recorded order amount exactly.
  - Reject mismatches and log them for review.

Secure example:

```python
# When creating the order, persist the expected amount.
expected_amount = int(amount * 100)

# During verification, ensure the submitted amount matches the stored order amount.
if amount * 100 != expected_amount:
    flash("Payment amount mismatch", "error")
    return redirect(url_for('wallets'))
```

## Additional observations

- The application uses parameterized SQL queries in the reviewed code paths, so SQL injection does not appear to be present in the current backend implementation.
- I did not see evidence of command injection or path traversal in the reviewed code paths.

## Recommended remediation priority

1. Remove the self-promoting admin route and enforce server-side admin authorization.
2. Rotate and move all secrets out of source code immediately.
3. Add CSRF protection to all state-changing endpoints.
4. Replace unsafe DOM insertion in the frontend.
5. Harden payment verification to bind the amount to the original order.
