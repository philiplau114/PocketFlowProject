import logging
import smtplib
from email.message import EmailMessage
import requests
import argparse
import sys
import config

def send_email(subject, body):
    if not (config.SMTP_SERVER and config.EMAIL_FROM and config.EMAIL_TO and config.SMTP_USER and config.SMTP_PASSWORD):
        logging.warning("Email not sent: SMTP/recipient config missing.")
        return False
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = config.EMAIL_FROM
        # support comma-separated or list for EMAIL_TO
        recipients = config.EMAIL_TO if isinstance(config.EMAIL_TO, list) else [addr.strip() for addr in str(config.EMAIL_TO).split(',') if addr.strip()]
        msg['To'] = ', '.join(recipients)
        msg.set_content(body)
        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
        logging.info("Email sent: %s", subject)
        return True
    except Exception as e:
        logging.error("Failed to send email: %s", e)
        return False

def send_telegram(message):
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        logging.warning("Telegram not sent: Bot token or chat id missing.")
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": config.TELEGRAM_CHAT_ID, "text": message}
    try:
        resp = requests.post(url, data=payload, timeout=10)
        if resp.status_code == 200:
            logging.info("Telegram sent: %s", message[:80])
            return True
        else:
            logging.error("Telegram send failed: %s", resp.text)
            return False
    except Exception as e:
        logging.error("Failed to send Telegram: %s", e)
        return False

def main():
    parser = argparse.ArgumentParser(description="Notification module test CLI")
    parser.add_argument("--test-email", action="store_true", help="Send a test email")
    parser.add_argument("--test-telegram", action="store_true", help="Send a test telegram message")
    parser.add_argument("--subject", type=str, help="Email subject (for --test-email)")
    parser.add_argument("--body", type=str, help="Email body (for --test-email)")
    parser.add_argument("--message", type=str, help="Telegram message (for --test-telegram)")

    args = parser.parse_args()

    if args.test_email:
        subject = args.subject or "PocketFlow Notification Test Email"
        body = args.body or "This is a test email from notify.py CLI mode."
        print(f"Sending test email: subject='{subject}' ...")
        success = send_email(subject, body)
        sys.exit(0 if success else 1)

    if args.test_telegram:
        message = args.message or "This is a test Telegram message from notify.py CLI mode."
        print(f"Sending test telegram message ...")
        success = send_telegram(message)
        sys.exit(0 if success else 1)

    parser.print_help()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()