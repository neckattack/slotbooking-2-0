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

        # Sende eine Testantwort zurück
        send_test_reply(from_addr, subject)

    mail.logout()

def send_test_reply(to_addr, orig_subject):
    # SMTP-Verbindung herstellen
    import smtplib
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        msg = email.message.EmailMessage()
        msg['From'] = EMAIL_USER
        msg['To'] = to_addr
        msg['Subject'] = f"Re: {orig_subject}"
        msg.set_content("Dies ist eine automatische Testantwort vom Agenten.")
        server.send_message(msg)
        print(f"Antwort an {to_addr} gesendet.")

if __name__ == "__main__":
    check_mail_and_reply()
