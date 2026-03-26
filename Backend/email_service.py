import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Replace these with your actual details
SENDER_EMAIL = "eventmanagementsys01@gmail.com"
APP_PASSWORD = "nuazzwirnwjwydba"  # Use an app password for Gmail

def send_swm_email(to_email, subject, html_content):
    msg = MIMEMultipart("alternative")
    msg['Subject'] = subject
    msg['From'] = f"SWM Alerts <{SENDER_EMAIL}>"
    msg['To'] = to_email

    part = MIMEText(html_content, 'html')
    msg.attach(part)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        print(f"Email successfully sent to {to_email}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

def get_burn_rate_template(user_name, wallet_name, burn_rate, days_left):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px solid #f1f5f9; }}
            .header {{ background-color: #fff7ed; padding: 30px; text-align: center; border-bottom: 2px solid #fed7aa; }}
            .header h1 {{ color: #c2410c; margin: 0; font-size: 24px; }}
            .content {{ padding: 30px; color: #334155; line-height: 1.6; font-size: 16px; }}
            .alert-box {{ background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 15px 20px; border-radius: 0 8px 8px 0; margin: 20px 0; font-weight: bold; color: #991b1b; }}
            .footer {{ background-color: #f8fafc; padding: 20px; text-align: center; font-size: 13px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
            .btn {{ display: inline-block; background-color: #c2410c; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>⚠️ High Spend Alert</h1>
            </div>
            <div class="content">
                <p>Hi {user_name},</p>
                <p>Your SWM financial health monitor has detected a high burn rate in one of your envelopes.</p>
                
                <div class="alert-box">
                    Sub-Wallet: {wallet_name}<br>
                    Current Burn Rate: ₹{burn_rate:,.0f} / day<br>
                    Estimated Depletion: {days_left} days
                </div>
                
                <p>At your current spending pace, this wallet will be completely empty soon. We recommend reviewing your recent transactions and slowing down your spending in this category.</p>
                
                
            </div>
            <div class="footer">
                You are receiving this because you enabled automated insights in SWM.
            </div>
        </div>
    </body>
    </html>
    """

def get_goal_completed_template(user_name, goal_name, total_saved):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 40px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px solid #f1f5f9; }}
            .header {{ background-color: #f0fdf4; padding: 30px; text-align: center; border-bottom: 2px solid #bbf7d0; }}
            .header h1 {{ color: #15803d; margin: 0; font-size: 28px; }}
            .content {{ padding: 30px; color: #334155; line-height: 1.6; font-size: 16px; text-align: center; }}
            .highlight-box {{ background-color: #faf5ff; border: 2px dashed #a855f7; padding: 25px; border-radius: 12px; margin: 25px 0; }}
            .highlight-box h2 {{ margin: 0 0 10px 0; color: #4c1d95; font-size: 22px; }}
            .amount {{ font-size: 32px; font-weight: 900; color: #a855f7; margin: 0; }}
            .footer {{ background-color: #f8fafc; padding: 20px; text-align: center; font-size: 13px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
            .btn {{ display: inline-block; background-color: #a855f7; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎉 Congratulations! 🎉</h1>
            </div>
            <div class="content">
                <p>Hi {user_name},</p>
                <p>You did it! Your dedication and smart financial planning have paid off.</p>
                
                <div class="highlight-box">
                    <h2>{goal_name}</h2>
                    <p style="margin: 0; color: #6b7280; text-transform: uppercase; font-size: 12px; font-weight: bold;">Fully Funded</p>
                    <p class="amount">₹{total_saved:,.0f}</p>
                </div>
                
                <p>Whether you're picking up the keys today or just securing the funds for the future, you should be incredibly proud of hitting this milestone.</p>
                
                
            </div>
            <div class="footer">
                Smart Wallet Management (SWM) - Celebrating your financial wins.
            </div>
        </div>
    </body>
    </html>
    """