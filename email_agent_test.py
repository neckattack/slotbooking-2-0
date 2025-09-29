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

        # Mehrteilige E-Mails in Teilfragen zerlegen und jeweils beantworten
        from agent_gpt import agent_respond
        def _segment_questions(text: str):
            import re
            if not text:
                return []
            # Normalisieren von Zeilenumbrüchen
            t = text.replace('\r\n', '\n').replace('\r', '\n')
            # Erst nach Fragezeichen grob splitten und Fragezeichen wieder anhängen
            parts = []
            buf = []
            for ch in t:
                buf.append(ch)
                if ch == '?':
                    part = ''.join(buf).strip()
                    if part:
                        parts.append(part)
                    buf = []
            rest = ''.join(buf).strip()
            if rest:
                parts.append(rest)
            # Zusätzlich Bullet-Zeilen als eigene Fragen behandeln, falls keine Fragezeichen
            bullets = []
            for line in t.split('\n'):
                if re.match(r'^\s*([\-\*•]|\d+\.)\s+', line) and len(line.strip()) > 5:
                    bullets.append(line.strip())
            # Wenn keine klaren Fragen erkannt, fallback: ganzer Body als eine Frage
            if not parts and not bullets:
                return [t.strip()]
            # Mergen: bevorzugt parts (Fragen), ergänze bullets die noch nicht enthalten sind
            segs = parts[:]
            for b in bullets:
                if all(b not in p for p in segs):
                    segs.append(b)
            # Filter zu kurze Segmente
            segs = [s.strip() for s in segs if len(s.strip()) >= 5]
            return segs[:6]  # harte Obergrenze, um Spam zu vermeiden

        segments = _segment_questions(body)
        try:
            if len(segments) <= 1:
                antwort = agent_respond(body, channel="email", user_email=from_addr)
            else:
                antworten = []
                for i, seg in enumerate(segments):
                    try:
                        seg_answer = agent_respond(seg, channel="email", user_email=from_addr)
                    except Exception as e:
                        seg_answer = f"[Teilfrage {i+1}: Fehler bei der Antwortgenerierung: {e}]"
                    # Baue einen Abschnitt (übersichtlich je Frage)
                    abschnitt = f"<h3>Frage {i+1}</h3>\n<div>{seg_answer}</div>"
                    antworten.append(abschnitt)
                antwort = "\n".join(antworten)
            logger.info(f"Antwort generiert (Segmente={len(segments)}): {antwort[:300]}...")
        except Exception as e:
            logger.error(f"Fehler bei agent_respond: {e}")
            antwort = f"[Fehler bei der Antwortgenerierung: {e}]"
        try:
            send_test_reply(from_addr, subject, antwort)
            logger.info(f"Antwort an {from_addr} gesendet.")
        except Exception as e:
            logger.error(f"Fehler beim Senden der Antwort an {from_addr}: {e}")

    mail.logout()

def send_test_reply(to_addr, orig_subject, antwort_text):
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

            # Verwende die bereits erzeugte Antwort (kein zweiter LLM-Call)
            antwort_html = antwort_text
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
            from email.utils import parseaddr
            # Reine E-Mail extrahieren (z.B. aus "Name <mail@domain>")
            searched_email = (parseaddr(to_addr)[1] or to_addr).strip().lower()
            logger.info(f"[Mail-Check] Prüfe Rolle/Person für Absender (bereinigt): {searched_email}")
            # Case-insensitive Suche
            user_info = None
            try:
                user_info = get_user_info_by_email(searched_email)
            except Exception as e:
                logger.error(f"Fehler bei get_user_info_by_email: {e}")
            if user_info:
                full_name = (user_info.get('first_name') or '')
                if user_info.get('last_name'):
                    full_name = (full_name + ' ' + user_info['last_name']).strip()
                address = user_info.get('address') or '–'
                source = user_info.get('source') or 'unbekannt'
                user_id = user_info.get('user_id')
                logger.info(f"[Mail-Check] User erkannt: email={searched_email} | source={source} | user_id={user_id} | Rolle={user_info.get('role')} | Name={full_name} | Adresse={address}")
                debug_info = (
                    f"[DEBUG: BLUE-DB Treffer] email: {searched_email} | source: {source} | user_id: {user_id} | Name: {full_name} | Rolle: {user_info.get('role')} | Adresse: {address}"
                )
                if user_info.get('role') == 'admin':
                    antwort_html = '<b>Hallo Admin!</b><br>Du bist als Admin in der BLUE-Datenbank hinterlegt. Wenn du spezielle Systembefehle oder Support brauchst, gib mir einfach Bescheid.'
            else:
                logger.info(f"[Mail-Check] User nicht in BLUE-DB gefunden für: {searched_email}")
                debug_info = f"[DEBUG: Kein BLUE-DB Treffer] email: {searched_email}"
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
