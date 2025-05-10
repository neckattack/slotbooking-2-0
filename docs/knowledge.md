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

---

## FAQ für Masseure (Blue Portal)

**Wie komme ich denn jetzt in mein Portal?**

Dein Profil auf Blue ist jetzt aktiv:
https://marketplace.neckattack.net/dashboard

Unter "mein Konto" → Kontoinformationen kannst du noch deine Daten korrigieren (Tel.nr., Foto etc....)

**Wie kann ich die Anfragen annehmen?**

Im Dashboard / Armaturenbrett findest du 2 große Boxen. Die grüne Box "kommende Jobs" zeigt dir alle Einladungen.
Klick auf einen Titel und dann auf "bin interessiert", wenn dich der Job ein bisschen interessiert.
Du bist dann noch nicht zugeteilt, kannst aber Zusatzinfos in den Chat unter dem Job schreiben (neben deinem Foto).

Wenn ich dich zuteile, bekommst du eine Mail. Dann musst DU nochmal in die grüne Box und zu dem Job gehen und ihn "bestätigen".
Das letzte OK geben immer die Masseure.
Das ist der grüne Button unten, neben deinem Foto: "bestätigen".

Wenn der Job fertig ist, landet er in der blauen Box: "alte Jobs".
Dort kannst du ihn als "geschlossen markieren" und dann landet das Geld automatisch in deinem Wallet / Geldbeutel.
Dort einfach deine Bankdaten eintragen, und auf "auszahlen" drücken.

**Wie komme ich zu meinem Geld?**

Wenn der Job fertig ist, landet er in der blauen Box: "alte Jobs".
Dort kannst du ihn als "geschlossen markieren" und dann landet das Geld automatisch in deinem Wallet / Geldbeutel.
Dort einfach deine Bankdaten eintragen und auf "auszahlen" drücken.

**Ich bin steuerpflichtig.**

Auf deinem Profil unter “Mein Geldbeutel” findest du oben rechts “Zahlungsinfos hinzufügen”. Bei der Frage “Zahlst du MwSt?” gibst du dann “Ja” an - die Steuer wird dann automatisch berechnet und hinzugefügt.

**Wie kann ich Jobs finden?**

Wir laden dich zu jedem Job im Umkreis von 100km ein.
Und du bekommst jedes Mal auch eine E-Mail mit der Einladung.
Wichtig ist, dass deine Wohnadresse stimmt :)


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


- **Wie finde ich freie Slots?**
  - Frage: "Welche Slots sind nächste Woche noch frei?"


<!-- Hier kannst du beliebig weitere FAQs für Masseure ergänzen! -->

- Hier können beliebige Markdown-Dokumente ergänzt werden.
**Woher weiß ich, dass meine Rechnung bezahlt wurde?**
  - Antwort: Logge dich zuerst in neckattack Blue ein: [nmarketplace.neckattack.net/login](https://nmarketplace.neckattack.net/login).  
    Klicke dann auf „Meine Geldbörse“ am linken Rand.  
    Rechts unten findest du den Abschnitt mit deinen Gutschriften.  
    Gutschriften können nur ausgezahlt werden für Jobs, die du als erledigt markiert hast und die auch von uns als „geschlossen“ (closed) markiert wurden.  
    Unter „Jobs“ → „History“ siehst du deine alten und neuen Gutschriften mit dem jeweiligen Status.
**Wann wird meine Rechnung bezahlt?**
  - Antwort: Wir zahlen Eingehende Rechnungen bzw. Gutschriften immer einmal pro Woche. STellst Du Deine Gutschrift oder Deine Rechnung bis Freitag, kommt Sie diret am Freitag in den Rechnungslauf und wird überwiesen Dann ist Dein Geld ca. am Dienstag spätestens verfügbar
  
**Wie erstelle ich eine Gutschrift?**
  - Antwort: Logge dich zuerst in neckattack Blue ein: [nmarketplace.neckattack.net/login](https://nmarketplace.neckattack.net/login).  
    Klicke dann auf „Meine Geldbörse“ am linken Rand.  
    Rechts unten findest du den Abschnitt mit deinen Gutschriften.  
    Gutschriften können nur ausgezahlt werden für Jobs, die du als erledigt markiert hast und die auch von uns als „geschlossen“ (closed) markiert wurden.  
    Unter „Jobs“ → „History“ siehst du deine alten und neuen Gutschriften mit dem jeweiligen Status.
**Wie erstelle ich eine Rechnung?**
  - Antwort: Du brauchst keine Rechnung zu erstellen, nur im System auf den close button drücken - dan schicken ud überweisen wir Dir eine Gutschrift mit dem bis zum Datum aufgelaufenen Geldern.
  