import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
import mysql.connector
from dotenv import load_dotenv
from datetime import datetime
from openai import OpenAI
from agent_core import find_next_appointment_for_name
from agent_gpt import agent_respond
from encryption_utils import encrypt_password, decrypt_password
from auth_utils import create_jwt_token, decode_jwt_token, verify_password, hash_password, require_auth, require_role

load_dotenv()

# Initialize OpenAI client
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Flask-App muss vor allen @app.route-Dekoratoren existieren
app = Flask(__name__)

# Einfache In-Memory-Caches (kurzer TTL) für Geschwindigkeit
INBOX_CACHE = {"data": None, "ts": 0, "key": None}
THREAD_CACHE = {}   # uid -> {data, ts}  (Mail-Thread-Inhalt)
COMPOSE_CACHE = {}  # uid -> {html, to, subject, ts} (Antwort-Entwurf)

# Per-Process TTL-Caches für BLUE-DB und Job-Abfragen (beschleunigt Preface)
BLUE_USER_CACHE = {}  # email -> {data, ts}
JOBS_CACHE = {}       # user_id -> {upcoming, past, ts}

def _cache_get(store: dict, key: str, ttl: int):
    import time as _t
    e = store.get(key)
    if not e:
        return None
    if _t.time() - e.get('ts', 0) > ttl:
        try:
            del store[key]
        except Exception:
            pass
        return None
    return e

def _cache_set(store: dict, key: str, value: dict):
    import time as _t
    value = dict(value or {})
    value['ts'] = _t.time()
    store[key] = value
    return value

# Agent-Aufruf mit Timeout, damit UI nicht hängt
def _agent_respond_with_timeout(text: str, *, channel: str, user_email: str, timeout_s: int = 8, agent_settings: dict = None, contact_profile: dict = None):
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as _TO
    import time as _time
    from flask import current_app as _cap
    def _call():
        try:
            return agent_respond(text, channel=channel, user_email=user_email, agent_settings=agent_settings, contact_profile=contact_profile)
        except Exception as e:
            try:
                _cap.logger.error(f"[agent_respond] exception: {e}")
            except Exception:
                pass
            return ""
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_call)
        try:
            t0 = _time.time()
            res = fut.result(timeout=timeout_s)
            dt = (_time.time() - t0)
            try:
                _cap.logger.info(f"[agent_respond] done in {dt:.2f}s (timeout_s={timeout_s}) len={len(res or '')}")
            except Exception:
                pass
            return res or "", False
        except _TO:
            try:
                fut.cancel()
            except Exception:
                pass
            try:
                _cap.logger.warning(f"[agent_respond] TIMEOUT after {timeout_s}s")
            except Exception:
                pass
            return "", True

# Plaintext -> einfaches, sauberes HTML (Absätze, Listen, Zeilenumbrüche)
def _plaintext_to_html_email(s: str) -> str:
    import re as _re
    import html as _html
    if not s:
        return ""
    # Wenn schon HTML-Tags enthalten sind, nicht doppelt konvertieren
    if '<' in s and '>' in s:
        return s
    # HTML-escapen
    s = _html.escape(s)
    # Einfache Markdown-Fettschrift **text** -> <strong>text</strong>
    s = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    lines = s.splitlines()
    out = []
    i = 0
    n = len(lines)
    while i < n:
        # Geordnete Liste erkennen (1. 2. 3.)
        if _re.match(r"^\s*\d+\.\s+", lines[i]):
            # Prüfe, ob es wirklich eine Sequenz ist; sonst Einzel-"1." verwerfen
            j = i
            items = []
            while j < n and _re.match(r"^\s*\d+\.\s+", lines[j]):
                li = _re.sub(r"^\s*\d+\.\s+", '', lines[j]).strip()
                items.append(li)
                j += 1
            if len(items) >= 2:
                out.append('<ol>')
                for li in items:
                    out.append(f"<li>{li}</li>")
                out.append('</ol>')
                i = j
                while i < n and lines[i].strip() == '':
                    i += 1
                continue
            else:
                # Einzelne oder leere "1."-Zeile ignorieren
                i = j
                while i < n and lines[i].strip() == '':
                    i += 1
                continue
        # Ungeordnete Liste erkennen (- oder •)
        if _re.match(r"^\s*(?:[-•])\s+", lines[i]):
            out.append('<ul>')
            while i < n and _re.match(r"^\s*(?:[-•])\s+", lines[i]):
                li = _re.sub(r"^\s*(?:[-•])\s+", '', lines[i]).strip()
                out.append(f"<li>{li}</li>")
                i += 1
            out.append('</ul>')
            while i < n and lines[i].strip() == '':
                i += 1
            continue
        # Absatz sammeln bis Leerzeile
        para = []
        while i < n and lines[i].strip() != '':
            para.append(lines[i])
            i += 1
        # Leerzeilen überspringen
        while i < n and lines[i].strip() == '':
            i += 1
        text = '<br>'.join([p.strip() for p in para])
        # aufeinanderfolgende <br> reduzieren
        text = _re.sub(r"(?:<br>\s*){2,}", '<br>', text)
        if text:
            out.append(f"<p>{text}</p>")
    html = '\n'.join(out).strip()
    return html or _html.escape(s)

# Cached BLUE-User-Infos (TTL 120s)
def _get_user_info_cached(email_addr: str, ttl: int = 120):
    try:
        ck = (email_addr or '').strip().lower()
        c = _cache_get(BLUE_USER_CACHE, ck, ttl)
        if c is not None:
            return c.get('data')
        from agent_blue import get_user_info_by_email
        data = get_user_info_by_email(ck)
        _cache_set(BLUE_USER_CACHE, ck, {'data': data})
        return data
    except Exception:
        return None

# Cached Jobs (TTL 120s)
def _get_jobs_cached(user_id: int, ttl: int = 120):
    try:
        key = str(int(user_id))
        c = _cache_get(JOBS_CACHE, key, ttl)
        if c is not None:
            return c.get('upcoming') or [], c.get('past') or []
        from agent_debug_jobs import (
            get_upcoming_tasks_via_bids,
            get_upcoming_tasks_precise,
            get_upcoming_jobs_for_user,
            get_past_tasks_via_bids,
        )
        jobs = get_upcoming_tasks_via_bids(user_id, limit=5)
        if not jobs:
            jobs = get_upcoming_tasks_precise(user_id, limit=5)
        if not jobs:
            jobs = get_upcoming_jobs_for_user(user_id, limit=5)
        if not jobs:
            from agent_debug_jobs import get_bids_tasks_any
            jobs = get_bids_tasks_any(user_id, limit=5)
        try:
            jobs_past = get_past_tasks_via_bids(user_id, limit=5) or []
        except Exception:
            jobs_past = []
        _cache_set(JOBS_CACHE, key, {'upcoming': jobs or [], 'past': jobs_past or []})
        return jobs or [], jobs_past or []
    except Exception:
        return [], []

@app.route("/api/health", methods=["GET"])
def health_check():
    """
    Health-Check- und Routing-Test für die FAQ/DB-Logik.
    Gibt die Antworten auf eine FAQ- und eine DB-Testfrage als JSON zurück.
    """
    faq_frage = "Wie erkenne ich, ob meine Rechnung bezahlt wurde?"
    db_frage = "Welche Termine gibt es morgen?"
    try:
        faq_antwort = agent_respond(faq_frage, channel="health")
        db_antwort = agent_respond(db_frage, channel="health")
        return jsonify({
            "status": "ok",
            "faq_test": {
                "frage": faq_frage,
                "antwort": faq_antwort
            },
            "db_test": {
                "frage": db_frage,
                "antwort": db_antwort
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/healthz")
def healthz():
    return "ok", 200

import logging
app.logger.setLevel(logging.INFO)

# Logge die Version des MySQL-Connectors
import mysql.connector
app.logger.info(f"mysql-connector-python Version: {mysql.connector.__version__}")

# Prüfe und logge die wichtigsten DB-Umgebungsvariablen beim Start
app.logger.info(f"[DB-UMGEBUNG] DB_HOST={os.environ.get('DB_HOST')}, DB_USER={os.environ.get('DB_USER')}, DB_NAME={os.environ.get('DB_NAME')}, DB_PORT={os.environ.get('DB_PORT')}")

from db_utils import get_db_connection
from flask import current_app
from db_utils_blue import get_blue_db_connection

@app.route('/debug/db-test')
def debug_db_test():
    """
    Prüft die Verbindung zur BLUE-DB und sucht nach einer Test-Admin-Mail.
    Gibt das Ergebnis als JSON zurück.
    """
    import os
    test_email = os.environ.get('DEBUG_ADMIN_EMAIL', 'chris.walther@neckattack.net')
    result = {'db_connect': False, 'admin_found': False, 'error': None}
    try:
        conn = get_blue_db_connection()
        cursor = conn.cursor(dictionary=True)
        result['db_connect'] = True
        cursor.execute("SELECT admin_username FROM tbl_admin WHERE admin_email = %s", (test_email,))
        admin_row = cursor.fetchone()
        result['admin_found'] = bool(admin_row)
        if admin_row:
            result['admin_username'] = admin_row['admin_username']
        cursor.close()
        conn.close()
    except Exception as e:
        result['error'] = str(e)
    return jsonify(result)


def get_reservations_for_today():
    """
    Returns a list of reservations (customer name and email) for today's date.
    """
    today_str = datetime.now().strftime('%Y-%m-%d')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT r.name AS kunde, r.email AS kunde_email
        FROM reservations r
        JOIN times t ON r.time_id = t.id
        JOIN dates d ON t.date_id = d.id
        WHERE d.date = %s
    """
    try:
        cursor.execute(sql, (today_str,))
        rows = cursor.fetchall()
        reservations = [{"name": row["kunde"], "email": row["kunde_email"]} for row in rows if row["kunde"]]
        return reservations
    except Exception as e:
        app.logger.error(f"[DB-Fehler bei get_reservations_for_today]: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

@app.route("/")
def index():
    # Standardansicht: zur Inbox weiterleiten
    return redirect(url_for('emails_page'))

@app.route("/emails")
def emails_page():
    return render_template("emails.html")

@app.route("/api/emails/inbox")
@require_auth
def api_emails_inbox(current_user):
    import imaplib, email
    from email.header import decode_header
    limit = request.args.get('limit', default=20, type=int)
    
    # Check if user has email settings configured
    user_email = current_user.get('user_email')
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT imap_host, imap_port, imap_user, imap_pass_encrypted, imap_security "
            "FROM user_email_settings WHERE user_email=%s",
            (user_email,)
        )
        settings = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if settings and settings.get('imap_host'):
            # Use user's settings
            from encryption_utils import decrypt_password
            host = settings['imap_host']
            port = int(settings.get('imap_port', 993))
            user = settings['imap_user']
            pw = decrypt_password(settings['imap_pass_encrypted']) if settings['imap_pass_encrypted'] else ''
            mailbox = 'INBOX'
        else:
            # No user settings - return error to prompt configuration
            return jsonify({"error": "Please configure email settings first", "needs_config": True}), 400
    except Exception as e:
        app.logger.error(f"[IMAP] Error checking user settings: {e}")
        # No fallback - user must configure their own email settings
        return jsonify({"error": "Email settings error. Please configure your email settings.", "needs_config": True}), 400
    
    if not (host and user and pw):
        return jsonify({"error": "IMAP configuration incomplete. Please configure email settings."}), 400
    try:
        # Cache nutzen
        cache_key = f"{host}:{port}:{user}:{mailbox}:{limit}"
        import time as _t
        now = _t.time()
        if INBOX_CACHE["data"] is not None and INBOX_CACHE["key"] == cache_key and now - INBOX_CACHE["ts"] < 15:
            return jsonify({'items': INBOX_CACHE['data']})
        # Logge, welche Keys tatsächlich verwendet werden
        used_host_key = 'IMAP_HOST' if os.environ.get('IMAP_HOST') else ('IMAP_SERVER' if os.environ.get('IMAP_SERVER') else '—')
        used_user_key = 'IMAP_USER' if os.environ.get('IMAP_USER') else ('EMAIL_USER' if os.environ.get('EMAIL_USER') else '—')
        used_pass_key = 'IMAP_PASS' if os.environ.get('IMAP_PASS') else ('EMAIL_PASS' if os.environ.get('EMAIL_PASS') else '—')
        app.logger.info(f"[IMAP] Verbinde zu {host}:{port}, mailbox={mailbox}, user={(user or '')[:3]+'***'} | keys host={used_host_key}, user={used_user_key}, pass={used_pass_key}")
        M = imaplib.IMAP4_SSL(host, port)
        M.login(user, pw)
        sel_typ, sel_data = M.select(mailbox)
        if sel_typ != 'OK':
            raise RuntimeError(f"IMAP select failed: {sel_typ} {sel_data}")
        # UID-Suche ist robuster
        typ, data = M.uid('search', None, 'ALL')
        if typ != 'OK' or not data or data[0] is None:
            raise RuntimeError(f'IMAP UID search failed: {typ} {data}')
        ids = data[0].split()
        app.logger.info(f"[IMAP] Treffer gesamt: {len(ids)}")
        ids = ids[-limit:] if limit and len(ids) > limit else ids
        items = []
        for mid in reversed(ids):  # neueste zuerst
            typ, msgdata = M.uid('fetch', mid, '(FLAGS RFC822.HEADER)')
            if typ != 'OK' or not msgdata or not msgdata[0]:
                continue
            # msgdata kann ein Tupel oder Liste sein
            tup = msgdata[0]
            raw_bytes = tup[1] if isinstance(tup, tuple) else tup
            # FLAGS extrahieren
            flags_raw = (tup[0].decode() if isinstance(tup, tuple) and isinstance(tup[0], (bytes, bytearray)) else '')
            seen = ('\\Seen' in flags_raw) if flags_raw else False
            msg = email.message_from_bytes(raw_bytes)
            # Betreff decodieren
            raw_sub = msg.get('Subject', '')
            dh = decode_header(raw_sub)
            subject_parts = []
            for s, enc in dh:
                try:
                    subject_parts.append(s.decode(enc or 'utf-8') if isinstance(s, bytes) else str(s))
                except Exception:
                    subject_parts.append(s.decode('utf-8', errors='ignore') if isinstance(s, bytes) else str(s))
            subject = ''.join(subject_parts)
            from_addr = msg.get('From', '')
            date = msg.get('Date', '')
            uid_str = mid.decode() if isinstance(mid, (bytes, bytearray)) else str(mid)
            message_id = msg.get('Message-ID', '') or uid_str
            items.append({
                'subject': subject,
                'from': from_addr,
                'date': date,
                'message_id': message_id,
                'uid': uid_str,
                'seen': seen
            })
        M.close()
        M.logout()
        INBOX_CACHE["data"] = items
        INBOX_CACHE["ts"] = now
        INBOX_CACHE["key"] = cache_key
        return jsonify({'items': items})
    except Exception as e:
        app.logger.error(f"[IMAP] Fehler beim Laden der Inbox: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/contacts/<int:contact_id>/topics', methods=['GET'])
@require_auth
def api_contacts_topics_list(current_user, contact_id):
    """Gibt gespeicherte Themen (contact_topics) für einen Kontakt zurück."""
    user_email = current_user.get('user_email')
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, topic_label, topic_type, status, last_mentioned_at
            FROM contact_topics
            WHERE user_email=%s AND contact_id=%s
            ORDER BY COALESCE(last_mentioned_at, created_at) DESC, id DESC
            """,
            (user_email, contact_id),
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        topics = []
        for r in rows:
            topics.append(
                {
                    "id": r["id"],
                    "label": r["topic_label"],
                    "topic_type": r.get("topic_type"),
                    "status": r.get("status"),
                    "last_mentioned_at": r.get("last_mentioned_at").strftime("%d.%m.%Y") if r.get("last_mentioned_at") else None,
                }
            )
        return jsonify({"topics": topics}), 200
    except Exception as e:
        app.logger.error(f"[Contact Topics List] Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/emails/agent-compose', methods=['POST'])
@require_auth
def api_emails_agent_compose(current_user):
    """Erstellt einen Antwortvorschlag (HTML) für eine gegebene E-Mail-ID aus DB.
    Request: { uid: email_id (int) }
    Response: { html, to, subject }
    """
    data = request.get_json(silent=True) or {}
    email_id = data.get('uid')  # uid ist jetzt email_id aus DB
    # Optional: längeres Timeout anfordern (z. B. 20s), aber deckeln
    try:
        req_timeout = int(data.get('timeout_s')) if 'timeout_s' in data else None
    except Exception:
        req_timeout = None
    if req_timeout is None:
        timeout_s = 8
    else:
        timeout_s = max(4, min(30, req_timeout))
    if not email_id:
        return jsonify({'error': 'email_id fehlt'}), 400
    
    try:
        email_id = int(email_id)
    except:
        return jsonify({'error': 'email_id muss eine Zahl sein'}), 400
    
    user_email = current_user.get('user_email')
    try:
        # Compose-Cache Early-Return (TTL 300s) für schnelle Wiederholungen
        import time as _t
        now = _t.time()
        cc = COMPOSE_CACHE.get(str(email_id))
        if cc and now - cc.get('ts', 0) < 300 and not cc.get('timed_out'):
            if cc.get('has_body') or cc.get('has_preface'):
                return jsonify({ 'html': cc['html'], 'to': cc['to'], 'subject': cc['subject'] })
            else:
                try:
                    del COMPOSE_CACHE[str(email_id)]
                except Exception:
                    pass
        
        # Load email from database
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT e.id, e.subject, e.from_addr, e.from_name, e.to_addrs, e.body_text, e.body_html, 
                   e.contact_id, c.name as contact_name, c.contact_email, 
                   c.profile_summary, c.email_count
            FROM emails e
            LEFT JOIN contacts c ON e.contact_id = c.id
            WHERE e.id = %s AND e.user_email = %s
            """,
            (email_id, user_email)
        )
        email_row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not email_row:
            return jsonify({'error': 'E-Mail nicht gefunden'}), 404
        
        subject = email_row['subject'] or ''
        from_addr = email_row['from_addr'] or ''
        from_name = email_row['from_name'] or ''
        to_addr = email_row['to_addrs'] or ''
        plaintext = email_row['body_text']
        html_body = email_row['body_html']
        
        # Quelle für den Agenten: bevorzugt Plaintext; wenn nur HTML vorhanden ist, in Text umwandeln
        def _html_to_text(s: str) -> str:
            import re, html as _html
            if not s:
                return ''
            # Zeilenumbrüche für Blockelemente
            s = re.sub(r'<\s*br\s*/?>', '\n', s, flags=re.IGNORECASE)
            s = re.sub(r'</\s*p\s*>', '\n\n', s, flags=re.IGNORECASE)
            s = re.sub(r'</\s*div\s*>', '\n', s, flags=re.IGNORECASE)
            s = re.sub(r'</\s*li\s*>', '\n', s, flags=re.IGNORECASE)
            # Tags entfernen
            s = re.sub(r'<[^>]+>', '', s)
            # HTML-Entities
            s = _html.unescape(s)
            # Whitespace normalisieren
            s = re.sub(r'\n\s*\n\s*\n+', '\n\n', s)
            return s.strip()
        source_text = (plaintext or ( _html_to_text(html_body) if html_body else '' )).strip()
        
        # Intelligente Begrüßung basierend auf User-Stil und Kontakt
        from email.utils import parseaddr as _parseaddr
        
        # Helper: Extract greeting style from sent emails
        def _learn_user_greeting_style(user_email_addr, contact_email_addr):
            """Analyzes user's sent emails to learn their greeting style"""
            try:
                conn_learn = get_settings_db_connection()
                cursor_learn = conn_learn.cursor(dictionary=True)
                
                # Get last 10 sent emails from this user to this contact (or any contact)
                cursor_learn.execute(
                    """
                    SELECT body_text, body_html 
                    FROM emails 
                    WHERE user_email = %s 
                    AND from_addr LIKE %s
                    ORDER BY received_at DESC 
                    LIMIT 10
                    """,
                    (user_email, f"%{user_email_addr}%")
                )
                sent_emails = cursor_learn.fetchall()
                cursor_learn.close()
                conn_learn.close()
                
                if not sent_emails:
                    return None
                
                # Extract greetings from email bodies
                import re
                greetings = []
                for em in sent_emails:
                    text = (em['body_text'] or em['body_html'] or '')[:300]
                    # Match common German greetings at start of email
                    patterns = [
                        r'^(Hallo|Hi|Hey|Moin|Guten Tag|Sehr geehrte[rs]?|Liebe[rs]?)\s+([^,\n]+)',
                        r'^(Servus|Grüß Gott|Grüezi)\s+([^,\n]+)',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, text.strip(), re.IGNORECASE | re.MULTILINE)
                        if match:
                            greetings.append(match.group(1))
                            break
                
                if greetings:
                    # Return most common greeting
                    from collections import Counter
                    most_common = Counter(greetings).most_common(1)[0][0]
                    return most_common
                
                return None
            except Exception as e:
                app.logger.warning(f"[Learn Greeting] Error: {e}")
                return None
        
        # Helper: Determine formal vs informal address
        def _determine_address_style(contact_name, contact_email_addr, user_email_addr):
            """Determines if contact should be addressed formally (Sie) or informally (Du)"""
            try:
                conn_style = get_settings_db_connection()
                cursor_style = conn_style.cursor(dictionary=True)
                
                # Check previous emails from user to contact for Sie/Du
                cursor_style.execute(
                    """
                    SELECT body_text, body_html 
                    FROM emails 
                    WHERE user_email = %s 
                    AND (to_addrs LIKE %s OR from_addr LIKE %s)
                    ORDER BY received_at DESC 
                    LIMIT 5
                    """,
                    (user_email, f"%{contact_email_addr}%", f"%{contact_email_addr}%")
                )
                emails_hist = cursor_style.fetchall()
                cursor_style.close()
                conn_style.close()
                
                du_count = 0
                sie_count = 0
                
                for em in emails_hist:
                    text = (em['body_text'] or em['body_html'] or '').lower()
                    # Count Du/Dir/Dein vs Sie/Ihnen/Ihr
                    du_count += len(re.findall(r'\b(du|dir|dein|deine)\b', text))
                    sie_count += len(re.findall(r'\b(sie|ihnen|ihr|ihre)\b', text))
                
                # Determine formality
                is_formal = sie_count > du_count
                
                # Determine if first name or last name
                use_first_name = not is_formal or '@' not in (contact_name or '')
                
                name_to_use = contact_name or contact_email_addr.split('@')[0]
                
                # Try to extract first/last name
                if ' ' in (contact_name or ''):
                    parts = contact_name.split()
                    first_name = parts[0]
                    last_name = parts[-1] if len(parts) > 1 else parts[0]
                    
                    if use_first_name:
                        name_to_use = first_name
                    else:
                        # Formal: Herr/Frau + last name (we can't determine gender, so skip title)
                        name_to_use = last_name
                else:
                    name_to_use = contact_name or contact_email_addr.split('@')[0]
                
                return {
                    'is_formal': is_formal,
                    'use_first_name': use_first_name,
                    'name': name_to_use,
                    'full_name': contact_name
                }
                
            except Exception as e:
                app.logger.warning(f"[Address Style] Error: {e}")
                return {
                    'is_formal': False,
                    'use_first_name': True,
                    'name': contact_name or contact_email_addr.split('@')[0],
                    'full_name': contact_name
                }
        
        # Learn greeting style and address
        contact_email_addr = email_row.get('contact_email') or from_addr
        contact_name_str = email_row.get('contact_name') or from_name or ''
        contact_profile_summary = email_row.get('profile_summary', '')
        
        # Helper: Extract name from profile or email address
        def _extract_real_name(name_str, email_addr, profile_summary):
            """Extract actual name from various sources"""
            # If name is just an email address, extract local part
            if '@' in (name_str or ''):
                local_part = name_str.split('@')[0]
                # Capitalize first letter
                name_str = local_part.capitalize()
            
            # If name is still empty or looks like email, try profile
            if not name_str or '@' in name_str:
                if profile_summary:
                    # Try to extract name from profile: "Johanna ist..." or "Name: Johanna"
                    import re
                    # Pattern 1: "Johanna ist..." at start
                    match = re.search(r'^([A-ZÄÖÜ][a-zäöüß]+)\s+(ist|arbeitet|hat|sendet)', profile_summary)
                    if match:
                        name_str = match.group(1)
                    else:
                        # Pattern 2: Look for capitalized name after common phrases
                        match = re.search(r'(?:Kunde|Person|Kontakt|Name):\s*([A-ZÄÖÜ][a-zäöüß]+)', profile_summary)
                        if match:
                            name_str = match.group(1)
            
            # Final fallback: extract from email
            if not name_str or '@' in name_str:
                local_part = email_addr.split('@')[0] if email_addr else 'Kunde'
                name_str = local_part.capitalize()
            
            return name_str
        
        # Extract real name before processing
        contact_name_str = _extract_real_name(contact_name_str, contact_email_addr, contact_profile_summary)
        
        user_greeting_style = _learn_user_greeting_style(user_email, contact_email_addr)
        address_info = _determine_address_style(contact_name_str, contact_email_addr, user_email)
        
        # Build personalized greeting
        greeting_word = user_greeting_style or "Hallo"
        contact_display_name = address_info['name']
        
        if address_info['is_formal'] and not address_info['use_first_name']:
            # Formal: "Sehr geehrter Herr Schmidt" or "Guten Tag Frau Müller"
            if greeting_word.lower() in ['sehr geehrter', 'sehr geehrte']:
                greeting_html = f"<p>{greeting_word} {contact_display_name},</p>"
            else:
                greeting_html = f"<p>{greeting_word} {contact_display_name},</p>"
        else:
            # Informal: "Hallo Max" or "Moin Anna"
            greeting_html = f"<p>{greeting_word} {contact_display_name},</p>"
        
        app.logger.info(f"[Greeting] Style: {greeting_word}, Formal: {address_info['is_formal']}, Name: {contact_display_name}")
        # Preface: Jobs upcoming/past (nur bei EXPLIZITER Bitte nach Jobs/Terminen)
        visible_preface_html = ""
        _source_lc = (source_text or "").lower()
        _job_terms = ['job', 'jobs', 'termin', 'termine', 'einsatz', 'einsätze', 'auftrag', 'aufträge']
        _request_terms = ['bitte', 'auflisten', 'liste', 'übersicht', 'zeige', 'meine', 'kommenden', 'letzten', 'zukünftigen', 'vergangenen']
        _explicit_patterns = [
            'meine jobs', 'meine termine', 'kommenden jobs', 'kommenden termine', 'letzten jobs', 'letzten termine',
            'zukünftigen jobs', 'zukünftigen termine', 'vergangenen jobs', 'vergangenen termine',
            'jobs auflisten', 'termine auflisten', 'übersicht deiner jobs', 'übersicht deiner termine'
        ]
        _preface_ok = (
            any(t in _source_lc for t in _explicit_patterns) or
            (any(t in _source_lc for t in _job_terms) and any(t in _source_lc for t in _request_terms))
        )
        def _fmt_dt(val):
            from datetime import datetime as _dt
            if val is None:
                return "—"
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
        try:
            searched_email_pref = (_parseaddr(from_addr)[1] or from_addr).strip().lower()
            user_info_pref = _get_user_info_cached(searched_email_pref)
            jobs_upcoming, jobs_past = [], []
            if user_info_pref and user_info_pref.get('role') == 'masseur' and user_info_pref.get('user_id'):
                try:
                    jobs_upcoming, jobs_past = _get_jobs_cached(int(user_info_pref['user_id']))
                except Exception:
                    pass
            if _preface_ok and (jobs_upcoming or jobs_past):
                blocks = []
                if jobs_upcoming:
                    items = []
                    for j in jobs_upcoming:
                        date = _fmt_dt(j.get('date'))
                        loc = j.get('location') or '—'
                        title = j.get('task_title') or j.get('description') or '—'
                        instr = j.get('task_instruction')
                        instr_short = (instr[:80] + '…') if instr and len(instr) > 80 else (instr or '')
                        extra = f" <span style=\"color:#666;\">({instr_short})</span>" if instr_short else ""
                        items.append(f"<li><strong>{date}</strong> – {loc} · {title}{extra}</li>")
                    blocks.append("<p>Deine nächsten Jobs:</p>" + f"<ul>{''.join(items)}</ul>")
                if jobs_past:
                    items = []
                    for j in jobs_past:
                        date = _fmt_dt(j.get('date'))
                        loc = j.get('location') or '—'
                        title = j.get('task_title') or j.get('description') or '—'
                        items.append(f"<li><strong>{date}</strong> – {loc} · {title}</li>")
                    blocks.append("<p>Deine letzten Jobs:</p>" + f"<ul>{''.join(items)}</ul>")
                intro = "<p>hier ist eine kurze Übersicht deiner nächsten und letzten Jobs:</p>"
                visible_preface_html = ("<!-- PREFACE-BEGIN -->" "<div style=\"margin-bottom:14px;\">" + intro + "".join(blocks) + "</div>" "<!-- PREFACE-END -->")
        except Exception:
            pass
        
        # Load user agent settings for personalized responses
        agent_settings = {}
        try:
            conn_settings = get_settings_db_connection()
            cursor_settings = conn_settings.cursor(dictionary=True)
            cursor_settings.execute(
                "SELECT role, instructions, faq_text, document_links "
                "FROM user_agent_settings WHERE user_email=%s",
                (user_email,)
            )
            settings_row = cursor_settings.fetchone()
            cursor_settings.close()
            conn_settings.close()
            if settings_row:
                agent_settings = {
                    'role': settings_row.get('role') or '',
                    'instructions': settings_row.get('instructions') or '',
                    'faq_text': settings_row.get('faq_text') or '',
                    'document_links': settings_row.get('document_links') or ''
                }
        except Exception as e:
            app.logger.warning(f"[Agent-Compose] Could not load agent settings: {e}")
        
        # Load contact profile if available (from DB using uid as email_id)
        contact_profile = None
        try:
            conn_profile = get_settings_db_connection()
            cursor_profile = conn_profile.cursor(dictionary=True)
            cursor_profile.execute(
                """
                SELECT e.contact_id, c.name, c.contact_email, c.profile_summary, c.email_count 
                FROM emails e 
                LEFT JOIN contacts c ON e.contact_id = c.id 
                WHERE e.id = %s AND e.user_email = %s
                """,
                (email_id, user_email)
            )
            row = cursor_profile.fetchone()
            cursor_profile.close()
            conn_profile.close()
            if row and row.get('profile_summary'):
                contact_profile = {
                    'name': row.get('name'),
                    'email': row.get('contact_email'),
                    'summary': row.get('profile_summary'),
                    'email_count': row.get('email_count')
                }
                app.logger.info(f"[Agent-Compose] Loaded contact profile for {row.get('name')}")
        except Exception as e:
            app.logger.warning(f"[Agent-Compose] Could not load contact profile: {e}")
        
        # Agent-Antwort mit Timeout (UI soll nicht >8s warten)
        antwort_body, timed_out = _agent_respond_with_timeout(source_text, channel="email", user_email=from_addr, timeout_s=timeout_s, agent_settings=agent_settings, contact_profile=contact_profile)
        # Doppelte Grußformeln entfernen, falls LLM bereits mit "Hallo ..." startet
        def _strip_greeting_html(html: str) -> str:
            import re
            if not html:
                return html
            # Extended list of German greetings to remove
            greetings_pattern = (
                r'hallo|hi|hey|moin|servus|guten tag|guten morgen|guten abend|'
                r'sehr geehrte[rs]?|liebe[rs]?|grüß gott|grüezi|hallöchen'
            )
            # <p>...</p> Beginn mit gängigen Grußformeln entfernen (inkl. Name/E-Mail/Kommata)
            html = re.sub(rf'^\s*<p>\s*({greetings_pattern})[^<]*</p>\s*', '', html, flags=re.IGNORECASE)
            # Plaintext-Variante (ohne <p>) am Anfang
            html = re.sub(rf'^\s*({greetings_pattern})[^\n<]*\n+', '', html, flags=re.IGNORECASE)
            return html
        antwort_body = _strip_greeting_html(antwort_body)
        # Body als "leer" behandeln, wenn nach HTML->Text kaum Inhalt vorhanden ist
        _antwort_text = _html_to_text(antwort_body or '')
        _has_meaningful_body = bool(_antwort_text and len(_antwort_text.strip()) >= 8)
        # Antworten-HTML zusammensetzen:
        # - Wenn Preface vorhanden ist, KEIN weiterer Body anhängen (ist bereits die gewünschte Antwortform)
        has_preface = bool(visible_preface_html)
        if visible_preface_html:
            antwort_html = greeting_html + visible_preface_html
        else:
            # Wenn der LLM-Body leer ist (auch ohne Timeout), liefern wir 504 statt eines leeren Drafts mit nur "Hallo,"
            if not _has_meaningful_body:
                return jsonify({'error': 'compose_empty'}), 504
            body_html = _plaintext_to_html_email(antwort_body)
            antwort_html = greeting_html + body_html
        has_body = _has_meaningful_body
        # Draft ohne feste KI-Standardsignatur: nur der eigentliche Antworttext.
        # Die persönliche Signatur des Users wird erst beim Versand im Endpoint
        # /api/emails/send aus den Email-Einstellungen angehängt.
        draft_html = (
            "<!-- DRAFT-GENERATED -->\n"
            '<div style="font-family:Arial,sans-serif;font-size:1.08em;line-height:1.5;">'
            f"{antwort_html}"
            '</div>'
        )
        # Vorschlagsempfänger/Betreff
        reply_to = from_addr
        reply_subject = ("Re: " + subject) if subject and not subject.lower().startswith("re:") else (subject or "Antwort")
        # Bei Timeout ohne verwertbaren Body und ohne Preface -> 504 (zusätzlich oben schon für leere Bodies behandelt)
        if (timed_out and not visible_preface_html and not (antwort_body and antwort_body.strip())):
            return jsonify({'error': 'compose_timeout'}), 504
        # In Compose-Cache legen (Timeout-Drafts nicht für Early-Return verwenden)
        COMPOSE_CACHE[str(email_id)] = {
            'html': draft_html,
            'to': reply_to,
            'subject': reply_subject,
            'ts': now,
            'timed_out': timed_out,
            'has_body': has_body,
            'has_preface': has_preface,
        }
        return jsonify({ 'html': draft_html, 'to': reply_to, 'subject': reply_subject })
    except Exception as e:
        app.logger.error(f"[AGENT-COMPOSE] error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/emails/send', methods=['POST'])
@require_auth
def api_emails_send(current_user):
    """Versendet eine Mail (HTML). Request: { to, subject, html, account_id } """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    data = request.get_json(silent=True) or {}
    to_addr = data.get('to')
    subject = data.get('subject') or ''
    html = data.get('html') or ''
    account_id = data.get('account_id')
    if not to_addr or not html:
        return jsonify({'error': 'to und html sind erforderlich'}), 400
    
    # Get user-specific email account (multi-account support)
    user_email = current_user.get('user_email')
    if not account_id:
        return jsonify({'error': 'account_id erforderlich'}), 400
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, account_email, smtp_host, smtp_port, smtp_user, smtp_pass_encrypted, smtp_security "
            "FROM email_accounts WHERE user_email=%s AND id=%s AND is_active=1",
            (user_email, account_id)
        )
        settings = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if settings and settings.get('smtp_host'):
            from encryption_utils import decrypt_password
            smtp_host = settings['smtp_host']
            smtp_port = int(settings.get('smtp_port', 465))
            smtp_user = settings['smtp_user']
            smtp_pass = decrypt_password(settings['smtp_pass_encrypted']) if settings['smtp_pass_encrypted'] else ''
            smtp_security = (settings.get('smtp_security') or 'auto').lower()
            from_addr = settings.get('account_email') or smtp_user
        else:
            return jsonify({'error': 'Please configure email settings first'}), 400
    except Exception as e:
        app.logger.error(f"[Send] Error loading email account: {e}")
        return jsonify({'error': 'Email settings error'}), 400
    
    if not (smtp_host and smtp_user and smtp_pass):
        return jsonify({'error': 'SMTP configuration incomplete'}), 400
    
    app.logger.info(f"[Send] Attempting to send email to {to_addr} via {smtp_host}:{smtp_port} (security: {smtp_security})")
    
    # Optional: User-Signatur laden und in sauberes HTML-Layout einbetten
    try:
        conn_sig = get_settings_db_connection()
        cur_sig = conn_sig.cursor(dictionary=True)
        cur_sig.execute(
            "SELECT signature_html FROM user_email_settings WHERE user_email=%s",
            (user_email,),
        )
        row_sig = cur_sig.fetchone()
        cur_sig.close()
        conn_sig.close()
        signature_html = (row_sig or {}).get('signature_html') if row_sig else None
        if signature_html:
            # Signatur-Block; sorgt dafür, dass Bilder in der Signatur responsiv sind
            signature_block = (
                '<div style="border-top:1px solid #e5e7eb; margin-top:24px; padding-top:12px; font-size:13px; color:#4b5563;">'
                '<div style="max-width:100%;">'
                f"{signature_html}"
                '</div>'
                '</div>'
            )

            # Komplettes Mail-Layout (Karte mit Rand, Header, Inhalt, Footer)
            content_html = html
            html = (
                '<!DOCTYPE html>'
                '<html>'
                '<body style="margin:0; padding:0; background-color:#f3f4f6;">'
                '<div style="max-width:640px; margin:0 auto; padding:24px 16px;">'
                '<div style="background-color:#ffffff; border-radius:8px; border:1px solid #e5e7eb; '
                'padding:24px; font-family:Arial,sans-serif; font-size:14px; color:#111827; line-height:1.6;">'
                '<div style="font-size:11px; color:#6b7280; text-transform:uppercase; letter-spacing:0.12em; '
                'margin-bottom:16px;">Antwort</div>'
                f"{content_html}"
                f"{signature_block}"
                '<div style="margin-top:24px; font-size:11px; color:#9ca3af; border-top:1px dashed #e5e7eb; padding-top:8px;">'
                'Gesendet mit InboxIQ'
                '</div>'
                '</div>'
                '</div>'
                '</body>'
                '</html>'
            )
    except Exception as e:
        app.logger.warning(f"[Send] Could not load/apply signature: {e}")

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['To'] = to_addr
        part = MIMEText(html, 'html', 'utf-8')
        msg.attach(part)

        def _send_ssl():
            app.logger.debug(f"[Send] Trying SSL on {smtp_host}:{smtp_port}")
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=12) as server:
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [to_addr], msg.as_string())
            app.logger.info(f"[Send] Email sent successfully via SSL")

        def _send_starttls():
            # Use smtp_port from user settings, not env variable
            port_tls = smtp_port if smtp_security == 'starttls' else int(os.environ.get('SMTP_PORT_STARTTLS', '587'))
            app.logger.debug(f"[Send] Trying STARTTLS on {smtp_host}:{port_tls}")
            with smtplib.SMTP(smtp_host, port_tls, timeout=12) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [to_addr], msg.as_string())
            app.logger.info(f"[Send] Email sent successfully via STARTTLS")

        if smtp_security == 'ssl':
            _send_ssl()
        elif smtp_security == 'starttls':
            _send_starttls()
        else:
            # auto: Try both SSL and STARTTLS
            ssl_error = None
            try:
                _send_ssl()
            except Exception as e1:
                ssl_error = e1
                app.logger.warning(f"[SMTP] SSL (port {smtp_port}) failed: {e1}, trying STARTTLS...")
                try:
                    _send_starttls()
                except Exception as e2:
                    app.logger.error(f"[SMTP] STARTTLS also failed: {e2}")
                    # Raise the more specific error
                    raise e2
        return jsonify({'ok': True})
    except Exception as e:
        import socket, smtplib, ssl, traceback
        err_txt = f"{e}"
        code = 'smtp_error'
        status = 500
        # Typisierte Fehlerklassen mappen für bessere Diagnose im UI
        if isinstance(e, smtplib.SMTPAuthenticationError):
            code = 'smtp_auth'
        elif isinstance(e, smtplib.SMTPServerDisconnected):
            code = 'smtp_disconnected'
        elif isinstance(e, smtplib.SMTPRecipientsRefused):
            code = 'smtp_rcpt_refused'
        elif isinstance(e, smtplib.SMTPSenderRefused):
            code = 'smtp_sender_refused'
        elif isinstance(e, smtplib.SMTPDataError):
            code = 'smtp_data_error'
        elif isinstance(e, (socket.timeout, TimeoutError)):
            code = 'smtp_timeout'
        elif isinstance(e, socket.gaierror):
            code = 'smtp_dns'
        elif isinstance(e, ssl.SSLError):
            code = 'smtp_ssl'
        app.logger.error(f"[SMTP] send error ({code}): {err_txt}\n" + traceback.format_exc())
        return jsonify({'error': err_txt, 'code': code}), status


@app.route('/api/user/signature-image', methods=['POST'])
@require_auth
def api_user_signature_image(current_user):
    """Lädt ein Signaturbild für den aktuellen User hoch und gibt die URL zurück.

    Request (multipart/form-data): Feld 'file'
    Response: { ok: true, url: 'https://.../static/signatures/...' }
    """
    from werkzeug.utils import secure_filename

    user_email = current_user.get('user_email') or ''
    if 'file' not in request.files:
        return jsonify({'error': 'file fehlt'}), 400
    f = request.files['file']
    if not f or f.filename == '':
        return jsonify({'error': 'Leere Datei'}), 400

    # Einfacher Typ-/Größencheck
    allowed_mimes = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/jpg': '.jpg', 'image/gif': '.gif'}
    mime = (f.mimetype or '').lower()
    ext = allowed_mimes.get(mime)
    if not ext:
        return jsonify({'error': 'Nur PNG/JPEG/GIF erlaubt'}), 400

    # Größe begrenzen (~2 MB)
    f.stream.seek(0, os.SEEK_END)
    size = f.stream.tell()
    f.stream.seek(0)
    if size > 2 * 1024 * 1024:
        return jsonify({'error': 'Datei zu groß (max. 2 MB)'}), 400

    # Dateiname aus User-E-Mail ableiten
    base = secure_filename(user_email or 'signature') or 'signature'
    filename = f"{base}{ext}"
    sig_dir = os.path.join(app.root_path, 'static', 'signatures')
    try:
        os.makedirs(sig_dir, exist_ok=True)
        full_path = os.path.join(sig_dir, filename)
        f.save(full_path)
    except Exception as e:
        app.logger.error(f"[Signature-Upload] Fehler beim Speichern: {e}")
        return jsonify({'error': 'Fehler beim Speichern der Datei'}), 500

    # URL bauen (extern, inkl. Domain) – kann direkt in <img src> genutzt werden
    try:
        from flask import url_for as _url_for
        url = _url_for('static', filename=f'signatures/{filename}', _external=True)
    except Exception:
        url = f"/static/signatures/{filename}"

    return jsonify({'ok': True, 'url': url}), 200


@app.route('/api/emails/smtp-test', methods=['POST'])
@require_auth
def api_emails_smtp_test(current_user):
    """Test SMTP connection for a specific email account (multi-account)."""
    import smtplib
    from encryption_utils import decrypt_password

    user_email = current_user.get('user_email')
    data = request.get_json(silent=True) or {}
    account_id = data.get('account_id')
    if not account_id:
        return jsonify({'ok': False, 'error': 'account_id erforderlich'}), 400

    try:
        # SMTP-Settings aus email_accounts laden
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT smtp_host, smtp_port, smtp_user, smtp_pass_encrypted, smtp_security "
            "FROM email_accounts WHERE user_email=%s AND id=%s AND is_active=1",
            (user_email, account_id)
        )
        settings = cursor.fetchone()
        cursor.close()
        conn.close()

        if not settings or not settings.get('smtp_host'):
            return jsonify({'ok': False, 'error': 'Keine SMTP-Einstellungen für diesen Account gefunden'}), 400

        smtp_host = settings['smtp_host']
        smtp_port = int(settings.get('smtp_port', 465))
        smtp_user = settings['smtp_user']
        smtp_pass = decrypt_password(settings['smtp_pass_encrypted']) if settings['smtp_pass_encrypted'] else ''
        smtp_security = (settings.get('smtp_security') or 'auto').lower()

        if not (smtp_host and smtp_user and smtp_pass):
            return jsonify({'ok': False, 'error': 'SMTP-Konfiguration unvollständig'}), 400

        # Test connection
        test_result = {
            'host': smtp_host,
            'port': smtp_port,
            'user': smtp_user[:3] + '***' if smtp_user and len(smtp_user) > 3 else (smtp_user or ''),
            'security': smtp_security,
            'tests': []
        }

        def test_ssl():
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10) as server:
                server.login(smtp_user, smtp_pass)
            return True

        def test_starttls():
            port_tls = smtp_port if smtp_security == 'starttls' else 587
            with smtplib.SMTP(smtp_host, port_tls, timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_user, smtp_pass)
            return True

        # Run tests based on security mode
        if smtp_security == 'ssl':
            try:
                test_ssl()
                test_result['tests'].append({'method': 'SSL', 'success': True, 'message': f'Verbindung erfolgreich auf Port {smtp_port}'})
            except Exception as e:
                test_result['tests'].append({'method': 'SSL', 'success': False, 'message': str(e)})
                return jsonify({'ok': False, **test_result}), 500
        elif smtp_security == 'starttls':
            try:
                test_starttls()
                test_result['tests'].append({'method': 'STARTTLS', 'success': True, 'message': f'Verbindung erfolgreich auf Port {smtp_port}'})
            except Exception as e:
                test_result['tests'].append({'method': 'STARTTLS', 'success': False, 'message': str(e)})
                return jsonify({'ok': False, **test_result}), 500
        else:  # auto
            # Try SSL first
            ssl_success = False
            try:
                test_ssl()
                test_result['tests'].append({'method': 'SSL', 'success': True, 'message': f'Verbindung erfolgreich auf Port {smtp_port}'})
                ssl_success = True
            except Exception as e:
                test_result['tests'].append({'method': 'SSL', 'success': False, 'message': str(e)})

            # Try STARTTLS
            if not ssl_success:
                try:
                    test_starttls()
                    test_result['tests'].append({'method': 'STARTTLS', 'success': True, 'message': 'Verbindung erfolgreich auf Port 587'})
                except Exception as e:
                    test_result['tests'].append({'method': 'STARTTLS', 'success': False, 'message': str(e)})
                    return jsonify({'ok': False, **test_result}), 500

        return jsonify({'ok': True, **test_result}), 200

    except Exception as e:
        import traceback
        return jsonify({'ok': False, 'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/emails/sync', methods=['POST'])
@require_auth
def api_emails_sync(current_user):
    """Sync emails from IMAP to database.

    Body: { limit: 20, count_only: false, account_id, folder? }
    - limit: Anzahl der neu zu ladenden E-Mails (neueste zuerst)
    - count_only: wenn true, wird nur total_on_server gezählt
    - account_id: E-Mail-Account in email_accounts
    - folder: optionaler IMAP-Ordner (Default 'INBOX')
    """
    import imaplib, email
    from email.header import decode_header
    import re
    
    data = request.get_json(silent=True) or {}
    limit = data.get('limit')  # None = all new, 20/50/100 = specific count
    count_only = data.get('count_only', False)  # Just count emails on server
    account_id = data.get('account_id')
    # IMAP-Folder vom Client und logischen DB-Folder bestimmen
    raw_folder = (data.get('folder') or 'INBOX').strip() or 'INBOX'
    folder_imap = 'INBOX'
    folder_db_key = 'inbox'
    if isinstance(raw_folder, str):
        f = raw_folder.strip()
        # Kaputte Präfixe wie '." INBOX.Sent' säubern
        if f.startswith('."') or f.startswith('"'):
            f = f.lstrip('.').lstrip('"').strip()
        fu = f.upper()
        # Gesendet-Varianten
        if 'SENT' in fu:
            folder_imap = f or 'INBOX.Sent'
            folder_db_key = 'sent'
        # Archiv-Varianten
        elif 'ARCHIVE' in fu or 'ARCHIV' in fu:
            folder_imap = f or 'Archive'
            folder_db_key = 'archive'
        # Inbox-Varianten (auch wenn zusätzlich INBOX.* drinsteht)
        elif 'INBOX' in fu:
            folder_imap = 'INBOX'
            folder_db_key = 'inbox'
        else:
            # Fallback: letzten Pfadteil als Key verwenden
            lower = f.lower()
            last_part = lower.split('/')[-1].split('.')[-1]
            folder_imap = f or 'INBOX'
            folder_db_key = last_part or lower or 'inbox'
    else:
        folder_imap = 'INBOX'
        folder_db_key = 'inbox'
    
    user_email = current_user.get('user_email')
    if not account_id:
        return jsonify({'error': 'account_id erforderlich'}), 400
    
    try:
        # Get IMAP settings from selected email account
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, imap_host, imap_port, imap_user, imap_pass_encrypted, imap_security "
            "FROM email_accounts WHERE user_email=%s AND id=%s AND is_active=1",
            (user_email, account_id)
        )
        settings = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not settings or not settings.get('imap_host'):
            return jsonify({'error': 'IMAP settings not configured'}), 400
        
        from encryption_utils import decrypt_password
        host = settings['imap_host']
        port = int(settings.get('imap_port', 993))
        user = settings['imap_user']
        pw = decrypt_password(settings['imap_pass_encrypted']) if settings['imap_pass_encrypted'] else ''
        
        # Connect to IMAP
        M = imaplib.IMAP4_SSL(host, port, timeout=15)
        M.login(user, pw)
        # Ordner auswählen (Standard: INBOX)
        # Folder-Namen (folder_imap) wurde oben bereits normalisiert
        # Viele Server erwarten Foldernamen in Anführungszeichen, v.a. bei Leerzeichen
        try:
            try:
                sel_typ, _ = M.select(f'"{folder_imap}"')
            except imaplib.IMAP4.error as e1:
                # Fallback: ungequotete Variante versuchen
                app.logger.warning(f"[Sync] IMAP SELECT with quotes failed for folder={folder_imap!r}: {e1}")
                sel_typ, _ = M.select(folder_imap)
        except imaplib.IMAP4.error as e2:
            app.logger.error(f"[Sync] IMAP SELECT failed for folder={folder_imap!r}: {e2}")
            M.close()
            M.logout()
            return jsonify({'error': f"IMAP SELECT failed for folder {folder_imap!r}: {e2}"}), 500
        if sel_typ != 'OK':
            app.logger.error(f"[Sync] IMAP SELECT returned {sel_typ} for folder={folder_imap!r}")
            M.close()
            M.logout()
            return jsonify({'error': f"IMAP SELECT status {sel_typ} for folder {folder_imap!r}"}), 500
        
        # Search all emails
        typ, data = M.search(None, 'ALL')
        if typ != 'OK':
            M.close()
            M.logout()
            return jsonify({'error': 'IMAP search failed'}), 500
        
        all_uids = data[0].split()
        total_on_server = len(all_uids)
        
        # If just counting
        if count_only:
            M.close()
            M.logout()
            return jsonify({'total_on_server': total_on_server}), 200
        
        # Bereits synchronisierte Kombinationen aus message_id und Ordner laden,
        # damit dieselbe Nachricht in verschiedenen Ordnern (z.B. INBOX vs. Gesendet)
        # separat gespeichert werden kann.
        conn_db = get_settings_db_connection()
        cursor_db = conn_db.cursor()
        cursor_db.execute(
            "SELECT message_id, folder FROM emails WHERE user_email=%s AND account_id=%s",
            (user_email, account_id)
        )
        synced_rows = [(row[0], (row[1] or '').lower()) for row in cursor_db.fetchall() if row[0]]
        synced_ids = set(synced_rows)
        
        # Determine which emails to fetch
        if limit:
            # Anzahl bereits für diesen logischen Folder (folder_db_key) synchronisierter Nachrichten
            current_folder_key = (folder_db_key or 'inbox').lower()
            already_for_folder = sum(1 for _mid, f in synced_ids if f == current_folder_key)
            # Wir holen den nächsten Block "limit" älterer UIDs hinter den bereits synchronisierten
            # all_uids ist nach IMAP-Spezifikation von alt nach neu sortiert
            total_uids = len(all_uids)
            end_index = max(0, total_uids - already_for_folder)
            start_index = max(0, end_index - int(limit))
            uids_to_fetch = all_uids[start_index:end_index]
        else:
            # Fetch all (careful!)
            uids_to_fetch = all_uids
        
        synced_count = 0
        new_contacts_count = 0

        for uid in uids_to_fetch:
            try:
                # FLAGS gemeinsam mit der Nachricht laden, damit wir den Gelesen-Status (\Seen) auswerten können
                typ, msg_data = M.fetch(uid, '(FLAGS RFC822)')
                if typ != 'OK':
                    continue

                # msg_data[0] ist i.d.R. ein Tupel: (b'1 (FLAGS (..) RFC822 {bytes}', raw_bytes)
                tup = msg_data[0]
                if isinstance(tup, tuple):
                    meta_raw = tup[0].decode() if isinstance(tup[0], (bytes, bytearray)) else str(tup[0])
                    raw_email = tup[1]
                else:
                    meta_raw = ''
                    raw_email = tup

                # Gelesen-Status aus FLAGS extrahieren
                is_read = 1 if ('\\Seen' in meta_raw) else 0
                msg = email.message_from_bytes(raw_email)

                # Extract message_id
                message_id = msg.get('Message-ID', '').strip()
                if not message_id:
                    message_id = f"no-id-{uid.decode()}"

                # Skip, wenn diese Kombination aus message_id und Ziel-Ordner bereits in der DB vorhanden ist
                key = (message_id, (folder_db_key or 'inbox').lower())
                if key in synced_ids:
                    continue

                # Extract headers
                from_addr = msg.get('From', '')
                to_addrs = msg.get('To', '')
                subject = msg.get('Subject', '')
                date_str = msg.get('Date', '')

                # Decode headers
                def decode_header_value(value):
                    if not value:
                        return ''
                    parts = decode_header(value)
                    decoded = []
                    for content, encoding in parts:
                        if isinstance(content, bytes):
                            decoded.append(content.decode(encoding or 'utf-8', errors='ignore'))
                        else:
                            decoded.append(str(content))
                    return ' '.join(decoded)

                from_addr = decode_header_value(from_addr)
                subject = decode_header_value(subject)

                # Extract email address and name from "Name <email@example.com>"
                from_email = from_addr
                from_name = ''
                email_match = re.search(r'<(.+?)>', from_addr)
                if email_match:
                    from_email = email_match.group(1)
                    from_name = from_addr.split('<')[0].strip().strip('"')

                # Parse date
                from email.utils import parsedate_to_datetime
                try:
                    received_at = parsedate_to_datetime(date_str)
                except Exception:
                    received_at = datetime.now()

                # Extract body
                body_text = ''
                body_html = ''
                has_attachments = False

                if msg.is_multipart():
                    for part in msg.walk():
                        ctype = part.get_content_type()
                        if ctype == 'text/plain' and not body_text:
                            try:
                                payload = part.get_payload(decode=True)
                                body_text = payload.decode(part.get_content_charset() or 'utf-8', errors='ignore')
                            except Exception:
                                pass
                        elif ctype == 'text/html' and not body_html:
                            try:
                                payload = part.get_payload(decode=True)
                                body_html = payload.decode(part.get_content_charset() or 'utf-8', errors='ignore')
                            except Exception:
                                pass
                        elif part.get_filename():
                            has_attachments = True
                else:
                    try:
                        payload = msg.get_payload(decode=True)
                        if msg.get_content_type() == 'text/html':
                            body_html = payload.decode(msg.get_content_charset() or 'utf-8', errors='ignore')
                        else:
                            body_text = payload.decode(msg.get_content_charset() or 'utf-8', errors='ignore')
                    except Exception:
                        pass

                # Get or create contact
                cursor_db.execute(
                    "SELECT id FROM contacts WHERE user_email=%s AND contact_email=%s",
                    (user_email, from_email)
                )
                contact_row = cursor_db.fetchone()

                if contact_row:
                    contact_id = contact_row[0]
                    # Update contact stats
                    cursor_db.execute(
                        "UPDATE contacts SET email_count=email_count+1, last_contact_at=%s, "
                        "name=%s WHERE id=%s",
                        (received_at, from_name or from_email, contact_id)
                    )
                else:
                    # Create new contact
                    cursor_db.execute(
                        "INSERT INTO contacts (user_email, contact_email, name, first_name, "
                        "email_count, first_contact_at, last_contact_at) "
                        "VALUES (%s, %s, %s, %s, 1, %s, %s)",
                        (user_email, from_email, from_name or from_email, from_name.split()[0] if from_name else '',
                         received_at, received_at)
                    )
                    contact_id = cursor_db.lastrowid
                    new_contacts_count += 1

                # Insert email, Folder-Namen als logischen DB-Key speichern
                folder_db = (folder_db_key or 'inbox').lower()
                cursor_db.execute(
                    "INSERT INTO emails (message_id, user_email, account_id, contact_id, from_addr, from_name, "
                    "to_addrs, subject, body_text, body_html, received_at, folder, has_attachments, is_read) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (message_id, user_email, account_id, contact_id, from_email, from_name, to_addrs,
                     subject, body_text[:50000] if body_text else '', body_html[:100000] if body_html else '',
                     received_at, folder_db, has_attachments, is_read)
                )

                synced_count += 1
                synced_ids.add(key)

            except Exception as e:
                app.logger.error(f"[Sync] Error processing email {uid}: {e}")
                continue

        conn_db.commit()
        cursor_db.close()
        conn_db.close()
        
        M.close()
        M.logout()
        
        # Gesamtanzahl der bereits in der DB vorhandenen Kombinationen
        total_in_db = len(synced_ids)
        # Anzahl der bereits in der DB vorhandenen Mails NUR für den aktuellen Ordner
        current_folder_key = (folder_db_key or 'inbox').lower()
        total_in_db_folder = sum(1 for _mid, f in synced_rows if f == current_folder_key)

        return jsonify({
            'ok': True,
            'synced': synced_count,
            'total_on_server': total_on_server,
            'total_in_db': total_in_db,
            'total_in_db_folder': total_in_db_folder,
            'new_contacts': new_contacts_count,
            'already_synced': total_in_db - synced_count
        }), 200
        
    except Exception as e:
        app.logger.error(f"[Sync] Error: {e}")
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/email-folders', methods=['GET'])
@require_auth
def api_email_folders_compat(current_user):
    """Kompatibilitäts-Endpoint für ältere Frontend-Versionen.

    Ruft intern api_emails_folders auf, damit sowohl /api/emails/folders
    als auch /api/email-folders gültige Ordnerlisten liefern.
    """
    return api_emails_folders(current_user)


@app.route('/api/emails/folders', methods=['GET'])
@require_auth
def api_emails_folders(current_user):
    """Liest die IMAP-Ordnerstruktur für einen Account aus und gibt sie zurück.

    Query:
    - account_id (required)

    Response: {
      "folders": [
        {"imap_name": "INBOX", "db_key": "inbox", "label": "Posteingang"},
        ...
      ]
    }
    """
    import imaplib
    from encryption_utils import decrypt_password

    user_email = current_user.get('user_email')
    account_id = request.args.get('account_id', type=int)
    if not account_id:
        return jsonify({'error': 'account_id erforderlich'}), 400

    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT imap_host, imap_port, imap_user, imap_pass_encrypted, imap_security "
            "FROM email_accounts WHERE user_email=%s AND id=%s AND is_active=1",
            (user_email, account_id),
        )
        settings = cursor.fetchone()
        cursor.close()
        conn.close()

        if not settings or not settings.get('imap_host'):
            return jsonify({'error': 'IMAP settings not configured'}), 400

        host = settings['imap_host']
        port = int(settings.get('imap_port', 993))
        user = settings['imap_user']
        pw = decrypt_password(settings['imap_pass_encrypted']) if settings['imap_pass_encrypted'] else ''

        M = imaplib.IMAP4_SSL(host, port, timeout=15)
        M.login(user, pw)
        typ, data = M.list()
        if typ != 'OK':
            M.logout()
            return jsonify({'error': 'IMAP LIST failed'}), 500

        folders = []
        for raw in data:
            if not raw:
                continue
            # raw ist z.B. b'(\HasNoChildren) "/" "INBOX"'
            try:
                line = raw.decode('utf-8', errors='ignore')
            except Exception:
                continue
            # Name steht typischerweise in den letzten Anführungszeichen
            parts = line.split(' "')
            if len(parts) < 2:
                continue
            name = parts[-1].rstrip('"')
            if not name:
                continue

            imap_name = name

            # Label und db_key heuristisch bestimmen
            lower_name = (imap_name or 'INBOX').lower()
            # Nur den letzten Pfadteil betrachten (INBOX/Sent -> Sent)
            last_part = lower_name.split('/')[-1].split('.')[-1]

            # Logischer Typ und db_key bestimmen (stabil für Deduplizierung)
            logical_type = None
            if 'inbox' in last_part:
                logical_type = 'inbox'
            elif 'sent' in last_part or 'gesendet' in last_part:
                logical_type = 'sent'
            elif 'archive' in last_part or 'archiv' in last_part:
                logical_type = 'archive'
            elif 'draft' in last_part or 'entwurf' in last_part:
                logical_type = 'drafts'
            elif 'spam' in last_part or 'junk' in last_part:
                logical_type = 'spam'
            elif 'trash' in last_part or 'deleted' in last_part or 'papierkorb' in last_part:
                logical_type = 'trash'

            # db_key: stabiler Ordner-Key, passend zu unserer DB-Speicherung
            if logical_type is not None:
                db_key = logical_type
            else:
                db_key = last_part or lower_name

            # Label für die UI bestimmen
            if logical_type == 'inbox':
                label = 'Posteingang'
            elif logical_type == 'sent':
                label = 'Gesendet'
            elif logical_type == 'drafts':
                label = 'Entwürfe'
            elif logical_type == 'spam':
                label = 'Spam'
            elif logical_type == 'trash':
                label = 'Papierkorb'
            elif logical_type == 'archive':
                label = 'Archiv'
            else:
                # Originalnamen verwenden
                label = imap_name

            folders.append({
                'imap_name': imap_name,
                'db_key': db_key,
                'label': label,
            })

        M.logout()

        # Deduplizieren: pro logischem Ordner nur einen Eintrag behalten
        unique_folders = []
        seen = set()
        for f in folders:
            # Für Standardordner (inbox/sent/archive/drafts/trash/spam) nur
            # einen Eintrag behalten, egal wie viele IMAP-Varianten es gibt.
            db_key = (f.get('db_key') or '').lower()
            label = (f.get('label') or '').lower()
            if db_key in {'inbox', 'sent', 'archive', 'drafts', 'trash', 'spam'}:
                key = ('std', db_key)
            else:
                key = (db_key, label)
            if key in seen:
                continue
            seen.add(key)
            unique_folders.append(f)

        # Optional: nach gängigen Ordnern sortieren (Inbox, Sent, Archiv, Rest alphabetisch)
        priority = {'posteingang': 0, 'inbox': 0, 'gesendet': 1, 'sent': 1, 'archive': 2, 'archiv': 2}

        def sort_key(f):
            lp = f['label'].lower()
            return (priority.get(lp, 10), lp)

        folders_sorted = sorted(unique_folders, key=sort_key)

        return jsonify({'folders': folders_sorted}), 200

    except Exception as e:
        app.logger.error(f"[IMAP Folders] Error: {e}")
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/emails/list', methods=['GET'])
@require_auth
def api_emails_list(current_user):
    """Get emails from database.

    Query params:
    - folder: Ordner in der emails-Tabelle (z.B. 'inbox', 'sent', 'archive') oder 'all' für alle Ordner
    - limit, offset
    - account_id
    """
    user_email = current_user.get('user_email')
    folder = request.args.get('folder', 'inbox')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    account_id = request.args.get('account_id', type=int)
    if not account_id:
        return jsonify({'error': 'account_id erforderlich'}), 400
    
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Get emails with contact info
        if folder == 'all':
            cursor.execute(
                """
                SELECT e.id, e.message_id, e.from_addr, e.from_name, e.to_addrs, e.subject,
                       e.body_text, e.body_html, e.received_at, e.folder, e.is_read, e.starred,
                       e.has_attachments, c.name as contact_name, c.contact_email, c.email_count as contact_email_count
                FROM emails e
                LEFT JOIN contacts c ON e.contact_id = c.id
                WHERE e.user_email = %s AND e.account_id = %s
                ORDER BY e.received_at DESC
                LIMIT %s OFFSET %s
                """,
                (user_email, account_id, limit, offset)
            )
        else:
            # Für bestimmte Folder (z.B. 'sent') auch historische Varianten mit berücksichtigen
            if folder == 'sent':
                folder_values = ('sent', 'inbox.sent', 'sent items')
                cursor.execute(
                    """
                    SELECT e.id, e.message_id, e.from_addr, e.from_name, e.to_addrs, e.subject,
                           e.body_text, e.body_html, e.received_at, e.folder, e.is_read, e.starred,
                           e.has_attachments, c.name as contact_name, c.contact_email, c.email_count as contact_email_count
                    FROM emails e
                    LEFT JOIN contacts c ON e.contact_id = c.id
                    WHERE e.user_email = %s AND e.account_id = %s AND e.folder IN (%s, %s, %s)
                    ORDER BY e.received_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (user_email, account_id, *folder_values, limit, offset)
                )
            else:
                cursor.execute(
                    """
                    SELECT e.id, e.message_id, e.from_addr, e.from_name, e.to_addrs, e.subject,
                           e.body_text, e.body_html, e.received_at, e.folder, e.is_read, e.starred,
                           e.has_attachments, c.name as contact_name, c.contact_email, c.email_count as contact_email_count
                    FROM emails e
                    LEFT JOIN contacts c ON e.contact_id = c.id
                    WHERE e.user_email = %s AND e.account_id = %s AND e.folder = %s
                    ORDER BY e.received_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (user_email, account_id, folder, limit, offset)
                )
        emails = cursor.fetchall()
        
        # Get total count (abhängig von folder/all)
        if folder == 'all':
            cursor.execute(
                "SELECT COUNT(*) as total FROM emails WHERE user_email=%s AND account_id=%s",
                (user_email, account_id)
            )
        else:
            if folder == 'sent':
                folder_values = ('sent', 'inbox.sent', 'sent items')
                cursor.execute(
                    "SELECT COUNT(*) as total FROM emails WHERE user_email=%s AND account_id=%s AND folder IN (%s, %s, %s)",
                    (user_email, account_id, *folder_values)
                )
            else:
                cursor.execute(
                    "SELECT COUNT(*) as total FROM emails WHERE user_email=%s AND account_id=%s AND folder=%s",
                    (user_email, account_id, folder)
                )
        total = cursor.fetchone()['total']
        
        # Check if any emails exist at all (to know if sync is needed)
        cursor.execute(
            "SELECT COUNT(*) as total FROM emails WHERE user_email=%s AND account_id=%s",
            (user_email, account_id)
        )
        total_all_folders = cursor.fetchone()['total']
        
        # Check if user has email settings (to know if we can sync more)
        cursor.execute(
            "SELECT id FROM email_accounts WHERE user_email=%s AND id=%s AND is_active=1 AND imap_host IS NOT NULL",
            (user_email, account_id)
        )
        has_imap_settings = cursor.fetchone() is not None
        
        cursor.close()
        conn.close()
        
        # Format emails for frontend
        formatted_emails = []
        for email_row in emails:
            formatted_emails.append({
                'id': email_row['id'],
                'uid': str(email_row['id']),  # Use DB id as uid for compatibility
                'from': email_row['from_name'] or email_row['from_addr'],
                'from_addr': email_row['from_addr'],
                'subject': email_row['subject'] or '(Kein Betreff)',
                'date': email_row['received_at'].strftime('%d.%m.%Y %H:%M') if email_row['received_at'] else '',
                'body_preview': (email_row['body_text'] or '')[:200],
                'is_read': email_row['is_read'],
                'starred': email_row['starred'],
                'has_attachments': email_row['has_attachments'],
                'contact_name': email_row['contact_name'],
                'contact_email': email_row['contact_email'],
                'contact_email_count': email_row['contact_email_count']
            })
        
        return jsonify({
            'emails': formatted_emails,
            'total': total,
            'total_all_folders': total_all_folders,
            'has_more': (offset + limit) < total,  # More in DB
            'can_sync_more': has_imap_settings  # Can check server for more
        }), 200
        
    except Exception as e:
        app.logger.error(f"[List Emails] Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/emails/debug-folders', methods=['GET'])
def api_emails_debug_folders():
    """Gibt für einen Account die in der DB vorhandenen Folder-Werte samt Anzahl zurück.

    Hilft beim Debuggen, unter welchem Folder-Key z.B. gesendete Mails gespeichert sind.
    """
    user_email = request.args.get('user_email')
    account_id = request.args.get('account_id', type=int)
    if not account_id:
        return jsonify({'error': 'account_id erforderlich'}), 400
    
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT COALESCE(folder, '') AS folder, COUNT(*) AS cnt
            FROM emails
            WHERE user_email=%s AND account_id=%s
            GROUP BY COALESCE(folder, '')
            ORDER BY cnt DESC
            """,
            (user_email, account_id)
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({'folders': rows})
    except Exception as e:
        app.logger.error(f"[Emails Debug Folders] Error: {e}")
        return jsonify({'error': 'Error loading debug folders'}), 500


@app.route('/api/emails/get/<int:email_id>', methods=['GET'])
@require_auth
def api_emails_get(current_user, email_id):
    """Get single email by ID from database"""
    user_email = current_user.get('user_email')
    
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute(
            """
            SELECT e.*, c.name as contact_name, c.contact_email, c.email_count as contact_email_count,
                   c.profile_summary, c.salutation, c.sentiment, c.email_length_preference,
                   c.communication_frequency, c.category
            FROM emails e
            LEFT JOIN contacts c ON e.contact_id = c.id
            WHERE e.id = %s AND e.user_email = %s
            """,
            (email_id, user_email)
        )
        email_row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not email_row:
            return jsonify({'error': 'Email not found'}), 404
        
        return jsonify({
            'id': email_row['id'],
            'from': email_row['from_name'] or email_row['from_addr'],
            'from_addr': email_row['from_addr'],
            'to': email_row['to_addrs'],
            'subject': email_row['subject'] or '(Kein Betreff)',
            'date': email_row['received_at'].strftime('%d.%m.%Y %H:%M') if email_row['received_at'] else '',
            'body_html': email_row['body_html'] or '',
            'body_text': email_row['body_text'] or '',
            'has_attachments': email_row['has_attachments'],
            'contact_name': email_row['contact_name'],
            'contact_email': email_row['contact_email'],
            'contact_email_count': email_row['contact_email_count'] or 1,
            'contact_id': email_row.get('contact_id'),
            'profile_summary': email_row.get('profile_summary', ''),
            'kpis': {
                'salutation': email_row.get('salutation'),
                'sentiment': email_row.get('sentiment'),
                'email_length_preference': email_row.get('email_length_preference'),
                'communication_frequency': email_row.get('communication_frequency'),
                'category': email_row.get('category')
            }
        }), 200
        
    except Exception as e:
        app.logger.error(f"[Get Email] Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/contacts/list', methods=['GET'])
@require_auth
def api_contacts_list(current_user):
    """Get all contacts for current user"""
    user_email = current_user.get('user_email')
    search = request.args.get('search', '').strip()
    
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        if search:
            # Search by name or email
            cursor.execute(
                """
                SELECT id, contact_email, name, first_name, email_count, 
                       first_contact_at, last_contact_at
                FROM contacts
                WHERE user_email = %s AND (name LIKE %s OR contact_email LIKE %s)
                ORDER BY last_contact_at DESC
                LIMIT 100
                """,
                (user_email, f'%{search}%', f'%{search}%')
            )
        else:
            # Get all contacts
            cursor.execute(
                """
                SELECT id, contact_email, name, first_name, email_count, 
                       first_contact_at, last_contact_at
                FROM contacts
                WHERE user_email = %s
                ORDER BY last_contact_at DESC
                LIMIT 100
                """,
                (user_email,)
            )
        
        contacts = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Format for frontend
        formatted = []
        for c in contacts:
            formatted.append({
                'id': c['id'],
                'name': c['name'] or c['contact_email'],
                'email': c['contact_email'],
                'email_count': c['email_count'],
                'first_contact': c['first_contact_at'].strftime('%d.%m.%Y') if c['first_contact_at'] else '–',
                'last_contact': c['last_contact_at'].strftime('%d.%m.%Y %H:%M') if c['last_contact_at'] else '–'
            })
        
        return jsonify({'contacts': formatted, 'total': len(formatted)}), 200
        
    except Exception as e:
        app.logger.error(f"[List Contacts] Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/contacts/<int:contact_id>/emails', methods=['GET'])
@require_auth
def api_contacts_emails(current_user, contact_id):
    """Get all emails from a specific contact"""
    user_email = current_user.get('user_email')
    
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Verify contact belongs to user
        cursor.execute(
            "SELECT id, name, contact_email, email_count FROM contacts WHERE id=%s AND user_email=%s",
            (contact_id, user_email)
        )
        contact = cursor.fetchone()
        
        if not contact:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Contact not found'}), 404
        
        # Get all emails from this contact
        cursor.execute(
            """
            SELECT id, subject, body_text, received_at, is_read, has_attachments
            FROM emails
            WHERE contact_id = %s AND user_email = %s
            ORDER BY received_at DESC
            """,
            (contact_id, user_email)
        )
        emails = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Format emails
        formatted_emails = []
        for e in emails:
            formatted_emails.append({
                'id': e['id'],
                'subject': e['subject'] or '(Kein Betreff)',
                'preview': (e['body_text'] or '')[:150],
                'date': e['received_at'].strftime('%d.%m.%Y %H:%M') if e['received_at'] else '',
                'is_read': e['is_read'],
                'has_attachments': e['has_attachments']
            })
        
        return jsonify({
            'contact': {
                'id': contact['id'],
                'name': contact['name'],
                'email': contact['contact_email'],
                'email_count': contact['email_count']
            },
            'emails': formatted_emails
        }), 200
        
    except Exception as e:
        app.logger.error(f"[Contact Emails] Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/contacts/<int:contact_id>/notes', methods=['GET'])
@require_auth
def api_contacts_notes_list(current_user, contact_id):
    """Get notes for a specific contact"""
    user_email = current_user.get('user_email')
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Verify contact belongs to user
        cursor.execute(
            "SELECT id FROM contacts WHERE id=%s AND user_email=%s",
            (contact_id, user_email)
        )
        contact = cursor.fetchone()
        if not contact:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Contact not found'}), 404

        cursor.execute(
            """
            SELECT id, note_text, created_at
            FROM contact_notes
            WHERE contact_id = %s AND user_email = %s
            ORDER BY created_at DESC
            """,
            (contact_id, user_email)
        )
        notes = cursor.fetchall()
        cursor.close()
        conn.close()

        formatted = [
            {
                'id': n['id'],
                'text': n['note_text'],
                'created_at': n['created_at'].strftime('%d.%m.%Y %H:%M') if n['created_at'] else ''
            }
            for n in notes
        ]

        return jsonify({'notes': formatted}), 200
    except Exception as e:
        app.logger.error(f"[Contact Notes List] Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/contacts/<int:contact_id>/notes', methods=['POST'])
@require_auth
def api_contacts_notes_create(current_user, contact_id):
    """Create a new note for a contact"""
    user_email = current_user.get('user_email')
    data = request.get_json(silent=True) or {}
    text = (data.get('text') or '').strip()
    if not text:
        return jsonify({'error': 'Notiz darf nicht leer sein'}), 400

    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Verify contact belongs to user
        cursor.execute(
            "SELECT id FROM contacts WHERE id=%s AND user_email=%s",
            (contact_id, user_email)
        )
        contact = cursor.fetchone()
        if not contact:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Contact not found'}), 404

        cursor.execute(
            """
            INSERT INTO contact_notes (contact_id, user_email, note_text, created_at)
            VALUES (%s, %s, %s, NOW())
            """,
            (contact_id, user_email, text)
        )
        conn.commit()
        note_id = cursor.lastrowid
        cursor.close()
        conn.close()

        return jsonify({'ok': True, 'id': note_id}), 201
    except Exception as e:
        app.logger.error(f"[Contact Notes Create] Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/contacts/<int:contact_id>/notes/<int:note_id>', methods=['DELETE'])
@require_auth
def api_contacts_notes_delete(current_user, contact_id, note_id):
    """Delete a note for a contact (soft permission check by user_email + contact)."""
    user_email = current_user.get('user_email')
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Verify note belongs to this user + contact
        cursor.execute(
            "SELECT id FROM contact_notes WHERE id=%s AND contact_id=%s AND user_email=%s",
            (note_id, contact_id, user_email),
        )
        note = cursor.fetchone()
        if not note:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Note not found'}), 404
        cursor.execute(
            "DELETE FROM contact_notes WHERE id=%s AND contact_id=%s AND user_email=%s",
            (note_id, contact_id, user_email),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True}), 200
    except Exception as e:
        app.logger.error(f"[Contact Notes Delete] Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/contacts/<int:contact_id>/generate-profile', methods=['POST'])
@require_auth
def api_contacts_generate_profile(current_user, contact_id):
    """Generate AI profile summary for a contact"""
    user_email = current_user.get('user_email')
    
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Verify contact belongs to user
        cursor.execute(
            "SELECT id, name, contact_email FROM contacts WHERE id=%s AND user_email=%s",
            (contact_id, user_email)
        )
        contact = cursor.fetchone()
        
        if not contact:
            cursor.close()
            conn.close()
            return jsonify({'error': 'Contact not found'}), 404
        
        # Manuelle Kontakt-Notizen laden (wichtigste Quelle für das Profil)
        cursor.execute(
            """
            SELECT note_text, created_at
            FROM contact_notes
            WHERE contact_id = %s AND user_email = %s
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (contact_id, user_email),
        )
        notes_rows = cursor.fetchall()

        notes_lines = []
        if notes_rows:
            for n in notes_rows:
                ts = n['created_at'].strftime('%d.%m.%Y %H:%M') if n['created_at'] else ''
                notes_lines.append(f"- ({ts}) {n['note_text']}")
        notes_context = "\n".join(notes_lines) if notes_lines else "(Keine Notizen hinterlegt)"
        
        # Get all emails from this contact (including from/to info for KPI calculation)
        cursor.execute(
            """
            SELECT subject, body_text, body_html, received_at, from_addr, to_addrs
            FROM emails 
            WHERE contact_id = %s AND user_email = %s 
            ORDER BY received_at DESC
            LIMIT 50
            """,
            (contact_id, user_email)
        )
        emails = cursor.fetchall()
        
        if not emails:
            cursor.close()
            conn.close()
            return jsonify({'error': 'No emails found for this contact'}), 404
        
        # Build email context (limit to avoid token overflow)
        email_texts = []
        for e in emails:
            date_str = e['received_at'].strftime('%d.%m.%Y') if e['received_at'] else ''
            body = (e['body_text'] or '')[:500]  # Limit each email to 500 chars
            email_texts.append(f"[{date_str}] Betreff: {e['subject']}\n{body}")
        
        email_context = "\n\n".join(email_texts)
        
        # Generate profile with GPT. WICHTIG: Manuelle Notizen haben Priorität.
        prompt = f"""Analysiere die folgenden Informationen zu einem Kontakt und erstelle ein prägnantes, praxisnahes Kontaktprofil.

Kontakt: {contact['name']} ({contact['contact_email']})

1) Manuell gepflegte Kontakt-Notizen (vom Nutzer, HÖCHSTE Priorität):
{notes_context}

2) E-Mail-Historie (zusätzlicher Kontext aus {len(emails)} E-Mails):
{email_context}

WICHTIG:
- Wenn Aussagen in den Notizen und in den E-Mails widersprüchlich sind, VERTRAUE den Notizen.
- Nutze die Notizen als wichtigste Quelle für das Profil und ergänze sie nur mit Details aus den E-Mails.
- Identifiziere explizit die aktuellsten Themen/Projekte (basierend auf den letzten E-Mails und Notizen) und erkenne offene Punkte oder noch nicht abgeschlossene Themen.

Formatiere die Antwort mit klarer Struktur:
- Nutze **Fettschrift** für Überschriften (z.B. **Wer ist dieser Kontakt:**)
- Nutze Absätze (doppelte Zeilenumbrüche)
- Nutze • oder - für Listen
- Gliedere in diese 7 Bereiche:

1. **Wer ist dieser Kontakt?** (Rolle, Bedürfnisse, Kontext, Hintergrund)
2. **Hauptanliegen & wiederkehrende Themen:** (Welche Themen, Probleme oder Projekte tauchen immer wieder auf?)
3. **Aktuellstes Thema / Projekt:** (Worum geht es im Moment konkret? Kurze Zusammenfassung des letzten relevanten Themas.)
4. **Offene Punkte & ungelöste Probleme:** (Was wirkt noch nicht abgeschlossen? Welche Fragen oder To-Dos sind noch offen?)
5. **Kommunikationsstil & Verhalten:**
6. **Besonderheiten & Muster:**
7. **Empfehlungen für zukünftige Kommunikation:** (Wie sollte man diesen Kontakt am besten ansprechen und was sollte man im nächsten Schritt tun?)

Sei präzise, geschäftlich und hilfreich. Max 220 Wörter."""
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Du bist ein CRM-Analyst, der Kundenprofile erstellt."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=400
        )
        
        summary = response.choices[0].message.content

        # Zweiter KI-Call: konkrete Themen als JSON für contact_topics extrahieren
        import json
        topics_payload = {
            "notes": notes_context,
            "emails": email_context,
        }
        topics_prompt = (
            "Analysiere die folgenden Notizen und E-Mails zu einem Kontakt. "
            "Extrahiere daraus eine kleine Liste konkreter Themen/Projekte als kompaktes JSON. "
            "Die Topic-Labels sollen aussagekräftige, aber nicht übertriebene Sätze oder Halbsätze sein, "
            "die möglichst Firma/Marke, Art des Vorgangs (z.B. Angebot, Buchung, Rechnung), Ort/Datum "
            "oder besondere Stichworte aus Betreff/Text enthalten. "
            "Nutze NUR Informationen, die im Betreff, Text oder in den Notizen vorkommen. Wenn Details "
            "wie Ort oder Datum fehlen, formuliere neutral (z.B. 'Kunde hat Workshop gebucht, Status unklar'). "
            "Allgemeine Labels wie 'Anfrage' oder 'Rechnung' sollen vermieden werden, wenn du sie mit ein paar "
            "Wörtern aus Betreff/Notizen präzisieren kannst (z.B. 'Rechnung für Job bei Firma X im Dezember'). "
            "Wenn du keine perfekten Informationen hast, erstelle trotzdem 3-6 sinnvolle, vorsichtig formulierte Themen, "
            "die das Geschehen grob zusammenfassen. Erfinde aber keine konkreten Orte, Daten oder Firmennamen. "
            "Fasse sehr ähnliche E-Mails zu einem gemeinsamen Thema zusammen und erzeuge höchstens 8 Themen.\n\n"
            "Gib das Ergebnis STRICT als JSON im folgenden Format zurück, ohne zusätzliche Erklärungen:\n\n"
            "{\n"
            "  \"topics\": [\n"
            "    {\n"
            "      \"label\": \"...\",\n"
            "      \"topic_type\": \"project|problem|general\",\n"
            "      \"status\": \"open|in_progress|done\",\n"
            "      \"last_mentioned_at\": \"YYYY-MM-DD\"\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Wenn du keine sinnvollen Themen findest, gib {\"topics\": []} zurück."
        )

        topics_response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Du extrahierst strukturierte Themenlisten als JSON für ein CRM."},
                {"role": "user", "content": topics_prompt + "\n\nDaten:\n" + json.dumps(topics_payload)[:6000]},
            ],
            temperature=0.2,
            max_tokens=400,
        )

        raw_topics = topics_response.choices[0].message.content or "{}"
        topics = []
        try:
            parsed = json.loads(raw_topics)
            topics = parsed.get("topics") or []
        except Exception as _:
            topics = []

        # Fallback: Wenn der KI-Call keine Topics geliefert hat, baue 3-5 einfache
        # Themen aus den letzten Betreffzeilen, damit im UI etwas sichtbar ist.
        if not topics:
            fallback_subjects = []
            seen_subj = set()
            for e in emails[:10]:
                subj = (e.get("subject") or "").strip()
                if not subj:
                    continue
                key = subj.lower()
                if key in seen_subj:
                    continue
                seen_subj.add(key)
                fallback_subjects.append(subj)
                if len(fallback_subjects) >= 5:
                    break

            topics = [
                {
                    "label": s,
                    "topic_type": "general",
                    "status": "in_progress",
                    "last_mentioned_at": emails[idx]["received_at"].strftime("%Y-%m-%d")
                    if emails[idx].get("received_at")
                    else None,
                }
                for idx, s in enumerate(fallback_subjects)
            ]

        # Bestehende Topics für diesen Kontakt löschen und neue speichern
        try:
            cursor.execute(
                "DELETE FROM contact_topics WHERE user_email=%s AND contact_id=%s",
                (user_email, contact_id),
            )
            for t in topics:
                label = (t.get("label") or "").strip()
                if not label:
                    continue
                topic_type = (t.get("topic_type") or None)
                status = (t.get("status") or None)
                last_date_str = (t.get("last_mentioned_at") or "").strip()
                last_dt = None
                if last_date_str:
                    from datetime import datetime as _dt
                    try:
                        last_dt = _dt.strptime(last_date_str, "%Y-%m-%d")
                    except Exception:
                        last_dt = None
                cursor.execute(
                    """
                    INSERT INTO contact_topics
                        (user_email, contact_id, topic_label, topic_type, status, first_mentioned_at, last_mentioned_at, raw_source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_email,
                        contact_id,
                        label,
                        topic_type,
                        status,
                        last_dt,
                        last_dt,
                        raw_topics[:1000],
                    ),
                )
            conn.commit()
        except Exception as e_topics:
            app.logger.error(f"[Contact Topics] Error while saving topics: {e_topics}")

        # Calculate KPIs
        def calculate_kpis(emails_list, contact_email, user_email_addr):
            """Calculate various KPIs from email history"""
            import re
            from datetime import datetime
            
            kpis = {
                'salutation': None,
                'sentiment': None,
                'email_length_preference': None,
                'avg_response_time_hours': None,
                'communication_frequency': None,
                'category': None,
            }
            
            # 1. Salutation (Sie/Du) - analyze emails TO the contact
            du_count = 0
            sie_count = 0
            for em in emails_list:
                # Check if this is FROM user (sent to contact)
                is_from_user = user_email_addr in (em.get('from_addr') or '')
                if is_from_user:
                    text = ((em.get('body_text') or '') + (em.get('body_html') or '')).lower()
                    du_count += len(re.findall(r'\b(du|dir|dein|deine)\b', text))
                    sie_count += len(re.findall(r'\b(sie|ihnen|ihr|ihre)\b', text))

            # Entscheidung mit Toleranz: Du/Sie nur bei klarem Vorsprung
            if du_count == 0 and sie_count == 0:
                kpis['salutation'] = 'Unklar'
            else:
                # leichte Gewichtung: mindestens 20 % Vorsprung oder mind. 3 absolute Treffer Differenz
                if du_count >= sie_count * 1.2 or (du_count - sie_count) >= 3:
                    kpis['salutation'] = 'Du'
                elif sie_count >= du_count * 1.2 or (sie_count - du_count) >= 3:
                    kpis['salutation'] = 'Sie'
                else:
                    kpis['salutation'] = 'Unklar'
            
            # 2. Sentiment - analyze recent emails FROM contact
            positive_words = ['danke', 'super', 'perfekt', 'toll', 'freue', 'gerne', 'prima', 'exzellent', 'großartig']
            negative_words = ['problem', 'fehler', 'nicht', 'leider', 'ärger', 'schlecht', 'unzufrieden', 'beschwerde']
            
            positive_score = 0
            negative_score = 0
            for em in emails_list[:10]:  # Last 10 emails
                is_from_contact = contact_email in (em.get('from_addr') or '')
                if is_from_contact:
                    text = ((em.get('body_text') or '') + (em.get('body_html') or '')).lower()
                    positive_score += sum(1 for word in positive_words if word in text)
                    negative_score += sum(1 for word in negative_words if word in text)
            
            if positive_score > negative_score * 1.5:
                kpis['sentiment'] = 'positive'
            elif negative_score > positive_score * 1.5:
                kpis['sentiment'] = 'negative'
            else:
                kpis['sentiment'] = 'neutral'
            
            # 3. Email length preference - average length
            lengths = []
            for em in emails_list[:20]:
                # Prefer plain text; if empty, fallback to stripped HTML
                text = em.get('body_text') or ''
                if not text:
                    html = em.get('body_html') or ''
                    if html:
                        # very lightweight HTML tag stripper
                        import re
                        text = re.sub(r'<[^>]+>', '', html)
                if text:
                    lengths.append(len(text))
            
            if lengths:
                avg_len = sum(lengths) / len(lengths)
                if avg_len < 300:
                    kpis['email_length_preference'] = 'short'
                elif avg_len < 800:
                    kpis['email_length_preference'] = 'medium'
                else:
                    kpis['email_length_preference'] = 'long'
            
            # 4. Communication frequency
            if len(emails_list) > 1:
                first_date = emails_list[-1].get('received_at')
                last_date = emails_list[0].get('received_at')
                if first_date and last_date:
                    days_diff = (last_date - first_date).days
                    if days_diff > 0:
                        emails_per_day = len(emails_list) / days_diff
                        if emails_per_day > 0.5:
                            kpis['communication_frequency'] = 'daily'
                        elif emails_per_day > 0.14:
                            kpis['communication_frequency'] = 'weekly'
                        elif emails_per_day > 0.03:
                            kpis['communication_frequency'] = 'monthly'
                        else:
                            kpis['communication_frequency'] = 'rare'
            
            # 5. Grobe Kontakt-Kategorie (nur Heuristik, kein hartes CRM-Feld)
            try:
                contact_email_l = (contact_email or '').lower()
                user_email_l = (user_email_addr or '').lower()
                contact_domain = contact_email_l.split('@')[-1] if '@' in contact_email_l else ''
                user_domain = user_email_l.split('@')[-1] if '@' in user_email_l else ''

                # Newsletter / Spam-Heuristik überwiegend aus Absenderadresse
                newsletter_like = any(pat in contact_email_l for pat in [
                    'newsletter', 'news@', 'no-reply', 'noreply', 'mailer@', 'bounce@'
                ])

                # Nutzungsfrequenz erneut berechnen (robust, falls oben nicht gesetzt)
                emails_per_day = None
                if len(emails_list) > 1:
                    first_date = emails_list[-1].get('received_at')
                    last_date = emails_list[0].get('received_at')
                    if first_date and last_date:
                        days_diff = max(1, (last_date - first_date).days)
                        emails_per_day = len(emails_list) / days_diff if days_diff > 0 else None

                # Entscheidungslogik
                if newsletter_like:
                    kpis['category'] = 'Spam/Werbung'
                elif contact_domain and user_domain and contact_domain == user_domain:
                    # Gleiche Domain wie der User → sehr wahrscheinlich Kollege/Mitarbeiter
                    kpis['category'] = 'Kollege/Mitarbeiter'
                elif emails_per_day is not None and emails_per_day > 0.2:
                    # Regelmäßiger Kontakt, keine Newsletter-Muster
                    kpis['category'] = 'Kunde (aktiv)'
                elif len(emails_list) >= 3:
                    # Mehrere Mails, aber seltener → normaler Kunde
                    kpis['category'] = 'Kunde'
                else:
                    kpis['category'] = 'Unklar'
            except Exception:
                # Heuristik ist nur Zusatz-Info – bei Fehlern neutral bleiben
                if not kpis.get('category'):
                    kpis['category'] = 'Unklar'
            
            return kpis
        
        # Calculate KPIs
        kpis = calculate_kpis(emails, contact['contact_email'], user_email)
        
        # Save to database with KPIs (inkl. Kategorie)
        cursor.execute(
            """
            UPDATE contacts 
            SET profile_summary = %s, 
                profile_updated_at = NOW(),
                salutation = %s,
                sentiment = %s,
                email_length_preference = %s,
                communication_frequency = %s,
                category = %s,
                kpis_updated_at = NOW()
            WHERE id = %s
            """,
            (summary,
             kpis.get('salutation'),
             kpis.get('sentiment'),
             kpis.get('email_length_preference'),
             kpis.get('communication_frequency'),
             kpis.get('category'),
             contact_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'ok': True,
            'summary': summary,
            'email_count': len(emails),
            'kpis': kpis
        }), 200
        
    except Exception as e:
        app.logger.error(f"[Generate Profile] Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/api/emails/imap-debug")
def api_emails_imap_debug():
    import imaplib
    host = os.environ.get('IMAP_HOST') or os.environ.get('IMAP_SERVER')
    port = int(os.environ.get('IMAP_PORT', '993'))
    user = os.environ.get('IMAP_USER') or os.environ.get('EMAIL_USER')
    pw = os.environ.get('IMAP_PASS') or os.environ.get('EMAIL_PASS')
    mailbox = os.environ.get('IMAP_MAILBOX', 'INBOX')
    if not (host and user and pw):
        return jsonify({"ok": False, "error": "IMAP Konfiguration unvollständig (IMAP_HOST/USER/PASS)."}), 500
    info = {"host": host, "port": port, "user": (user or '')[:3] + '***', "mailbox": mailbox,
            "used_keys": {
                "host": 'IMAP_HOST' if os.environ.get('IMAP_HOST') else ('IMAP_SERVER' if os.environ.get('IMAP_SERVER') else '—'),
                "user": 'IMAP_USER' if os.environ.get('IMAP_USER') else ('EMAIL_USER' if os.environ.get('EMAIL_USER') else '—'),
                "pass": 'IMAP_PASS' if os.environ.get('IMAP_PASS') else ('EMAIL_PASS' if os.environ.get('EMAIL_PASS') else '—'),
            }}
    try:
        M = imaplib.IMAP4_SSL(host, port)
        login_typ, login_data = M.login(user, pw)
        info["login"] = login_typ
        list_typ, list_data = M.list()
        info["list_typ"] = list_typ
        info["mailboxes"] = list_data[:10] if list_data else []
        sel_typ, sel_data = M.select(mailbox)
        info["select_typ"] = sel_typ
        status_typ, status_data = M.status(mailbox, "(MESSAGES UNSEEN RECENT)")
        info["status_typ"] = status_typ
        info["status_data"] = status_data
        srch_typ, srch_data = M.uid('search', None, 'ALL')
        count = len((srch_data[0] or b'').split()) if srch_typ == 'OK' and srch_data else 0
        info["search_typ"] = srch_typ
        info["total_uids"] = count
        if count:
            uids = (srch_data[0] or b'').split()
            info["last_uids"] = [u.decode() for u in uids[-5:]]
        M.close()
        M.logout()
        return jsonify({"ok": True, "info": info})
    except Exception as e:
        info["error"] = str(e)
        app.logger.error(f"[IMAP-DEBUG] {e}")
        return jsonify({"ok": False, "info": info}), 500


@app.route('/api/emails/smtp-debug')
def api_emails_smtp_debug():
    """Diagnose SMTP-Erreichbarkeit (DNS, TCP, SSL/STARTTLS) mit kurzen Timeouts."""
    import socket, ssl, smtplib, time
    host = os.environ.get('SMTP_HOST') or os.environ.get('SMTP_SERVER')
    user = os.environ.get('SMTP_USER') or os.environ.get('EMAIL_USER')
    pw = os.environ.get('SMTP_PASS') or os.environ.get('EMAIL_PASS')
    port_ssl = int(os.environ.get('SMTP_PORT', '465') or 465)
    port_tls = int(os.environ.get('SMTP_PORT_STARTTLS', '587') or 587)
    sec = (os.environ.get('SMTP_SECURITY') or 'auto').lower()
    info = {
        'env': {
            'host': host,
            'user': (user or '')[:3] + '***' if user else None,
            'security': sec,
            'port_ssl': port_ssl,
            'port_tls': port_tls,
        },
        'dns': {},
        'tcp': {},
        'smtp': {}
    }
    if not host:
        return jsonify({'ok': False, 'error': 'SMTP_HOST/SMTP_SERVER fehlt', 'info': info}), 400
    # DNS
    try:
        t0 = time.time(); addrs = socket.getaddrinfo(host, None)
        info['dns']['resolved'] = list({a[4][0] for a in addrs if a and a[4]})
        info['dns']['time_ms'] = int((time.time()-t0)*1000)
    except Exception as e:
        info['dns']['error'] = str(e)
    # TCP 465
    try:
        t0 = time.time(); s = socket.create_connection((host, port_ssl), timeout=5)
        s.close(); info['tcp']['465'] = {'ok': True, 'time_ms': int((time.time()-t0)*1000)}
    except Exception as e:
        info['tcp']['465'] = {'ok': False, 'error': str(e)}
    # TCP 587
    try:
        t0 = time.time(); s = socket.create_connection((host, port_tls), timeout=5)
        s.close(); info['tcp']['587'] = {'ok': True, 'time_ms': int((time.time()-t0)*1000)}
    except Exception as e:
        info['tcp']['587'] = {'ok': False, 'error': str(e)}
    # SMTP SSL 465 (EHLO)
    try:
        t0 = time.time()
        with smtplib.SMTP_SSL(host, port_ssl, timeout=6) as srv:
            code, msg = srv.noop()
        info['smtp']['ssl_465'] = {'ok': True, 'noop_code': int(code), 'time_ms': int((time.time()-t0)*1000)}
    except Exception as e:
        info['smtp']['ssl_465'] = {'ok': False, 'error': str(e)}
    # SMTP STARTTLS 587 (EHLO + STARTTLS)
    try:
        t0 = time.time()
        with smtplib.SMTP(host, port_tls, timeout=6) as srv:
            srv.ehlo(); srv.starttls(); srv.ehlo(); code, msg = srv.noop()
        info['smtp']['starttls_587'] = {'ok': True, 'noop_code': int(code), 'time_ms': int((time.time()-t0)*1000)}
    except Exception as e:
        info['smtp']['starttls_587'] = {'ok': False, 'error': str(e)}
    ok = any(v.get('ok') for v in info['tcp'].values())
    status = 200 if ok else 500
    return jsonify({'ok': ok, 'info': info}), status

@app.route('/api/emails/thread')
@require_auth
def api_emails_thread(current_user):
    import imaplib, email
    from email.header import decode_header
    uid = request.args.get('uid')
    if not uid:
        return jsonify({'error': 'uid fehlt'}), 400
    
    # Get user-specific email settings
    user_email = current_user.get('user_email')
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT imap_host, imap_port, imap_user, imap_pass_encrypted, imap_security "
            "FROM user_email_settings WHERE user_email=%s",
            (user_email,)
        )
        settings = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if settings and settings.get('imap_host'):
            from encryption_utils import decrypt_password
            host = settings['imap_host']
            port = int(settings.get('imap_port', 993))
            user = settings['imap_user']
            pw = decrypt_password(settings['imap_pass_encrypted']) if settings['imap_pass_encrypted'] else ''
            mailbox = 'INBOX'
        else:
            return jsonify({'error': 'Please configure email settings first'}), 400
    except Exception as e:
        app.logger.error(f"[Thread] Error loading user settings: {e}")
        return jsonify({'error': 'Email settings error'}), 400
    
    if not (host and user and pw):
        return jsonify({'error': 'IMAP configuration incomplete'}), 400
    try:
        M = imaplib.IMAP4_SSL(host, port)
        M.login(user, pw)
        M.select(mailbox)
        typ, msgdata = M.uid('fetch', uid, '(RFC822)')
        if typ != 'OK' or not msgdata or not msgdata[0]:
            raise RuntimeError('Fetch fehlgeschlagen')
        raw = msgdata[0][1] if isinstance(msgdata[0], tuple) else msgdata[0]
        msg = email.message_from_bytes(raw)
        # Header
        def _decode(s):
            parts = []
            for p, enc in decode_header(s or ''):
                try:
                    parts.append(p.decode(enc or 'utf-8') if isinstance(p, (bytes, bytearray)) else str(p))
                except Exception:
                    parts.append(p.decode('utf-8', errors='ignore') if isinstance(p, (bytes, bytearray)) else str(p))
            return ''.join(parts)
        subject = _decode(msg.get('Subject'))
        from_addr = msg.get('From', '')
        to_addr = msg.get('To', '')
        date = msg.get('Date', '')
        # Body (bevorzugt HTML)
        html_body = None
        text_body = None
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = part.get('Content-Disposition', '')
                if 'attachment' in (disp or '').lower():
                    continue
                payload = part.get_payload(decode=True)
                if ctype == 'text/html' and payload is not None:
                    try:
                        html_body = payload.decode(part.get_content_charset() or 'utf-8', errors='ignore')
                    except Exception:
                        html_body = payload.decode('utf-8', errors='ignore')
                elif ctype == 'text/plain' and payload is not None and text_body is None:
                    try:
                        text_body = payload.decode(part.get_content_charset() or 'utf-8', errors='ignore')
                    except Exception:
                        text_body = payload.decode('utf-8', errors='ignore')
        else:
            payload = msg.get_payload(decode=True)
            if payload is not None:
                ctype = msg.get_content_type()
                if ctype == 'text/html':
                    try:
                        html_body = payload.decode(msg.get_content_charset() or 'utf-8', errors='ignore')
                    except Exception:
                        html_body = payload.decode('utf-8', errors='ignore')
                else:
                    try:
                        text_body = payload.decode(msg.get_content_charset() or 'utf-8', errors='ignore')
                    except Exception:
                        text_body = payload.decode('utf-8', errors='ignore')
        M.close()
        M.logout()
        result = {
            'uid': uid,
            'subject': subject,
            'from': from_addr,
            'to': to_addr,
            'date': date,
            'html': html_body,
            'text': text_body
        }
        import time as _t
        now = _t.time()
        THREAD_CACHE[uid] = {"data": result, "ts": now}
        return jsonify(result)
    except Exception as e:
        app.logger.error(f"[IMAP] thread error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/emails/seen', methods=['POST'])
@require_auth
def api_emails_seen(current_user):
    """Markiert eine E-Mail als gelesen/ungelesen.

    Erwartet im Body: { uid: <email_id in DB>, seen: true|false }
    - Aktualisiert immer emails.is_read in der DB.
    - Versucht zusätzlich, das IMAP-Flag \\Seen anhand der Message-ID zu setzen/zurückzusetzen.
    """
    import imaplib

    data = request.get_json(silent=True) or {}
    email_id = data.get('uid') or data.get('id')
    seen = bool(data.get('seen', True))
    if not email_id:
        return jsonify({'error': 'uid (email_id) fehlt'}), 400

    user_email = current_user.get('user_email')

    # 1) DB: is_read aktualisieren und Message-ID + Account holen
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, message_id, account_id, folder FROM emails WHERE id=%s AND user_email=%s",
            (email_id, user_email),
        )
        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return jsonify({'error': 'E-Mail nicht gefunden'}), 404

        cursor.execute(
            "UPDATE emails SET is_read=%s WHERE id=%s AND user_email=%s",
            (1 if seen else 0, email_id, user_email),
        )
        conn.commit()
        message_id = row.get('message_id')
        account_id = row.get('account_id')
        folder_db = (row.get('folder') or 'inbox').lower()
        cursor.close()
        conn.close()
    except Exception as e:
        app.logger.error(f"[Emails Seen] DB error: {e}")
        return jsonify({'error': 'DB-Fehler beim Aktualisieren von is_read'}), 500

    # 2) Optional: IMAP-Flag \Seen setzen/zurücksetzen, falls Account + Message-ID vorhanden
    imap_updated = False
    try:
        if message_id and account_id:
            conn = get_settings_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT imap_host, imap_port, imap_user, imap_pass_encrypted, imap_security "
                "FROM email_accounts WHERE id=%s AND user_email=%s AND is_active=1",
                (account_id, user_email),
            )
            settings = cursor.fetchone()
            cursor.close()
            conn.close()

            if settings and settings.get('imap_host') and settings.get('imap_user'):
                from encryption_utils import decrypt_password

                host = settings['imap_host']
                port = int(settings.get('imap_port', 993))
                imap_user = settings['imap_user']
                pw = decrypt_password(settings['imap_pass_encrypted']) if settings['imap_pass_encrypted'] else ''

                if host and imap_user and pw:
                    # Grobe Folder-Mapping-Logik wie im Sync
                    if folder_db == 'sent':
                        folder_imap = 'Sent'
                    elif folder_db == 'archive':
                        folder_imap = 'Archive'
                    else:
                        folder_imap = 'INBOX'

                    M = imaplib.IMAP4_SSL(host, port, timeout=15)
                    M.login(imap_user, pw)
                    try:
                        try:
                            sel_typ, _ = M.select(f'"{folder_imap}"')
                        except imaplib.IMAP4.error:
                            sel_typ, _ = M.select(folder_imap)
                        if sel_typ == 'OK':
                            # Nach Message-ID suchen (UID SEARCH HEADER)
                            search_crit = f'(HEADER Message-ID "{message_id}")'
                            typ, data = M.uid('search', None, search_crit)
                            if typ == 'OK' and data and data[0]:
                                for u in data[0].split():
                                    if seen:
                                        M.uid('store', u, '+FLAGS.SILENT', '(\\Seen)')
                                    else:
                                        M.uid('store', u, '-FLAGS.SILENT', '(\\Seen)')
                                imap_updated = True
                    finally:
                        try:
                            M.close()
                        except Exception:
                            pass
                        M.logout()
    except Exception as e:
        # IMAP-Update ist nur Best-Effort; Fehler hier nicht als hartes API-Error behandeln
        app.logger.warning(f"[Emails Seen] IMAP update failed: {e}")

    return jsonify({'ok': True, 'imap_updated': imap_updated})


def get_settings_db_connection():
    """Connect to SETTINGS_DB (user_email_settings table) or fall back to main DB."""
    host = os.environ.get('SETTINGS_DB_HOST') or os.environ.get('DB_HOST')
    port = int(os.environ.get('SETTINGS_DB_PORT') or os.environ.get('DB_PORT', '3306'))
    user = os.environ.get('SETTINGS_DB_USER') or os.environ.get('DB_USER')
    pw = os.environ.get('SETTINGS_DB_PASSWORD') or os.environ.get('DB_PASSWORD')
    db = os.environ.get('SETTINGS_DB_NAME') or os.environ.get('DB_NAME')
    if not (host and user and pw and db):
        raise RuntimeError("SETTINGS_DB (or DB) configuration incomplete")
    return mysql.connector.connect(host=host, port=port, user=user, password=pw, database=db)


@app.route('/api/email-accounts/list', methods=['GET'])
@require_auth
def api_email_accounts_list(current_user):
    """Liste aktiver E-Mail-Accounts für den aktuellen User (Multi-Account-Unterstützung)."""
    user_email = current_user.get('user_email')
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, account_email, label FROM email_accounts WHERE user_email=%s AND is_active=1 ORDER BY id ASC",
            (user_email,)
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        accounts = [
            {
                'id': r['id'],
                'account_email': r['account_email'],
                'label': r.get('label') or r['account_email'],
            }
            for r in rows
        ]
        return jsonify({'accounts': accounts}), 200
    except Exception as e:
        app.logger.error(f"[Email-Accounts-List] error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/email-accounts/<int:account_id>', methods=['GET'])
@require_auth
def api_email_account_get(current_user, account_id: int):
    """Liefert die Details eines E-Mail-Accounts des aktuellen Users (ohne Passwörter)."""
    user_email = current_user.get('user_email')
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, user_email, account_email, label,
                   imap_host, imap_port, imap_user, imap_security,
                   smtp_host, smtp_port, smtp_user, smtp_security,
                   imap_pass_encrypted IS NOT NULL AS has_imap_password,
                   smtp_pass_encrypted IS NOT NULL AS has_smtp_password,
                   is_active
            FROM email_accounts
            WHERE user_email=%s AND id=%s
            """,
            (user_email, account_id),
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            return jsonify({'error': 'Account nicht gefunden'}), 404
        return jsonify({'account': row}), 200
    except Exception as e:
        app.logger.error(f"[Email-Account-Get] error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/email-accounts/save', methods=['POST'])
@require_auth
def api_email_account_save(current_user):
    """Erstellt oder aktualisiert einen E-Mail-Account des aktuellen Users.
    Body: { id?, account_email, label, imap_*, smtp_*, imap_pass?, smtp_pass?, is_active? }
    Passwörter werden nur überschrieben, wenn sie im Body gesetzt sind.
    """
    data = request.get_json(silent=True) or {}
    user_email = current_user.get('user_email')
    account_id = data.get('id')
    account_email = (data.get('account_email') or '').strip()
    label = (data.get('label') or '').strip() or account_email
    imap_host = (data.get('imap_host') or '').strip()
    imap_port = int(data.get('imap_port') or 993)
    imap_user = (data.get('imap_user') or '').strip()
    imap_pass = data.get('imap_pass') or ''
    imap_security = (data.get('imap_security') or 'ssl').lower()
    smtp_host = (data.get('smtp_host') or '').strip()
    smtp_port = int(data.get('smtp_port') or 465)
    smtp_user = (data.get('smtp_user') or '').strip()
    smtp_pass = data.get('smtp_pass') or ''
    smtp_security = (data.get('smtp_security') or 'ssl').lower()
    # Optionale User-Signatur (wird in user_email_settings gespeichert)
    signature_html = data.get('signature_html')
    is_active = 1 if data.get('is_active', True) else 0

    if not (account_email and imap_host and imap_user and smtp_host and smtp_user):
        return jsonify({'error': 'account_email, imap_host, imap_user, smtp_host und smtp_user sind erforderlich'}), 400

    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Update vs. Insert
        if account_id:
            # Vorhandenen Datensatz laden, um Passwörter ggf. zu behalten
            cursor.execute(
                "SELECT imap_pass_encrypted, smtp_pass_encrypted FROM email_accounts WHERE id=%s AND user_email=%s",
                (account_id, user_email),
            )
            existing = cursor.fetchone()
            if not existing:
                cursor.close()
                conn.close()
                return jsonify({'error': 'Account nicht gefunden'}), 404

            imap_pass_enc = encrypt_password(imap_pass) if imap_pass else existing['imap_pass_encrypted']
            smtp_pass_enc = encrypt_password(smtp_pass) if smtp_pass else existing['smtp_pass_encrypted']

            cursor.execute(
                """
                UPDATE email_accounts
                SET account_email=%s, label=%s,
                    imap_host=%s, imap_port=%s, imap_user=%s, imap_pass_encrypted=%s, imap_security=%s,
                    smtp_host=%s, smtp_port=%s, smtp_user=%s, smtp_pass_encrypted=%s, smtp_security=%s,
                    is_active=%s
                WHERE id=%s AND user_email=%s
                """,
                (
                    account_email, label,
                    imap_host, imap_port, imap_user, imap_pass_enc, imap_security,
                    smtp_host, smtp_port, smtp_user, smtp_pass_enc, smtp_security,
                    is_active,
                    account_id, user_email,
                ),
            )
        else:
            # Neuer Account: Passwörter sind Pflicht
            if not imap_pass or not smtp_pass:
                cursor.close()
                conn.close()
                return jsonify({'error': 'Für einen neuen Account sind IMAP- und SMTP-Passwort erforderlich'}), 400

            imap_pass_enc = encrypt_password(imap_pass)
            smtp_pass_enc = encrypt_password(smtp_pass)

            cursor.execute(
                """
                INSERT INTO email_accounts
                    (user_email, account_email, label,
                     imap_host, imap_port, imap_user, imap_pass_encrypted, imap_security,
                     smtp_host, smtp_port, smtp_user, smtp_pass_encrypted, smtp_security,
                     is_active)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    user_email, account_email, label,
                    imap_host, imap_port, imap_user, imap_pass_enc, imap_security,
                    smtp_host, smtp_port, smtp_user, smtp_pass_enc, smtp_security,
                    is_active,
                ),
            )
            account_id = cursor.lastrowid

        conn.commit()
        cursor.close()
        conn.close()

        # Signatur separat in user_email_settings ablegen (Best-Effort)
        if signature_html is not None and user_email:
            try:
                conn2 = get_settings_db_connection()
                cur2 = conn2.cursor()
                # Erst versuchen zu aktualisieren
                cur2.execute(
                    "UPDATE user_email_settings SET signature_html=%s, updated_at=NOW() WHERE user_email=%s",
                    (signature_html, user_email),
                )
                if cur2.rowcount == 0:
                    # Falls noch kein Eintrag existiert, minimalen Datensatz anlegen
                    cur2.execute(
                        "INSERT INTO user_email_settings (user_email, signature_html, created_at, updated_at) "
                        "VALUES (%s, %s, NOW(), NOW())",
                        (user_email, signature_html),
                    )
                conn2.commit()
                cur2.close()
                conn2.close()
            except Exception as e_sig:
                app.logger.warning(f"[Email-Account-Save] Konnte Signatur nicht speichern: {e_sig}")

        return jsonify({'ok': True, 'id': int(account_id)}), 200
    except Exception as e:
        app.logger.error(f"[Email-Account-Save] error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/email-accounts/<int:account_id>/delete', methods=['POST'])
@require_auth
def api_email_account_delete(current_user, account_id: int):
    """Deaktiviert einen E-Mail-Account des aktuellen Users (Soft-Delete via is_active=0)."""
    user_email = current_user.get('user_email')
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE email_accounts SET is_active=0 WHERE id=%s AND user_email=%s",
            (account_id, user_email),
        )
        affected = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        if affected == 0:
            return jsonify({'error': 'Account nicht gefunden'}), 404
        return jsonify({'ok': True}), 200
    except Exception as e:
        app.logger.error(f"[Email-Account-Delete] error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/email-settings', methods=['GET'])
def api_user_email_settings_get():
    """Get email settings for a user. Query param: user_email"""
    user_email = request.args.get('user_email', '').strip()
    if not user_email:
        return jsonify({'error': 'user_email parameter required'}), 400
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT user_email, imap_host, imap_port, imap_user, imap_security, "
            "smtp_host, smtp_port, smtp_user, smtp_security, signature_html, created_at, updated_at "
            "FROM user_email_settings WHERE user_email=%s",
            (user_email,)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if not row:
            return jsonify({'exists': False}), 404
        # Don't return encrypted passwords, just confirm they exist
        return jsonify({
            'exists': True,
            'user_email': row['user_email'],
            'imap_host': row['imap_host'],
            'imap_port': row['imap_port'],
            'imap_user': row['imap_user'],
            'imap_security': row['imap_security'],
            'smtp_host': row['smtp_host'],
            'smtp_port': row['smtp_port'],
            'smtp_user': row['smtp_user'],
            'smtp_security': row['smtp_security'],
            'signature_html': row.get('signature_html'),
            'created_at': str(row['created_at']),
            'updated_at': str(row['updated_at'])
        }), 200
    except Exception as e:
        app.logger.error(f"[GET email-settings] error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/email-settings', methods=['POST'])
def api_user_email_settings_post():
    """Save/update email settings for a user.

    Body kann vollstaendige IMAP/SMTP-Daten (Erstkonfiguration) oder
    nur eine Signatur-Aktualisierung enthalten:
      { user_email, signature_html }
    """
    data = request.get_json(silent=True) or {}
    user_email = data.get('user_email', '').strip()
    if not user_email:
        return jsonify({'error': 'user_email required'}), 400
    # Signatur kann auch alleine geschickt werden
    signature_html = data.get('signature_html')

    imap_host = (data.get('imap_host') or '').strip()
    imap_port = int(data.get('imap_port', 993)) if 'imap_port' in data else 993
    imap_user = (data.get('imap_user') or '').strip()
    imap_pass = data.get('imap_pass', '')
    imap_security = data.get('imap_security', 'ssl')
    smtp_host = (data.get('smtp_host') or '').strip()
    smtp_port = int(data.get('smtp_port', 465)) if 'smtp_port' in data else 465
    smtp_user = (data.get('smtp_user') or '').strip()
    smtp_pass = data.get('smtp_pass', '')
    smtp_security = data.get('smtp_security', 'ssl')

    full_update = bool(imap_host and imap_user and smtp_host and smtp_user)

    if not full_update and signature_html is None:
        return jsonify({'error': 'Either full IMAP/SMTP config or signature_html required'}), 400
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)

        if full_update:
            # Check if settings exist (für Passwort-Handling)
            cursor.execute(
                "SELECT imap_pass_encrypted, smtp_pass_encrypted FROM user_email_settings WHERE user_email=%s",
                (user_email,)
            )
            existing = cursor.fetchone()

            # Only encrypt/update password if provided, otherwise keep existing
            if existing:
                imap_pass_enc = encrypt_password(imap_pass) if imap_pass else existing['imap_pass_encrypted']
                smtp_pass_enc = encrypt_password(smtp_pass) if smtp_pass else existing['smtp_pass_encrypted']
            else:
                # New entry: require passwords
                if not imap_pass or not smtp_pass:
                    cursor.close()
                    conn.close()
                    return jsonify({'error': 'Passwords required for new configuration'}), 400
                imap_pass_enc = encrypt_password(imap_pass)
                smtp_pass_enc = encrypt_password(smtp_pass)

            # Upsert: insert or update on duplicate key (inkl. optionaler Signatur)
            sql = """
                INSERT INTO user_email_settings
                (user_email, imap_host, imap_port, imap_user, imap_pass_encrypted, imap_security,
                 smtp_host, smtp_port, smtp_user, smtp_pass_encrypted, smtp_security, signature_html)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    imap_host=VALUES(imap_host), imap_port=VALUES(imap_port),
                    imap_user=VALUES(imap_user), imap_pass_encrypted=VALUES(imap_pass_encrypted),
                    imap_security=VALUES(imap_security),
                    smtp_host=VALUES(smtp_host), smtp_port=VALUES(smtp_port),
                    smtp_user=VALUES(smtp_user), smtp_pass_encrypted=VALUES(smtp_pass_encrypted),
                    smtp_security=VALUES(smtp_security),
                    signature_html=VALUES(signature_html)
            """
            cursor.execute(sql, (
                user_email, imap_host, imap_port, imap_user, imap_pass_enc, imap_security,
                smtp_host, smtp_port, smtp_user, smtp_pass_enc, smtp_security, signature_html,
            ))
        else:
            # Nur Signatur aktualisieren
            cursor.execute(
                "UPDATE user_email_settings SET signature_html=%s, updated_at=NOW() WHERE user_email=%s",
                (signature_html, user_email),
            )
            if cursor.rowcount == 0:
                cursor.close()
                conn.close()
                return jsonify({'error': 'Email settings must be created before updating signature'}), 400

        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True, 'message': 'Settings saved'}), 200
    except Exception as e:
        app.logger.error(f"[POST email-settings] error: {e}")
        return jsonify({'error': str(e)}), 500


def get_users_db_connection():
    """Connect to users DB (same as SETTINGS_DB or main DB)."""
    return get_settings_db_connection()


@app.route('/api/auth/debug', methods=['GET'])
def api_auth_debug():
    """Debug endpoint: shows DB config (without passwords) and connection status."""
    import socket
    
    # Get DB config from ENV
    settings_host = os.environ.get('SETTINGS_DB_HOST') or os.environ.get('DB_HOST')
    settings_port = os.environ.get('SETTINGS_DB_PORT') or os.environ.get('DB_PORT', '3306')
    settings_user = os.environ.get('SETTINGS_DB_USER') or os.environ.get('DB_USER')
    settings_db = os.environ.get('SETTINGS_DB_NAME') or os.environ.get('DB_NAME')
    jwt_secret_set = bool(os.environ.get('JWT_SECRET_KEY'))
    
    info = {
        'config': {
            'SETTINGS_DB_HOST': settings_host or '(not set)',
            'SETTINGS_DB_PORT': settings_port,
            'SETTINGS_DB_USER': settings_user or '(not set)',
            'SETTINGS_DB_NAME': settings_db or '(not set)',
            'SETTINGS_DB_PASSWORD': '***' if os.environ.get('SETTINGS_DB_PASSWORD') else '(not set)',
            'JWT_SECRET_KEY': 'SET' if jwt_secret_set else '(not set)',
        },
        'fallback': {
            'DB_HOST': os.environ.get('DB_HOST') or '(not set)',
            'DB_PORT': os.environ.get('DB_PORT', '3306'),
            'DB_USER': os.environ.get('DB_USER') or '(not set)',
            'DB_NAME': os.environ.get('DB_NAME') or '(not set)',
            'DB_PASSWORD': '***' if os.environ.get('DB_PASSWORD') else '(not set)',
        },
        'connection_test': {},
        'tables': []
    }
    
    # Test DB connection
    if settings_host and settings_user and settings_db:
        try:
            conn = get_users_db_connection()
            cursor = conn.cursor()
            
            # Check if users table exists
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            info['tables'] = tables
            
            if 'users' in tables:
                cursor.execute("SELECT COUNT(*) as count FROM users")
                count = cursor.fetchone()[0]
                info['connection_test']['users_table'] = f'EXISTS ({count} rows)'
            else:
                info['connection_test']['users_table'] = 'NOT FOUND'
            
            cursor.close()
            conn.close()
            info['connection_test']['status'] = 'SUCCESS'
        except Exception as e:
            info['connection_test']['status'] = 'FAILED'
            info['connection_test']['error'] = str(e)
    else:
        info['connection_test']['status'] = 'INCOMPLETE CONFIG'
    
    # Test DNS resolution
    if settings_host:
        try:
            ip = socket.gethostbyname(settings_host)
            info['connection_test']['dns_resolved'] = ip
        except Exception as e:
            info['connection_test']['dns_error'] = str(e)
    
    return jsonify(info), 200


@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    """Login endpoint. Body: { email, password }. Returns JWT token."""
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    try:
        conn = get_users_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, email, password_hash, role, first_name, last_name, active "
            "FROM users WHERE email=%s",
            (email,)
        )
        user = cursor.fetchone()
        cursor.close()
        
        if not user:
            conn.close()
            return jsonify({'error': 'Invalid email or password'}), 401
        
        if not user['active']:
            conn.close()
            return jsonify({'error': 'Account is deactivated'}), 403
        
        if not verify_password(password, user['password_hash']):
            conn.close()
            return jsonify({'error': 'Invalid email or password'}), 401
        
        # Update last_login
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_login=NOW() WHERE id=%s", (user['id'],))
        conn.commit()
        cursor.close()
        conn.close()
        
        # Create JWT token
        token = create_jwt_token(
            user_email=user['email'],
            role=user['role'],
            user_id=user['id']
        )
        
        return jsonify({
            'ok': True,
            'token': token,
            'user': {
                'id': user['id'],
                'email': user['email'],
                'role': user['role'],
                'first_name': user['first_name'],
                'last_name': user['last_name']
            }
        }), 200
    except Exception as e:
        app.logger.error(f"[Login] error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/auth/me', methods=['GET'])
@require_auth
def api_auth_me(current_user):
    """Get current user info from JWT token. Requires Authorization header."""
    try:
        conn = get_users_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, email, role, first_name, last_name, active, created_at, last_login "
            "FROM users WHERE id=%s",
            (current_user['user_id'],)
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if not user['active']:
            return jsonify({'error': 'Account is deactivated'}), 403
        
        return jsonify({
            'ok': True,
            'user': {
                'id': user['id'],
                'email': user['email'],
                'role': user['role'],
                'first_name': user['first_name'],
                'last_name': user['last_name'],
                'created_at': str(user['created_at']) if user['created_at'] else None,
                'last_login': str(user['last_login']) if user['last_login'] else None
            }
        }), 200
    except Exception as e:
        app.logger.error(f"[Auth/me] error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/profile', methods=['PUT'])
@require_auth
def api_user_profile_update(current_user):
    """Update current user's profile (first_name, last_name, password)."""
    data = request.get_json(silent=True) or {}
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    password = data.get('password', '')
    
    try:
        conn = get_users_db_connection()
        cursor = conn.cursor()
        
        # Update first_name and last_name
        cursor.execute(
            "UPDATE users SET first_name=%s, last_name=%s WHERE id=%s",
            (first_name, last_name, current_user['user_id'])
        )
        
        # Update password if provided
        if password:
            if len(password) < 6:
                cursor.close()
                conn.close()
                return jsonify({'error': 'Password must be at least 6 characters'}), 400
            
            password_hash = hash_password(password)
            cursor.execute(
                "UPDATE users SET password_hash=%s WHERE id=%s",
                (password_hash, current_user['user_id'])
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'ok': True,
            'message': 'Profile updated',
            'user': {
                'first_name': first_name,
                'last_name': last_name
            }
        }), 200
    except Exception as e:
        app.logger.error(f"[User/profile] error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/agent-settings', methods=['GET'])
@require_auth
def api_user_agent_settings_get(current_user):
    """Get agent settings for current user."""
    user_email = current_user.get('user_email')
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT role, instructions, faq_text, document_links, created_at, updated_at "
            "FROM user_agent_settings WHERE user_email=%s",
            (user_email,)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not row:
            return jsonify({'role': '', 'instructions': '', 'faq_text': '', 'document_links': ''}), 200
        
        return jsonify({
            'role': row['role'] or '',
            'instructions': row['instructions'] or '',
            'faq_text': row['faq_text'] or '',
            'document_links': row['document_links'] or '',
            'created_at': str(row['created_at']) if row['created_at'] else None,
            'updated_at': str(row['updated_at']) if row['updated_at'] else None
        }), 200
    except Exception as e:
        app.logger.error(f"[Agent-Settings GET] error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/agent-settings', methods=['POST'])
@require_auth
def api_user_agent_settings_post(current_user):
    """Save/update agent settings for current user."""
    data = request.get_json(silent=True) or {}
    role = (data.get('role') or '').strip()
    instructions = (data.get('instructions') or '').strip()
    faq_text = (data.get('faq_text') or '').strip()
    document_links = (data.get('document_links') or '').strip()
    user_email = current_user.get('user_email')
    
    try:
        conn = get_settings_db_connection()
        cursor = conn.cursor()
        
        # Check if settings exist
        cursor.execute(
            "SELECT id FROM user_agent_settings WHERE user_email=%s",
            (user_email,)
        )
        existing = cursor.fetchone()
        
        if existing:
            # Update - only update fields that are provided
            update_fields = []
            update_values = []
            
            if 'role' in data:
                update_fields.append('role=%s')
                update_values.append(role)
            if 'instructions' in data:
                update_fields.append('instructions=%s')
                update_values.append(instructions)
            if 'faq_text' in data:
                update_fields.append('faq_text=%s')
                update_values.append(faq_text)
            if 'document_links' in data:
                update_fields.append('document_links=%s')
                update_values.append(document_links)
            
            if update_fields:
                update_fields.append('updated_at=NOW()')
                update_values.append(user_email)
                cursor.execute(
                    f"UPDATE user_agent_settings SET {', '.join(update_fields)} WHERE user_email=%s",
                    tuple(update_values)
                )
        else:
            # Insert
            cursor.execute(
                "INSERT INTO user_agent_settings (user_email, role, instructions, faq_text, document_links) "
                "VALUES (%s, %s, %s, %s, %s)",
                (user_email, role, instructions, faq_text, document_links)
            )
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'ok': True, 'message': 'Agent settings saved'}), 200
    except Exception as e:
        app.logger.error(f"[Agent-Settings POST] error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/users', methods=['GET'])
@require_auth
@require_role(['superadmin'])
def api_admin_users_list(current_user):
    """List all users. Superadmin only."""
    try:
        conn = get_users_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, email, role, first_name, last_name, active, created_at, last_login "
            "FROM users ORDER BY created_at DESC"
        )
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Convert datetime to string
        for u in users:
            if u.get('created_at'):
                u['created_at'] = str(u['created_at'])
            if u.get('last_login'):
                u['last_login'] = str(u['last_login'])
        
        return jsonify({'ok': True, 'users': users}), 200
    except Exception as e:
        app.logger.error(f"[Admin/users/list] error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/users', methods=['POST'])
@require_auth
@require_role(['superadmin'])
def api_admin_users_create(current_user):
    """Create a new user. Superadmin only. Body: { email, first_name, last_name, password, role }."""
    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip().lower()
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'user').strip().lower()
    
    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400
    
    if role not in ['user', 'admin', 'superadmin']:
        return jsonify({'error': 'Invalid role'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    try:
        # Check if user already exists
        conn = get_users_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
        existing = cursor.fetchone()
        
        if existing:
            cursor.close()
            conn.close()
            return jsonify({'error': 'User with this email already exists'}), 400
        
        # Hash password
        password_hash = hash_password(password)
        
        # Insert user
        cursor.execute(
            "INSERT INTO users (email, password_hash, role, first_name, last_name, active, created_at) "
            "VALUES (%s, %s, %s, %s, %s, TRUE, NOW())",
            (email, password_hash, role, first_name, last_name)
        )
        conn.commit()
        new_user_id = cursor.lastrowid
        cursor.close()
        conn.close()
        
        return jsonify({
            'ok': True,
            'user': {
                'id': new_user_id,
                'email': email,
                'role': role,
                'first_name': first_name,
                'last_name': last_name,
                'active': True
            }
        }), 201
    except Exception as e:
        app.logger.error(f"[Admin/users/create] error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@require_auth
@require_role(['superadmin'])
def api_admin_users_delete(current_user, user_id):
    """Delete a user. Superadmin only."""
    try:
        # Don't allow deleting yourself
        if user_id == current_user['user_id']:
            return jsonify({'error': 'Cannot delete your own account'}), 400
        
        conn = get_users_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        
        if affected == 0:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({'ok': True, 'message': 'User deleted'}), 200
    except Exception as e:
        app.logger.error(f"[Admin/users/delete] error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/api/termine")
def termine():
    datum = request.args.get("datum")
    if not datum:
        return jsonify({"error": "Kein Datum angegeben"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    sql = """
    SELECT
        r.id AS reservierungs_id,
        r.name AS kunde,
        r.email AS kunde_email,
        t.id AS time_id,
        t.time_start,
        t.time_end,
        d.id AS datum_id,
        d.date,
        c.name AS firma,
        a1.first_name AS masseur_vorname,
        a1.last_name AS masseur_nachname,
        a1.email AS masseur_email,
        a2.first_name AS kontakt_vorname,
        a2.last_name AS kontakt_nachname,
        a2.email AS kontakt_email
    FROM dates d
    JOIN times t ON t.date_id = d.id
    LEFT JOIN reservations r ON r.time_id = t.id
    JOIN clients c ON d.client_id = c.id
    LEFT JOIN admin a1 ON d.masseur_id = a1.id
    LEFT JOIN admin a2 ON c.contact_masseur_id = a2.id
    WHERE d.date = %s
    ORDER BY t.time_start
    """
    try:
        cursor.execute(sql, (datum,))
        result = cursor.fetchall()
        termine = []
        for row in result:
            masseur = (
                f"{row['masseur_vorname']} {row['masseur_nachname']}"
                if row['masseur_vorname'] else
                f"{row['kontakt_vorname']} {row['kontakt_nachname']}"
                if row['kontakt_vorname'] else "Kein Masseur zugewiesen"
            )
            masseur_email = (
                row['masseur_email'] if row['masseur_email'] else row['kontakt_email']
            )
            termine.append({
                "zeit": f"{row['time_start']} - {row['time_end']}",
                "kunde": row['kunde'],
                "kunde_email": row['kunde_email'],
                "firma": row['firma'],
                "masseur": masseur,
                "masseur_email": masseur_email,
                "reservierungs_id": row['reservierungs_id'],
                "time_id": row['time_id']  # Wichtig für das Löschen
            })
        cursor.close()
        conn.close()
        return jsonify(termine)
    except Exception as e:
        app.logger.error(f"[DB-Fehler bei Terminabfrage]: {e}")
        return jsonify({"error": "DB-Fehler bei Terminabfrage"}), 500

@app.route("/api/termine/delete", methods=["POST"])
def delete_termine():
    if not request.is_json:
        return jsonify({"error": "Content-Type muss application/json sein"}), 400
    
    termine = request.get_json()
    if not isinstance(termine, list):
        return jsonify({"error": "Ungültiges Format"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # DEBUG: Alle Zeitslots für jedes angeforderte Datum und jede Firma (inkl. Buchungsstatus)
    # (Mehrfache Firmen/Datums-Kombis werden mehrfach geloggt, aber das ist für Debug-Zwecke okay)
    for termin in termine:
        firma = termin.get("firma")
        datum = termin.get("datum")
        if not (firma and datum):
            continue
        cursor.execute(
            """
            SELECT t.time_start, t.id, r.id as reservation_id
            FROM times t
            JOIN dates d ON t.date_id = d.id
            JOIN clients c ON d.client_id = c.id
            LEFT JOIN reservations r ON r.time_id = t.id
            WHERE d.date = %s AND c.name = %s
            ORDER BY t.time_start
            """, (datum, firma)
        )
        slots = cursor.fetchall()
        # DEBUG: Alle Zeitslots für das angeforderte Datum und die Firma (explizit für den User-Check)
        cursor.execute(
            "SELECT t.time_start, t.id, r.id as reservation_id "
            "FROM times t "
            "JOIN dates d ON t.date_id = d.id "
            "JOIN clients c ON d.client_id = c.id "
            "LEFT JOIN reservations r ON r.time_id = t.id "
            "WHERE d.date = %s AND c.name = %s ",
            (datum, firma)
        )
        all_slots = cursor.fetchall()
        for row in all_slots:
            zeit = str(row[0])
            time_id = row[1]
            reserv_id = row[2]
            status = "frei" if reserv_id is None else "belegt"
            app.logger.info(f"Slot: {zeit} (time_id: {time_id}) - {status}")
        app.logger.info(f"[DEBUG-USER] Alle Slots für {datum}, {firma}: {[ (str(row[0]), row[1], row[2]) for row in all_slots ]}")
    
    try:
        # Hole und lösche Zeitslots für das gegebene Datum, die Firma und die exakte Zeit
        # Teste alternative Parameter-Syntax (named style)
        sql_select_named = (
            "SELECT t.id "
            "FROM times t "
            "JOIN dates d ON t.date_id = d.id "
            "JOIN clients c ON d.client_id = c.id "
            "LEFT JOIN reservations r ON r.time_id = t.id "
            "WHERE d.date = %(datum)s "
            "AND c.name = %(firma)s "
            "AND TIME_TO_SEC(t.time_start) = %(zeit_seconds)s "
            "AND r.id IS NULL"
        )
        app.logger.info(f"SQL-Statement (named, nur freie Slots, Zeit in Sekunden): {sql_select_named}")

        sql_delete = "DELETE FROM times WHERE id = %s"
        deleted_count = 0

        for termin in termine:
            firma = termin.get("firma")
            zeit_intervall = termin.get("zeit") or termin.get("time")
            zeit_start = zeit_intervall.split(" - ")[0].strip() if zeit_intervall and " - " in zeit_intervall else zeit_intervall
            datum = termin.get("datum")

            # Zeit in Sekunden seit Mitternacht umwandeln
            try:
                h, m, s = map(int, zeit_start.split(":"))
                zeit_seconds = h * 3600 + m * 60 + s
            except Exception as e:
                app.logger.error(f"Zeit-Parsing-Fehler für '{zeit_start}': {e}")
                continue

            param_dict = {"datum": datum, "firma": firma, "zeit_seconds": zeit_seconds}
            app.logger.info(f"Parameter-Typ: {type(param_dict)}, Keys: {list(param_dict.keys())}")
            app.logger.info(f"Parameter-Werte: datum={datum}, firma={firma}, zeit_start={zeit_start}, zeit_seconds={zeit_seconds}")

            if not all([firma, zeit_start, datum]):
                app.logger.warning(f"Ungültige Termin-Daten (werden übersprungen): {termin}")
                continue

            app.logger.info(f"Lösche Termin: firma={firma}, zeit_start={zeit_start} ({zeit_seconds}s), datum={datum}")
            try:
                cursor.execute(sql_select_named, param_dict)
                result = cursor.fetchone()
                app.logger.info(f"SQL-Select-Result für {param_dict}: {result}")
            except Exception as e:
                app.logger.error(f"SQL-Fehler bei execute: {e}")
                continue

            if result:
                cursor.execute(sql_delete, (result[0],))
                deleted_count += 1
        
        conn.commit()
        return jsonify({
            "message": f"{deleted_count} Termine wurden erfolgreich gelöscht",
            "deleted_count": deleted_count
        })
        
    except Exception as e:
        conn.rollback()
        app.logger.error(f"Fehler beim Löschen der Termine: {str(e)}")
        return jsonify({"error": str(e)}), 500
        
    finally:
        cursor.close()
        conn.close()

@app.route("/api/slots")
def slots():
    datum = request.args.get("datum")
    if not datum:
        return jsonify({"error": "Kein Datum angegeben"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Hole alle Firmen (clients) für das Datum
    sql_clients = """
        SELECT d.id as date_id, c.id as client_id, c.name as firma,
               d.masseur_id,
               a1.first_name AS masseur_vorname, a1.last_name AS masseur_nachname, a1.email AS masseur_email
        FROM dates d
        JOIN clients c ON d.client_id = c.id
        LEFT JOIN admin a1 ON d.masseur_id = a1.id
        WHERE d.date = %s
    """
    try:
        cursor.execute(sql_clients, (datum,))
        client_rows = cursor.fetchall()
        result = []
        for client in client_rows:
            date_id = client['date_id']
            firma = client['firma']
            # Hole alle Slots für diese date_id
            sql_slots = """
                SELECT t.id as time_id, t.time_start, r.id as reservierungs_id, r.name as kunde, r.email as kunde_email
                FROM times t
                LEFT JOIN reservations r ON r.time_id = t.id
                WHERE t.date_id = %s
                ORDER BY t.time_start
            """
            cursor.execute(sql_slots, (date_id,))
            slots = []
            for row in cursor.fetchall():
                slots.append({
                    "time_id": row['time_id'],
                    "time_start": str(row['time_start']),
                    "frei": row['reservierungs_id'] is None,
                    "kunde": row['kunde'] if row['kunde'] else None,
                    "kunde_email": row['kunde_email'] if row['kunde_email'] else None
                })
            # Masseurname und E-Mail wie in /api/termine bauen
            masseur = (
                f"{client['masseur_vorname']} {client['masseur_nachname']}"
                if client.get('masseur_vorname') else "Kein Masseur zugewiesen"
            )
            masseur_email = client.get('masseur_email')
            result.append({
                "firma": firma,
                "date_id": date_id,
                "masseur": masseur,
                "masseur_email": masseur_email,
                "slots": slots
            })
        cursor.close()
        conn.close()
        return jsonify(result)
    except Exception as e:
        app.logger.error(f"[DB-Fehler bei Slotabfrage]: {e}")
        return jsonify({"error": "DB-Fehler bei Slotabfrage"}), 500

# --- ChatGPT-API-Endpunkt ---
@app.route('/api/chat', methods=['POST'])
def chat_api():
    import re
    data = request.get_json()
    messages = data.get('messages', [])
    if not messages or not isinstance(messages, list):
        return jsonify({'error': 'Kein Nachrichtenverlauf erhalten.'}), 400

    # --- Dynamische Kontext-Erweiterung für gezielte Fragen ---
    # Prüfe, ob letzte User-Nachricht nach bestimmten Mustern fragt
    db_context = ""
    last_user_msg = None
    for m in reversed(messages):
        if m.get('role') == 'user':
            last_user_msg = m.get('content', '')
            break
    from datetime import datetime, timedelta
    import pytz
    berlin = pytz.timezone('Europe/Berlin')
    now_berlin = datetime.now(berlin)
    today_str = now_berlin.strftime('%Y-%m-%d')

    name_match = None
    firmen_fuer_datum = None
    antwort_datum = None
    next_termin_name = None
    if last_user_msg:
        # Suche nach Mustern wie "letzter Termin von ..." oder "Wann war der letzte Termin von ..."
        match = re.search(r'letzte[rn]? termin (von|für) ([\w\s.\-]+)', last_user_msg, re.IGNORECASE)
        if not match:
            match = re.search(r'wann war der letzte termin (von|für) ([\w\s.\-]+)', last_user_msg, re.IGNORECASE)
        if match:
            name_match = match.group(2).strip()
        # Nächster Termin für ...
        match_next = re.search(r'nächste[rsn]? termin (von|für) ([\w\s.\-]+)', last_user_msg, re.IGNORECASE)
        if not match_next:
            match_next = re.search(r'wann.*nächste[rsn]? termin (von|für) ([\w\s.\-]+)', last_user_msg, re.IGNORECASE)
        if match_next:
            next_termin_name = match_next.group(2).strip()
        # Firmen mit Terminen an einem bestimmten Tag
        match_firmen = re.search(r'firmen.*(morgen|am ([0-9]{1,2})[.\-/]([0-9]{1,2})[.\-/]([0-9]{2,4}))', last_user_msg, re.IGNORECASE)
        if match_firmen:
            if 'morgen' in match_firmen.group(1).lower():
                antwort_datum = (now_berlin + timedelta(days=1)).strftime('%Y-%m-%d')
            else:
                # Versuche, ein Datum zu extrahieren
                try:
                    tag, monat, jahr = match_firmen.group(2), match_firmen.group(3), match_firmen.group(4)
                    if len(jahr) == 2:
                        jahr = '20' + jahr
                    antwort_datum = f"{jahr}-{monat.zfill(2)}-{tag.zfill(2)}"
                except Exception:
                    antwort_datum = None
            if antwort_datum:
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("""
                        SELECT DISTINCT firma FROM termine WHERE datum = %s
                    """, (antwort_datum,))
                    firmen = [row['firma'] for row in cursor.fetchall() if row.get('firma')]
                    if firmen:
                        db_context += f" Firmen mit Termin am {antwort_datum}: {', '.join(firmen)}."
                    else:
                        db_context += f" Für {antwort_datum} wurden keine Firmen mit Terminen gefunden."
                    cursor.close()
                    conn.close()
                    app.logger.info(f"[DB-ABFRAGE] Firmen für {antwort_datum}: {', '.join(firmen)}")
                except Exception as e:
                    app.logger.error(f"[DB-Fehler bei Firmenabfrage]: {e}")
                    db_context += f" [DB-Fehler bei Firmenabfrage: {e}]"
    if next_termin_name:
        # Gemeinsame Agentenlogik nutzen (wie beim E-Mail-Agenten)
        try:
            db_context += find_next_appointment_for_name(next_termin_name)

        except Exception as e:
            app.logger.info(f"[DB-ABFRAGE] Nächster Termin für {next_termin_name}: {row['naechster_termin'] if row else None}")
            db_context += f" [DB-Fehler: {e}]"
            app.logger.error(f"[DB-Fehler bei Terminabfrage]: {e}")
    elif name_match:
        # Auch hier: Gemeinsame Agentenlogik nutzen
        db_context += find_next_appointment_for_name(name_match)
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            # Zuerst: Firmensuche
            cursor.execute("SELECT id, name FROM clients WHERE name LIKE %s", (f"%{name_match}%",))
            firmen_treffer = cursor.fetchall()
            if firmen_treffer:
                db_context += f" Firmenname gefunden: {', '.join([f['name'] for f in firmen_treffer])}."
                app.logger.info(f"[DB-ABFRAGE] Firmenname gefunden: {', '.join([f['name'] for f in firmen_treffer])}")
            # Danach wie gehabt: Kundensuche
            app.logger.info(f"[DB-QUERY] Suche letzten Termin: SELECT MAX(datum) as letzter_termin, kunde FROM termine WHERE kunde LIKE '%{name_match}%'")
            cursor.execute("""
                SELECT MAX(datum) as letzter_termin, kunde
                FROM termine
                WHERE kunde LIKE %s
            """, (f"%{name_match}%",))
            row = cursor.fetchone()
            if row and row['letzter_termin']:
                db_context += f" Letzter Termin für {name_match}: {row['letzter_termin']}."
            else:
                # Fuzzy-Suche für Firmenname
                cursor.execute("SELECT name FROM clients")
                alle_firmen = [r['name'] for r in cursor.fetchall()]
                from difflib import get_close_matches
                vorschlaege_firma = get_close_matches(name_match, alle_firmen, n=3, cutoff=0.4)
                app.logger.info(f"[DB-ABFRAGE] Firmen-Fuzzy-Vorschläge für '{name_match}': {vorschlaege_firma}")
                if not alle_firmen:
                    db_context += " Es sind keine Firmen in der Datenbank hinterlegt."
                elif vorschlaege_firma:
                    db_context += f" Kein exakter Firmenname gefunden. Ähnliche Firmennamen: {', '.join(vorschlaege_firma)}."
                else:
                    db_context += f" Kein Firmenname oder ähnliche Firmen gefunden."
                # Suche nach ähnlichen Namen
                cursor.execute("SELECT DISTINCT kunde FROM termine WHERE kunde IS NOT NULL")
                alle_kunden = [r['kunde'] for r in cursor.fetchall()]
                from difflib import get_close_matches
                vorschlaege = get_close_matches(name_match, alle_kunden, n=3, cutoff=0.4)
                if vorschlaege:
                    db_context += f" Für {name_match} wurde kein Termin gefunden. Ähnliche Kundennamen: {', '.join(vorschlaege)}."
                else:
                    db_context += f" Für {name_match} wurde kein Termin gefunden und keine ähnlichen Namen entdeckt."
            cursor.close()
            conn.close()
            app.logger.info(f"[DB-ABFRAGE] Letzter Termin für {name_match}: {row['letzter_termin'] if row else None}")
        except Exception as e:
            app.logger.error(f"[DB-Fehler bei Terminabfrage]: {e}")
            db_context += f" [DB-Fehler: {e}]"
        except Exception as e:
            app.logger.error(f"[DB-Fehler bei Terminabfrage]: {e}")
            db_context += f" [DB-Fehler: {e}]"
    # --- System-Prompt klarstellen ---
    # Nutze zentrale Agentenfunktion für die Antwortgenerierung
    user_msg = last_user_msg or ""
    answer = agent_respond(user_msg, channel="chat")
    return jsonify({'answer': answer})

if __name__ == "__main__":
    app.run(debug=True)
