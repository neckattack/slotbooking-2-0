# slotbooking-2-0

## Übersicht
Dieses Projekt zeigt Termine aus einer MySQL-Datenbank in einer modernen, responsiven Weboberfläche (Deutsch, Bootstrap).

## Einrichtung

1. **Dateien im Repository anlegen**  
   (Im GitHub-Webeditor oder Codespaces)

2. **Render.com Web Service einrichten**
   - Neues Web Service erstellen
   - GitHub-Repo auswählen
   - Build-Command: `pip install -r requirements.txt`
   - Start-Command: `gunicorn app:app`
   - Environment: Python 3.10+
   - Umgebungsvariablen setzen (DB_HOST, DB_USER, ...)

3. **Fertig!**  
   Die Seite ist jetzt online erreichbar.

## Nutzung

- Im Browser öffnen
- Datum wählen, auf „Termine anzeigen“ klicken
- Termine werden angezeigt

## Hinweise

- Datenbankzugangsdaten niemals öffentlich machen!
- Änderungen am Code einfach im GitHub-Webeditor oder Codespaces übernehmen – Render.com deployed automatisch.
