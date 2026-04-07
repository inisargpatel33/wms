import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------------------------
# CONFIGURATION
# Try to load from .env file if it exists, otherwise fall back to hardcoded
# ---------------------------------------------------------------------------
def _load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    config = {}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    config[key.strip()] = value.strip()
    return config

_env = _load_env()

MAIL_USERNAME = _env.get('MAIL_USERNAME', 'smartwalletmanagement@gmail.com')
MAIL_PASSWORD = _env.get('MAIL_PASSWORD', 'bycecrjrxatkkgbp')  # fallback to hardcoded
MAIL_SERVER   = _env.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT     = int(_env.get('MAIL_PORT', 587))

if not MAIL_PASSWORD:
    print("WARNING: MAIL_PASSWORD not found in .env file. Emails will not send.")


# ---------------------------------------------------------------------------
# CORE SEND FUNCTION
# ---------------------------------------------------------------------------
def send_swm_email(to_email: str, subject: str, html_content: str) -> bool:
    """
    Send an HTML email via Gmail SMTP.
    Returns True on success, False on failure.
    Never raises — so a failed email never crashes a payment route.
    """
    if not MAIL_PASSWORD:
        print("WARNING: Skipping email send — no MAIL_PASSWORD configured.")
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = MAIL_USERNAME
        msg['To']      = to_email

        part = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(part)

        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.sendmail(MAIL_USERNAME, to_email, msg.as_string())

        logger.info("Email sent successfully to %s", to_email)
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("Gmail authentication failed. Check your App Password.")
        return False
    except smtplib.SMTPException as e:
        logger.error("SMTP error while sending email: %s", e)
        return False
    except OSError as e:
        logger.error("OS error while sending email (possibly console I/O issue): %s", e)
        return False
    except Exception as e:
        logger.exception("Unexpected error while sending email")
        return False


# ---------------------------------------------------------------------------
# EMAIL TEMPLATES
# ---------------------------------------------------------------------------
def get_burn_rate_template(user_name: str, wallet_name: str, burn_rate: float, days_left: int) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #ff6b35, #f7c59f); padding: 30px; text-align: center; }}
            .header h1 {{ color: white; margin: 0; font-size: 28px; }}
            .body {{ padding: 30px; }}
            .body p {{ color: #555; line-height: 1.6; font-size: 15px; }}
            .stat-box {{ background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 15px 20px; margin: 20px 0; }}
            .stat-box p {{ margin: 5px 0; color: #856404; font-weight: bold; }}
            .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #aaa; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>High Spend Alert</h1>
            </div>
            <div class="body">
                <p>Hi <strong>{user_name}</strong>,</p>
                <p>Your <strong>{wallet_name}</strong> envelope is burning through funds faster than expected.</p>
                <div class="stat-box">
                    <p>Daily Burn Rate: Rs.{burn_rate:.2f} / day</p>
                    <p>Estimated Days Remaining: {days_left} days</p>
                </div>
                <p>Consider reducing your spending or adding more funds to this envelope to avoid running out.</p>
            </div>
            <div class="footer">
                <p>This is an automated alert from Smart Wallet Manager (SWM).</p>
            </div>
        </div>
    </body>
    </html>
    """


def get_goal_completed_template(user_name: str, goal_name: str, total_saved: float) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
            .header {{ background: linear-gradient(135deg, #6a11cb, #2575fc); padding: 30px; text-align: center; }}
            .header h1 {{ color: white; margin: 0; font-size: 28px; }}
            .body {{ padding: 30px; }}
            .body p {{ color: #555; line-height: 1.6; font-size: 15px; }}
            .stat-box {{ background: #d4edda; border: 1px solid #28a745; border-radius: 8px; padding: 15px 20px; margin: 20px 0; }}
            .stat-box p {{ margin: 5px 0; color: #155724; font-weight: bold; font-size: 18px; }}
            .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #aaa; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Goal Achieved!</h1>
            </div>
            <div class="body">
                <p>Congratulations <strong>{user_name}</strong>!</p>
                <p>You have successfully completed your savings goal.</p>
                <div class="stat-box">
                    <p>Goal: {goal_name}</p>
                    <p>Total Saved: Rs.{total_saved:,.2f}</p>
                </div>
                <p>Keep up the great work and set your next goal to continue building your financial future!</p>
            </div>
            <div class="footer">
                <p>This is an automated message from Smart Wallet Manager (SWM).</p>
            </div>
        </div>
    </body>
    </html>
    """