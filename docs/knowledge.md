# neckattack Agent Knowledge Base

Hier kannst du interne Regeln, Policies, Rollen und weitere Dokumente für den neckattack-Agenten ablegen.

## Beispiel: Rollen und E-Mail-Adressen

- **Admin:**
    - chris@neckattack.net → Rolle: Admin, Name: Chris
    - Weitere Admins können hier ergänzt werden.
- **Kunde:**
    - Alle anderen E-Mail-Adressen werden standardmäßig als Kunden behandelt, außer sie stehen explizit als Admin/Team in dieser Liste.

## Beispiel: Interne Regeln

- Antworten an Admins dürfen interne Informationen enthalten.
- Antworten an Kunden müssen besonders freundlich und datenschutzkonform sein.
- ...

## Datenbankstruktur neckattack

- **clients**: Firmenkunden
  - Felder: id, name (Firmenname)
- **dates**: Termine pro Firma
  - Felder: id, client_id (verknüpft mit clients.id), date (Datum), masseur_id (verknüpft mit admin.id)
- **times**: Zeit-Slots an einem Tag
  - Felder: id, date_id (verknüpft mit dates.id), time_start, time_end
- **reservations**: Buchungen eines Slots
  - Felder: id, time_id (verknüpft mit times.id), name (Kundenname), email
- **admin**: Masseure und Ansprechpartner
  - Felder: id, first_name, last_name, email

### Beziehungen:
- Jede Firma (`clients`) hat Termine (`dates`) an bestimmten Tagen.
- Jeder Termin kann mehrere Zeit-Slots (`times`) haben.
- Jeder Slot kann von einem Kunden (`reservations`) gebucht werden.
- Masseure (`admin`) können einem Termin zugeordnet sein.

## Weitere Policies, FAQ, etc.

### Verhaltensregeln wenn Masseure anfragen 

- Wenn eine Anfrage von einem Masseur kommt (Absender ist in der admin-Tabelle):
    - Antworte bevorzugt mit internen Informationen, z.B. eigene Einsatzzeiten, alle Termine, bei denen der Masseur eingeteilt ist, Hinweise zu freien Slots oder Vertretungen.
    - Antworte an Masseure besonders kollegial und direkt, z.B. mit „Hallo {Vorname}, ...“
    - Keine sensiblen Kundendaten an Masseure weitergeben, nur Slot-Status und eigene Buchungen.
    - Bei Unsicherheit, ob der Absender ein Masseur ist, prüfe die E-Mail-Adresse gegen die admin-Tabelle.

#### FAQ für Masseure

- **Wie erfahre ich meine nächsten Einsätze?**
  - Frage einfach: "Wann bin ich wieder eingeteilt?" oder "Zeig mir meine nächsten Termine."

- **Wie erfahre ich meine nächsten Einsätze?**
  - Frage: "Wann bin ich wieder eingeteilt?" oder "Zeig mir meine nächsten Termine."

- **Woher weiß ich, dass meine Rechnung bezahlt wurde?**
  - Antwort: Logge dich zuerst in neckattack Blue ein: [nmarketplace.neckattack.net/login](https://nmarketplace.neckattack.net/login).  
    Klicke dann auf „Meine Geldbörse“ am linken Rand.  
    Rechts unten findest du den Abschnitt mit deinen Gutschriften.  
    Gutschriften können nur ausgezahlt werden für Jobs, die du als erledigt markiert hast und die auch von uns als „geschlossen“ (closed) markiert wurden.  
    Unter „Jobs“ → „History“ siehst du deine alten und neuen Gutschriften mit dem jeweiligen Status.
- **Wie finde ich freie Slots?**
  - Frage: "Welche Slots sind nächste Woche noch frei?"

- **Woher weiß ich, dass meine Rechnung bezahlt wurde?**
  - Antwort: Logge dich zuerst in neckattack Blue ein: [nmarketplace.neckattack.net/login](https://nmarketplace.neckattack.net/login).  
    Klicke dann auf „Meine Geldbörse“ am linken Rand.  
    Rechts unten findest du den Abschnitt mit deinen Gutschriften.  
    Gutschriften können nur ausgezahlt werden für Jobs, die du als erledigt markiert hast und die auch von uns als „geschlossen“ (closed) markiert wurden.  
    Unter „Jobs“ → „History“ siehst du deine alten und neuen Gutschriften mit dem jeweiligen Status.

<!-- Hier kannst du beliebig weitere FAQs für Masseure ergänzen! -->

- Hier können beliebige Markdown-Dokumente ergänzt werden.
**Woher weiß ich, dass meine Rechnung bezahlt wurde?**
  - Antwort: Logge dich zuerst in neckattack Blue ein: [nmarketplace.neckattack.net/login](https://nmarketplace.neckattack.net/login).  
    Klicke dann auf „Meine Geldbörse“ am linken Rand.  
    Rechts unten findest du den Abschnitt mit deinen Gutschriften.  
    Gutschriften können nur ausgezahlt werden für Jobs, die du als erledigt markiert hast und die auch von uns als „geschlossen“ (closed) markiert wurden.  
    Unter „Jobs“ → „History“ siehst du deine alten und neuen Gutschriften mit dem jeweiligen Status.