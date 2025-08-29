import os
import logging
import smtplib
from email.message import EmailMessage
import requests
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
EMAIL_FROM = os.getenv('EMAIL_FROM')
EMAIL_TO = [addr.strip() for addr in os.getenv('EMAIL_TO', '').split(',') if addr.strip()]

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_email(subject, body):
    if not (SMTP_SERVER and EMAIL_FROM and EMAIL_TO and SMTP_USER and SMTP_PASSWORD):
        logging.warning("Email not sent: SMTP/recipient config missing.")
        return
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = EMAIL_FROM
        msg['To'] = ', '.join(EMAIL_TO)
        msg.set_content(body)
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        logging.info("Email sent: %s", subject)
    except Exception as e:
        logging.error("Failed to send email: %s", e)

def send_telegram(message):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        logging.warning("Telegram not sent: Bot token or chat id missing.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        resp = requests.post(url, data=payload, timeout=10)
        if resp.status_code == 200:
            logging.info("Telegram sent: %s", message[:80])
        else:
            logging.error("Telegram send failed: %s", resp.text)
    except Exception as e:
        logging.error("Failed to send Telegram: %s", e)