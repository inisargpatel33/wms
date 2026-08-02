
 🚀 Smart Wallet Management System (SWM)

**Expense Tracking and Budget Control Platform**

 ⚠️ The Big Problem

In today's fast-paced digital era, managing personal finances efficiently has become a critical challenge. Many individuals lack a structured system to track categorized expenses and set budget limits. This gap leads to frequent overspending, zero visibility into where money is disappearing, and ultimately, poor financial planning.

 💡 The Solution

The **Smart Wallet Management System (SWM)** is a robust web-based application designed to directly combat financial indiscipline. By allowing users to manage their income and expenses through highly customizable, categorized "sub-wallets," the system provides total visibility into daily spending.

SWM actively prevents overspending by allowing users to set hard monthly budget limits for each category and automatically generating reminders when those limits are breached. This project promotes financial discipline, improves expense monitoring, and delivers a user-friendly solution for personal wealth management.



✨ Core Functionality & Features

 👤 User Capabilities (Financial Control)

* **Categorized Sub-Wallets:** Users can divide their main balance into specific sub-wallets (e.g., Food, Travel, Shopping, Bills) for laser-focused tracking.


* **Intelligent Budgeting & Alerts:** Users can set strict monthly budget limits for each category. The system actively monitors spending and generates alert notifications when spending exceeds the set limits.


* **Detailed Reporting & Analytics:** Generates comprehensive monthly expense reports, summaries, and graphical charts for deep financial analysis.


* **Real-Time Email Notifications:** Integrates SMTP to send immediate email confirmations whenever money is deposited into the wallet.


* **Seamless Transactions:** Complete capabilities to safely add, update, and delete income and expense transactions.



🛡️ Admin Capabilities (System Monitoring)

* **Secure Monitoring Hub:** A dedicated Admin dashboard with secure login authentication to oversee platform activity.


* **Global Transaction Ledger:** Admins can view and monitor all user transactions across the system to ensure integrity.


* **Security & Access Control:** Admins possess the authority to instantly block or unblock user wallets to prevent fraud or handle suspicious activity.


🛠️ Technology Stack : Built utilizing Agile Development Methodology for iterative, high-quality deployment.

* **Frontend:** HTML, CSS, JavaScript, Bootstrap

* **Backend:** Python (Flask / Django)

* **Database:** MySQL

* **Email Infrastructure:** SMTP (Gmail SMTP / Flask-Mail) for rapid email delivery

(Note: Real-time bank API integrations, multi-currency support, and QR-based payments are out of scope for this version to prioritize core system stability).



⚙️ Getting Started (Local Development)

Follow these steps to clone the repository and run the SWM project on your local machine.

### 1. Prerequisites

Ensure you have the following installed:

* **Python 3.x**
* **MySQL Server** (via XAMPP, WAMP, or standalone)
* **Git**

### 2. Clone the Repository

Open your terminal and run:

git clone https://github.com/yourusername/swm.git
cd swm


### 3. Environment Setup & Dependencies

Create a virtual environment to keep dependencies isolated, then install the required packages:

# Create virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install requirements
pip install -r requirements.txt

### 4. Database Configuration

1. Open your MySQL client (e.g., phpMyAdmin or MySQL Workbench).
2. Create a new database named `swm`.


3. Import the provided SQL schema file (located in the repository) to generate the required tables.
4. Create a `.env` file in the root directory and update your database credentials and SMTP email configurations:

FLASK_SECRET_KEY=your_secure_secret_key
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password


### 5. Run the Application

Start the backend server:


python Backend/main.py

*The server will boot up (typically on port 5000). Open your browser and navigate to `[http://127.0.0.1:5000](http://127.0.0.1:5000)` to access the platform.*
