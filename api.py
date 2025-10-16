#!/usr/bin/env python3
from flask import Flask, jsonify, request
import imaplib
import email
import re
import os
from dotenv import load_dotenv

load_dotenv()  # načte .env soubor

IMAP_HOST = "imap.rambler.ru"
IMAP_PORT = 993
API_PORT = int(os.getenv("PORT", 4000))  # default 5000

app = Flask(__name__)

def login_imap(email_user, email_pass):
    mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    mail.login(email_user, email_pass)
    return mail

def search_latest_email(mail, sender):
    mail.select("INBOX")
    status, data = mail.search(None, f'(FROM "{sender}")')
    if status != "OK":
        return None
    mail_ids = data[0].split()
    if not mail_ids:
        return None
    latest_email_id = mail_ids[-1]
    status, msg_data = mail.fetch(latest_email_id, "(RFC822)")
    if status != "OK":
        return None
    raw_email = msg_data[0][1]
    msg = email.message_from_bytes(raw_email)
    return msg

def extract_discord_link(msg):
    if msg is None:
        return None
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype == "text/html":
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            try:
                html_content = payload.decode(errors="ignore")
            except:
                html_content = str(payload)
            match = re.search(r'https://click\.discord\.com/[^\s"<>]+', html_content)
            if match:
                return match.group(0)
    return None

def extract_rockstar_code(msg):
    if msg is None:
        return None
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype == "text/html":
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            try:
                html_content = payload.decode(errors="ignore")
            except:
                html_content = str(payload)
            # exactly 6 digits
            match = re.search(r'\b(\d{6})\b', html_content)
            if match:
                return match.group(1)
    return None

@app.route("/get_codes", methods=["POST"])
def get_codes():
    """
    Accepts JSON:
    { "email": "...", "password": "..." }
    or
    { "credentials": "email:password" }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    email_user = data.get("email")
    email_pass = data.get("password")
    creds = data.get("credentials")

    if creds and (not email_user and not email_pass):
        if ":" not in creds:
            return jsonify({"error": "credentials must be in email:password format"}), 400
        email_user, email_pass = creds.split(":", 1)

    if not email_user or not email_pass:
        return jsonify({"error": "Missing email or password"}), 400

    try:
        mail = login_imap(email_user, email_pass)

        discord_msg = search_latest_email(mail, "noreply@discord.com")
        rockstar_msg = search_latest_email(mail, "noreply@rockstargames.com")

        discord_link = extract_discord_link(discord_msg) if discord_msg else None
        rockstar_code = extract_rockstar_code(rockstar_msg) if rockstar_msg else None

        mail.logout()
        return jsonify({
            "discord_link": discord_link,
            "rockstar_code": rockstar_code
        })
    except imaplib.IMAP4.error:
        return jsonify({"error": "IMAP login failed"}), 401
    except Exception as exc:
        return jsonify({"error": "internal server error", "detail": str(exc)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=API_PORT, debug=True)

