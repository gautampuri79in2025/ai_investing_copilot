import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

def send_email(subject: str, body: str):
    """
    Sends a plain-text email using SMTP settings from .env
    """
    from_addr = os.getenv("EMAIL_FROM")
    to_addr = os.getenv("EMAIL_TO")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", from_addr)
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not from_addr or not to_addr or not smtp_password:
        print("⚠️ Email not sent: missing EMAIL_FROM/EMAIL_TO/SMTP_PASSWORD in .env")
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        print(f"📧 Email sent to {to_addr}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
