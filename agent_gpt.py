import os
import openai
from datetime import datetime
from agent_core import find_next_appointment_for_name

openai.api_key = os.environ.get("OPENAI_API_KEY")

def agent_respond(user_message, channel="chat", user_email=None):
    """
    Liefert eine GPT-Antwort mit neckattack-Kontext und DB-Infos.
    - user_message: Die Frage/Bitte des Nutzers (Mailtext, Chat, ...)
    - channel: "chat", "email" etc.
    - user_email: falls bekannt, für Kontext (z.B. bei E-Mail)
    """
    # Kontextaufbau wie im Chatbot
    today_str = datetime.now().strftime('%Y-%m-%d')
    db_context = ""
    # Beispiel: Wenn nach "nächster Termin" gefragt wird, hole Termininfo
    if "nächster termin" in user_message.lower():
        name = user_email.split('@')[0] if user_email else "Unbekannt"
        db_context += find_next_appointment_for_name(name)
    # System-Prompt wie im Chatbot
    system_prompt = (
        f"Du bist ein KI-Assistent für die Slotbuchung bei neckattack. Das heutige Datum ist {today_str}.\n"
        "Beantworte alle Nutzerfragen stets auf Basis der echten Datenbankdaten und folge den internen Regeln.\n"
        "Wenn keine passenden Daten gefunden werden, erkläre das höflich und weise darauf hin.\n"
        "(Kanal: " + channel + ")\n"
        f"Datenbank-Kontext: {db_context}"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        return f"[Fehler bei GPT-Antwort: {e}]"
