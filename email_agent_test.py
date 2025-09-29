import imaplib
import smtplib
import email
from email.header import decode_header
import os

IMAP_SERVER = os.environ.get('IMAP_SERVER')  # z.B. 'imap.gmail.com'
IMAP_PORT = int(os.environ.get('IMAP_PORT', 993))
EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASS = os.environ.get('EMAIL_PASS')
SMTP_SERVER = os.environ.get('SMTP_SERVER')  # z.B. 'smtp.gmail.com'
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
FAQ_ONLY = os.environ.get('AGENT_FAQ_ONLY', 'false').lower() == 'true'


from agent_core import find_next_appointment_for_name

def check_mail_and_reply():
    import logging
    logger = logging.getLogger()
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_USER, EMAIL_PASS)
        logger.info(f"[IMAP] Login erfolgreich für {EMAIL_USER}")
        mail.select('inbox')
    except Exception as e:
        logger.error(f"[IMAP] Login/Verbindung fehlgeschlagen: {e}")
        return

    # Suche nach ungelesenen Mails
    status, messages = mail.search(None, 'UNSEEN')
    if status != 'OK':
        logger.info('Keine neuen Mails gefunden.')
        mail.logout()
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
        logger.info(f"Neue Mail von {from_addr} mit Betreff '{subject}'")

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
        logger.info(f"Mail-Body: {body}")

        # Sende echte neckattack-GPT-Antwort zurück
        from agent_gpt import agent_respond
        try:
            antwort = agent_respond(body, channel="email", user_email=from_addr)
            logger.info(f"Antwort generiert: {antwort}")
        except Exception as e:
            logger.error(f"Fehler bei agent_respond: {e}")
            antwort = f"[Fehler bei der Antwortgenerierung: {e}]"
        try:
            send_test_reply(from_addr, subject, antwort)
            logger.info(f"Antwort an {from_addr} gesendet.")
        except Exception as e:
            logger.error(f"Fehler beim Senden der Antwort an {from_addr}: {e}")

    mail.logout()

def send_test_reply(to_addr, orig_subject, body):
    import smtplib
    import logging
    logger = logging.getLogger()
    try:
        from email.utils import parseaddr
        import re
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_USER, EMAIL_PASS)
            msg = email.message.EmailMessage()
            msg['From'] = EMAIL_USER
            msg['To'] = to_addr
            msg['Subject'] = f"Re: {orig_subject}"

            # --- Anrede ermitteln ---
            name = parseaddr(to_addr)[0]
            if not name:
                match = re.match(r"([a-zA-ZäöüÄÖÜß\-\.]+)", to_addr)
                name = match.group(1).split(".")[0].capitalize() if match else ""

            # Prompt für ChatGPT vorbereiten
            from agent_gpt import agent_respond
            beispiel_html = """
<p>Hallo Max,</p>
<p>vielen Dank für deine Anfrage. Hier die wichtigsten Schritte:</p>
<ul>
  <li>Logge dich ein.</li>
  <li>Klicke auf ...</li>
  <li>Prüfe ...</li>
</ul>
<p>Viele Grüße<br>Dein Support-Team</p>
"""
            if name:
                prompt_body = (
                    f"Bitte schreibe eine freundliche, professionelle Antwort-Mail an '{name}'. Die Antwort soll mit einer persönlichen Anrede beginnen, die folgende Nutzeranfrage beantworten und als vollständiges HTML mit <p>-Absätzen und <ul><li>-Listen, wo sinnvoll, formatiert sein. Gib ausschließlich HTML zurück, kein Markdown, keine reinen Texte. Abschluss freundlich. Beispiel:\n{beispiel_html}\nHier die Nutzeranfrage:\n\n{body}"
                )
            else:
                prompt_body = (
                    f"Bitte schreibe eine freundliche, professionelle Antwort-Mail. Die Antwort soll mit einer Anrede beginnen, die folgende Nutzeranfrage beantworten und als vollständiges HTML mit <p>-Absätzen und <ul><li>-Listen, wo sinnvoll, formatiert sein. Gib ausschließlich HTML zurück, kein Markdown, keine reinen Texte. Abschluss freundlich. Beispiel:\n{beispiel_html}\nHier die Nutzeranfrage:\n\n{body}"
                )
            try:
                antwort_html = agent_respond(prompt_body, channel="email", user_email=to_addr)
            except Exception as e:
                antwort_html = f"[Fehler bei der Antwortgenerierung: {e}]"
            # Fallback: Wenn kein HTML, dann Text in HTML umwandeln
            if not ("<p>" in antwort_html or "<ul>" in antwort_html or "<ol>" in antwort_html):
                def text_to_html(text):
                    import re
                    # Listenpunkte erkennen
                    lines = text.split('\n')
                    html_lines = []
                    in_list = False
                    for line in lines:
                        line = line.strip()
                        if re.match(r'^(\d+\.|\-|•)', line):
                            if not in_list:
                                html_lines.append('<ul>')
                                in_list = True
                            html_lines.append(f'<li>{line}</li>')
                        elif line:
                            if in_list:
                                html_lines.append('</ul>')
                                in_list = False
                            html_lines.append(f'<p>{line}</p>')
                    if in_list:
                        html_lines.append('</ul>')
                    return '\n'.join(html_lines)
                antwort_html = text_to_html(antwort_html)
            # Fallback: Plaintext-Version (HTML-Tags entfernen)
            import re
            # Entferne versehentlich eingefügte Markdown-Blöcke wie ```html am Anfang
            antwort_html = re.sub(r'^```html\s*', '', antwort_html.strip(), flags=re.IGNORECASE)
            antwort_plain = re.sub('<[^<]+?>', '', antwort_html)
            # --- Debug-Info aus BLUE-DB ---
            from agent_blue import get_user_info_by_email
            logger.info(f"[Mail-Check] Prüfe Rolle/Person für Absender: {to_addr}")
            # Case-insensitive Suche
            user_info = None
            try:
                user_info = get_user_info_by_email(to_addr.lower())
            except Exception as e:
                logger.error(f"Fehler bei get_user_info_by_email: {e}")
            if user_info:
                full_name = (user_info.get('first_name') or '')
                if user_info.get('last_name'):
                    full_name = (full_name + ' ' + user_info['last_name']).strip()
                address = user_info.get('address') or '–'
                logger.info(
                    f"[Mail-Check] User erkannt: Rolle={user_info.get('role')}, Name={full_name}, Adresse={address}"
                )
                debug_info = (
                    f"[DEBUG: User gefunden] Name: {full_name} | Rolle: {user_info.get('role')} | Adresse: {address}"
                )
                if user_info.get('role') == 'admin':
                    antwort_html = '<b>Hallo Admin!</b><br>Du bist als Admin in der BLUE-Datenbank hinterlegt. Wenn du spezielle Systembefehle oder Support brauchst, gib mir einfach Bescheid.'
            else:
                logger.info(f"[Mail-Check] User nicht in BLUE-DB gefunden für: {to_addr}")
                debug_info = "[DEBUG: User nicht in BLUE-DB gefunden]"
            # --- HTML-Body bauen ---
            html_body = f'''
            <div style="font-family:Arial,sans-serif;font-size:1.08em;">
              {antwort_html}
              <div style="margin-top:28px;text-align:left;">
                <img src="https://cdn-icons-png.flaticon.com/512/4712/4712035.png" alt="KI Bot" width="40" style="vertical-align:middle;border-radius:50%;margin-bottom:8px;">
                <br>
                <strong>neckattack KI-Assistenz</strong><br>
                <span style="font-size:0.95em;color:#666;">Ich bin der digitale Assistent von neckattack und helfe dir rund um die Uhr.</span>
                <hr style="margin:8px 0;">
                <span style="font-size:0.9em;">neckattack ltd. | Landhausstr. 90, Stuttgart | hello@neckattack.net</span>
                <br><span style="color:#c00;font-size:0.95em;">{debug_info}</span>
              </div>
            </div>
            '''
            msg.set_content(antwort_plain, subtype='plain')
            msg.add_alternative(html_body, subtype='html')
            logger.info(f"[Mail-Versand] Sende Antwort an {to_addr}...")
            server.send_message(msg)
            logger.info(f"[Mail-Versand] Antwort an {to_addr} gesendet.")
            logger.info(f"Antwort an {to_addr} gesendet.")
    except Exception as e:
        logger.error(f"Fehler beim SMTP-Versand an {to_addr}: {e}")


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
