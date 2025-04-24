import imaplib
import smtplib
import email
from email.header import decode_header
import os
from dotenv import load_dotenv

# Lade Umgebungsvariablen (für Mail-Login)
load_dotenv()

IMAP_SERVER = os.environ.get('IMAP_SERVER')  # z.B. 'imap.gmail.com'
IMAP_PORT = int(os.environ.get('IMAP_PORT', 993))
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASS = os.environ.get('EMAIL_PASS')
SMTP_SERVER = os.environ.get('SMTP_SERVER')  # z.B. 'smtp.gmail.com'
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))


from agent_core import find_next_appointment_for_name

def check_mail_and_reply():
    # Verbinde mit IMAP-Server
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(EMAIL_USER, EMAIL_PASS)
    mail.select('inbox')

    # Suche nach ungelesenen Mails
    status, messages = mail.search(None, 'UNSEEN')
    if status != 'OK':
        print('Keine neuen Mails gefunden.')
        return

    for num in messages[0].split():
        status, data = mail.fetch(num, '(RFC822)')
        if status != 'OK':
            continue
        msg = email.message_from_bytes(data[0][1])
        subject, encoding = decode_header(msg['Subject'])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding or 'utf-8')
        from_addr = msg.get('From')
        print(f"Neue Mail von {from_addr} mit Betreff '{subject}'")

        # --- E-Mail-Inhalt analysieren ---
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    charset = part.get_content_charset() or 'utf-8'
                    body = part.get_payload(decode=True).decode(charset, errors='ignore')
                    break
        else:
            charset = msg.get_content_charset() or 'utf-8'
            body = msg.get_payload(decode=True).decode(charset, errors='ignore')
        print(f"Mail-Body: {body}")

        # Sende echte neckattack-GPT-Antwort zurück
        from agent_gpt import agent_respond
        antwort = agent_respond(body, channel="email", user_email=from_addr)
        send_test_reply(from_addr, subject, antwort)

    mail.logout()

def send_test_reply(to_addr, orig_subject, body):
    # SMTP-Verbindung herstellen
    import smtplib
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        msg = email.message.EmailMessage()
        msg['From'] = EMAIL_USER
        msg['To'] = to_addr
        msg['Subject'] = f"Re: {orig_subject}"
        msg.set_content(body)
        server.send_message(msg)
        print(f"Antwort an {to_addr} gesendet.")


import time
import logging

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            logging.info("[E-Mail-Agent] Starte Mail-Check ...")
            check_mail_and_reply()
            logging.info("[E-Mail-Agent] Warte 60 Sekunden bis zum nächsten Durchlauf ...")
            time.sleep(60)
        except Exception as e:
            logging.error(f"[E-Mail-Agent] Fehler: {e}")
            time.sleep(60)
