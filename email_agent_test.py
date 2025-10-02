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
        import re  # für Segmentierung/HTML-Umwandlung
        # Sichtbarer Preface-Block mit kommenden Jobs für Masseure (immer anzeigen, wenn vorhanden)
        visible_preface_html = ""
        def _fmt_dt(val):
            from datetime import datetime
            if val is None:
                return "—"
            if isinstance(val, datetime):
                dt = val
            else:
                s = str(val)
                # Versuche Standard-MySQL-Formate
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                    try:
                        dt = datetime.strptime(s, fmt)
                        break
                    except Exception:
                        dt = None
                if dt is None:
                    return s
            return dt.strftime("%d.%m.%Y, %H:%M Uhr")
        try:
            from agent_blue import get_user_info_by_email
            from email.utils import parseaddr as _parseaddr
            searched_email_pref = (_parseaddr(from_addr)[1] or from_addr).strip().lower()
            user_info_pref = get_user_info_by_email(searched_email_pref)
            if user_info_pref and user_info_pref.get('role') == 'masseur' and user_info_pref.get('user_id'):
                try:
                    from agent_debug_jobs import (
                        get_upcoming_tasks_via_bids,
                        get_upcoming_tasks_precise,
                        get_upcoming_jobs_for_user,
                    )
                    # 1) bevorzugt über Bids
                    jobs = get_upcoming_tasks_via_bids(int(user_info_pref['user_id']), limit=5)
                    # 2) ansonsten direkte Zuweisung user_id an Task
                    if not jobs:
                        jobs = get_upcoming_tasks_precise(int(user_info_pref['user_id']), limit=5)
                    # 3) heuristischer Fallback
                    if not jobs:
                        jobs = get_upcoming_jobs_for_user(int(user_info_pref['user_id']), limit=5)
                    if not jobs:
                        from agent_debug_jobs import get_bids_tasks_any
                        jobs = get_bids_tasks_any(int(user_info_pref['user_id']), limit=5)
                    if jobs:
                        items = []
                        for j in jobs:
                            date = _fmt_dt(j.get('date'))
                            loc = j.get('location') or '—'
                            title = j.get('task_title') or j.get('description') or '—'
                            instr = j.get('task_instruction')
                            instr_short = (instr[:80] + '…') if instr and len(instr) > 80 else (instr or '')
                            extra = f" <span style=\"color:#666;\">({instr_short})</span>" if instr_short else ""
                            items.append(f"<li><strong>{date}</strong> – {loc} · {title}{extra}</li>")
                        visible_preface_html = (
                            "<!-- PREFACE-BEGIN -->"
                            "<div style=\"margin-bottom:14px;\">"
                            "<p>Hier sind deine kommenden Jobs:</p>"
                            f"<ul>{''.join(items)}</ul>"
                            "</div>"
                            "<!-- PREFACE-END -->"
                        )
                except Exception:
                    pass
        except Exception:
            pass
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
            return segs  # keine harte Obergrenze, flexibel

        segments = _segment_questions(body)
        try:
            if len(segments) <= 1:
                antwort = (visible_preface_html or "") + (agent_respond(body, channel="email", user_email=from_addr) or "")
            else:
                # Persönliche Anrede aus From-Adresse ableiten
                from email.utils import parseaddr
                name_guess = parseaddr(from_addr)[0] or ""
                if not name_guess:
                    m = re.search(r"([a-zA-ZäöüÄÖÜß\-\.]+)", from_addr)
                    if m:
                        name_guess = m.group(1).split(".")[0].capitalize()
                antworten = ([] if visible_preface_html else [f"<p>Hallo {name_guess},</p>" if name_guess else "<p>Hallo,</p>"])
                def _strip_greeting_html(html: str) -> str:
                    import re as _re2
                    if not html:
                        return html
                    # Entferne führende Begrüßungszeilen (Hallo ..., Hallo Chris, etc.)
                    html = _re2.sub(r'^\s*<p>\s*Hallo[^<]*</p>\s*', '', html, flags=_re2.IGNORECASE)
                    html = _re2.sub(r'^\s*Hallo[^<>\n]*\n+', '', html, flags=_re2.IGNORECASE)
                    return html
                for i, seg in enumerate(segments):
                    try:
                        seg_answer = agent_respond(seg, channel="email", user_email=from_addr)
                    except Exception as e:
                        # Freundlicher Fallback statt Fehlermeldung
                        seg_answer = (
                            "Es gab gerade ein technisches Problem bei der Beantwortung. "
                            "Bitte formuliere die Teilfrage kurz erneut – ich helfe dir umgehend."
                        )
                    # Sicherstellen, dass die Antwort HTML ist
                    ans_html = seg_answer
                    if not ("<p>" in ans_html or "<ul>" in ans_html or "<ol>" in ans_html or "<div>" in ans_html):
                        def _text_to_html(text):
                            lines = (text or "").split('\n')
                            html_lines = []
                            in_list = False
                            for line in lines:
                                line = line.strip()
                                if re.match(r'^(\d+\.\s+|\-|•\s+)', line):
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
                        ans_html = _text_to_html(ans_html)
                    # Doppelte Anreden vermeiden: Begrüßung in Segmentantworten entfernen,
                    # wenn wir bereits eine Anrede gesetzt haben
                    if antworten:
                        ans_html = _strip_greeting_html(ans_html)
                    abschnitt = f"<div style=\"margin-top:14px;\">{ans_html}</div>"
                    antworten.append(abschnitt)
                # Abschlussformel
                abschluss = (
                    "<p style=\"margin-top:18px;\">Viele Grüße</p>\n"
                    "<p>Dein Support-Team</p>"
                )
                antworten.append(abschluss)
                antwort = (visible_preface_html or "") + "\n".join(antworten)
            # Letzter Schritt: LLM-Review zur Konsolidierung (keine doppelten Anreden, inhaltlich passend)
            try:
                import os as _os
                from openai import OpenAI as _OpenAI
                _client = _OpenAI(api_key=_os.environ.get("OPENAI_API_KEY"))
                review_system = (
                    "Du bist ein Assistent, der E-Mail-Antworten final prüft.\n"
                    "- Bewahre den Inhalt zwischen <!-- PREFACE-BEGIN --> und <!-- PREFACE-END --> UNVERÄNDERT.\n"
                    "- Entferne doppelte Begrüßungen/Abschlüsse.\n"
                    "- Sorge für eine stimmige, kurze und hilfreiche Antwort, die zur Nutzerfrage passt.\n"
                    "- Gib NUR validen HTML-Body zurück, ohne Codeblöcke/Markdown."
                )
                review_user = (
                    f"[ORIGINAL_FRAGE]:\n{body}\n\n[ANTWORT_HTML]:\n{antwort}"
                )
                review_tokens = 900
                try:
                    review_tokens = int(_os.environ.get("AGENT_MAX_TOKENS", "900"))
                except Exception:
                    pass
                _resp = _client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": review_system},
                        {"role": "user", "content": review_user}
                    ],
                    max_tokens=review_tokens,
                    temperature=0.1
                )
                _clean = _resp.choices[0].message.content.strip()
                # Entferne etwaige Codefences
                import re as __re
                _clean = __re.sub(r'^```(?:html|\w+)?\s*', '', _clean)
                _clean = __re.sub(r'```\s*$', '', _clean)
                if _clean and len(_clean) > 50:
                    antwort = _clean
            except Exception:
                pass

            logger.info(f"Antwort generiert (Segmente={len(segments)}): {antwort[:300]}...")
        except Exception as e:
            logger.error(f"Fehler bei agent_respond: {e}")
            # Freundlicher Gesamt-Fallback (ohne Begrüßung, um Doppelungen zu vermeiden)
            antwort = (
                "<p>leider gab es gerade ein technisches Problem bei der Erstellung der Antwort. "
                "Ich helfe dir sehr gerne – schicke mir die Frage bitte nochmal oder formuliere sie etwas kürzer.</p>"
            )
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
            from datetime import datetime as _dt
            def _fmt_de(val):
                if val is None:
                    return '—'
                if isinstance(val, _dt):
                    dt = val
                else:
                    s = str(val)
                    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                        try:
                            dt = _dt.strptime(s, fmt)
                            break
                        except Exception:
                            dt = None
                    if dt is None:
                        return s
                return dt.strftime("%d.%m.%Y, %H:%M Uhr")
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
                # Optional: kommende Jobs für Masseure abrufen
                jobs_snippet = ""
                try:
                    if user_info.get('role') == 'masseur' and user_id:
                        from agent_debug_jobs import (
                            get_upcoming_tasks_via_bids,
                            get_upcoming_tasks_precise,
                            get_upcoming_jobs_for_user,
                        )
                        # 1) Bids
                        jobs = get_upcoming_tasks_via_bids(int(user_id), limit=3)
                        source_label = 'bids' if jobs else ''
                        # 2) direkte Tasks
                        if not jobs:
                            jobs = get_upcoming_tasks_precise(int(user_id), limit=3)
                            source_label = 'tasks' if jobs else source_label
                        # 3) Heuristik
                        if not jobs:
                            jobs = get_upcoming_jobs_for_user(int(user_id), limit=3)
                        if not jobs:
                            from agent_debug_jobs import get_bids_tasks_any
                            jobs = get_bids_tasks_any(int(user_id), limit=3)
                            if jobs and not source_label:
                                source_label = 'bids_any'
                            if jobs and not source_label:
                                source_label = 'heuristic'
                        if jobs:
                            parts = []
                            for j in jobs:
                                date = _fmt_de(j.get('date'))
                                loc = j.get('location') or '—'
                                title = j.get('task_title') or j.get('description') or '—'
                                instr = j.get('task_instruction')
                                instr_short = (instr[:60] + '…') if instr and len(instr) > 60 else (instr or '')
                                suffix = f" ({instr_short})" if instr_short else ""
                                parts.append(f"({date}) {loc} – {title}{suffix}")
                            jobs_snippet = f" | Jobs[{source_label}:{len(jobs)}]: " + "; ".join(parts)
                except Exception as e:
                    logger.error(f"[DEBUG-JOBS] Fehler beim Abruf kommender Jobs für user_id={user_id}: {e}")
                if not jobs_snippet:
                    jobs_snippet = " | Jobs: – keine gefunden –"
                app_ver = os.environ.get('APP_VERSION') or os.environ.get('RENDER_GIT_COMMIT') or ''
                version_snippet = (f" | ver: {app_ver[:7]}" if app_ver else "")
                debug_info = (
                    f"[DEBUG: BLUE-DB Treffer] email: {searched_email} | source: {source} | user_id: {user_id} | Name: {full_name} | Rolle: {user_info.get('role')} | Adresse: {address}{jobs_snippet}{version_snippet}"
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
