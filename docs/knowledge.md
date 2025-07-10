# neckattack Agent Knowledge Base



Wie komme ich ins Portal?

Dein Profil auf Blue ist jetzt aktiv: https://marketplace.neckattack.net/dashboard
Unter "mein Konto" → Kontoinformationen kannst du noch deine Daten korrigieren (Tel.nr., Foto etc.).

Anfragen annehmen:
Im Dashboard/Armaturenbrett findest du zwei große Boxen. Die grüne Box "kommende Jobs" zeigt dir alle Einladungen. Klick auf einen Titel und dann auf "bin interessiert", wenn dich der Job interessiert. Du bist dann noch nicht zugeteilt, kannst aber Zusatzinfos in den Chat unter dem Job schreiben (neben deinem Foto).
Wenn du zugeteilt wirst, bekommst du eine Mail. Dann musst du nochmal in die grüne Box und zu dem Job gehen und ihn "bestätigen". Das letzte OK geben immer die Masseure. Das ist der grüne Button unten, neben deinem Foto: "bestätigen".
Wenn der Job fertig ist, landet er in der blauen Box "alte Jobs". Dort kannst du ihn als "geschlossen markieren" und dann landet das Geld automatisch in deinem Wallet/Geldbeutel. Dort einfach deine Bankdaten eintragen und auf "auszahlen" drücken.

Geld auszahlen:
Wenn der Job fertig ist, landet er in der blauen Box "alte Jobs". Dort kannst du ihn als "geschlossen markieren" und das Geld wird automatisch in deinem Wallet/Geldbeutel gutgeschrieben. Dort einfach deine Bankdaten eintragen und auf "auszahlen" drücken.

Steuerpflicht:
Auf deinem Profil unter „Mein Geldbeutel“ findest du oben rechts „Zahlungsinfos hinzufügen“. Bei der Frage „Zahlst du MwSt?“ gibst du dann „Ja“ an – die Steuer wird dann automatisch berechnet und hinzugefügt.

Jobs finden:
Wir laden dich zu jedem Job im Umkreis von 100 km ein. Du bekommst jedes Mal auch eine E-Mail mit der Einladung. Wichtig ist, dass deine Wohnadresse stimmt :)


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

---

### Aktuelle FAQ für Masseure (Stand: Juli 2025)

**Wie komme ich denn jetzt in mein Portal?**

Dein Profil auf Blue ist jetzt aktiv:
https://marketplace.neckattack.net/dashboard

Unter "mein Konto" -> “Kontoinformationen” kannst du noch deine Daten korrigieren (Tel.nr., Foto etc....)

**Wie kann ich die Jobanfrage annehmen?**

Im Dashboard / Armaturenbrett findest du 2 große Boxen. Die grüne Box "kommende Jobs" zeigt dir alle Einladungen.
Klick auf einen Titel und dann auf "bin interessiert", wenn dich der Job ein bisschen interessiert.
Du bist dann noch nicht zugeteilt, kannst aber Zusatzinfos in den Chat unter dem Job schreiben (neben deinem Foto)

Wenn ich dich zuteile, bekommst du eine Mail. Dann musst DU nochmal in die grüne Box und zu dem Job gehen und ihn "bestätigen".
Das letzte OK geben immer die Masseure.
Das ist der grüne Button unten, neben deinem Foto: "bestätigen".

Wenn der Job fertig ist, landet er in der blauen Box: "alte Jobs".
Dort kannst du ihn als "geschlossen markieren" und dann landet das Geld automatisch in deinem Wallet / Geldbeutel.
Dort einfach deine Bankdaten eintragen, und auf "auszahlen" drücken.

**Wie komme ich zu meinem Geld?**

Wenn der Job fertig ist, landet er in der blauen Box: "alte Jobs".
Klick den Titel noch mal an und dann auf den Button (oben rechts): “als abgeschlossen markiren”. Nachdem du dein Feedback eingetragen hast, können wir den Job schließen und das Geld landet automatisch in deinem wallet / Geldbeutel.
Dort einfach deine Bankdaten eintragen und auf "auszahlen" drücken.

**Ich bin steuerpflichtig.**

In deinem Profil unter “Mein Geldbeutel” findest du oben rechts “Zahlungsinfos hinzufügen”. Bei der Frage “Zahlst du MwSt?” gibst du dann “Ja” an und fügst die Steuernummer hinzu - die Steuer wird dann automatisch berechnet und der Rechnung hinzugefügt.

**Wie kann ich Jobs finden?**

Wir laden dich zu jedem Job im Umkreis von 100km ein.
Und du bekommst jedes Mal auch eine E-Mail mit der Einladung.
Wichtig ist, dass deine Wohnadresse stimmt :)

**Wo kann ich parken?**

Wo du parken kannst, findest du im Bereich “Spezielle Anweisungen” in der Jobbeschreibung. Diese Informationen werden dir mitgeteilt, nachdem dir der Job zugewiesen wurde.

**Danke für die Jobeinladung. Ich bin interessiert. Was soll ich tun?**

Super, das freut uns! Wenn du den Job annehmen möchtest, klick auf das Jobangebot und oben rechts auf den Button “bin interessiert”. Wenn alles passt, wird dir der Job zugewiesen. Du bekommst dann eine Bestätigungs-Mail.

**Ich hab versehentlich “interessiert” gedrückt.**

Kein Problem - du kannst gerne beim Jobangebot eine Nachricht im Chat hinterlassen und uns mitteilen, dass es ein Versehen war und du kein Interesse hast. Alternativ kannst du auch eine Mail an Johanna oder Sonja (johanna@neckattack.net oder sonja@neckattack.net) schreiben.

**Ich kann für einen zugeteilten Termin doch nicht arbeiten.**

Das kann passieren! Wichtig ist nur, dass du uns so bald wie möglich darüber informierst, sodass wir einen Ersatz finden können. Schreib dazu einfach eine Mail an Johanna oder Sonja (johanna@neckattack.net oder sonja@neckattack.net ) oder ruf an unter +497113583609.

**Wo ist mein Geld?**

Nachdem du den Job beendet hast, musst du den Job im Blue abschließen. Geh dazu in deinem Profil auf “Meine Jobs”, und auf den Job, den du abschließen möchtest. Klick dann auf “als abgeschlossen markieren” und hinterlasse ein Feedback:
- War alles ok?
- Von wann bis wann warst du da
- bei einem Job mit Slotlisten angeben wie viele Personen massiert wurden
- sonstige relevante Information
Danach wird dir das Geld in deinen online Geldbeutel übertragen. Von dort kannst du dir das Guthaben auszahlen lassen. Die Rechnungen werden immer freitags bearbeitet - d.h. spätestens am Dienstag hast du dein Geld auf deinem Konto.

**Ich habe eine Einladung bekommen. Was soll ich jetzt tun?**

Wenn du den Job annehmen möchtest, klick auf das Jobangebot und oben rechts auf den Button “bin interessiert”. Wenn alles passt, wird dir der Job zugewiesen. Du bekommst dann eine Bestätigungs-Mail.

**Ich verstehe das Wallet nicht.**

Immer, wenn du einen Job abgeschlossen hast, wird dir das Geld in deinen online Geldbeutel (“wallet”) übertragen. Von dort kannst du dir das Guthaben auszahlen lassen - bitte füge dazu deine Zahlungsinfos hinzu (IBAN, Steuernummer etc). 
Die Rechnungen werden immer freitags bearbeitet - d.h. spätestens am Dienstag hast du dein Geld auf deinem Konto.

**Ich finde meine Rechnung / Gutschrift nicht.**

Deine Rechnungen findest du in deinem online Geldbeutel unter “history”. Du kannst dir die Rechnung als pdf downloaden.

**Bei meinem Job steht “voll” - was heißt das?**

Wenn bei deinem Job “voll” steht, heißt das, dass er besetzt ist.
Wenn der Job mit DIR besetzt ist, findest du ihn in deinem Profil in der grünen Box “kommende Jobs”.

**In meiner Rechnung fehlt ein Job.**

In deinem Wallet kannst du unten auf "history" klicken.
Dort sieht man, wann du deine letzte Rechnung beantragt hast:
Mit dem kleinen Plus rechts kannst du auch  noch mal kontrollieren, welche Jobs bei dieser Rechnung draufstehen.
Die Rechnungen werden alle immer freitags bearbeitet.
Das heißt, dass du dein Geld spätestens am Dienstag am Konto hast.
Dann wird der Status auch nicht mehr "wait" sondern "paid" lauten.
Ich hoffe, ich konnte dir helfen.

**Ich habe Geld von den Teilnehmern kassiert. Was soll ich jetzt tun?**

Nachdem du den Job beendet hast, musst du den Job im Blue abschließen. Geh dazu in deinem Profil auf “Meine Jobs”, und auf den Job, den du abschließen möchtest. Klick dann auf “als abgeschlossen markieren” und hinterlasse ein Feedback:
- War alles ok?
- Von wann bis wann warst du da
- bei einem Selbstzahler-Job angeben, wie viele Personen massiert wurden
- wieviel Geld hast du kassiert
- sonstige relevante Information
Dieser Job wird dann von uns mit einem Minus-Betrag abgeschlossen. Das ist das Geld, das du uns schuldest. Der Minus-Betrag wird von deiner nächsten Rechnung abgezogen.

**Wie kann ich meinen Job abschließen?**

Nachdem du den Job beendet hast, musst du den Job im Blue abschließen. Geh dazu in deinem Profil auf “Meine Jobs”, und auf den Job, den du abschließen möchtest. Klick dann auf “als abgeschlossen markieren” und hinterlasse ein Feedback:
- War alles ok?
- Von wann bis wann warst du da
- bei einem Selbstzahler-Job angeben, wie viele Personen massiert wurden
- sonstige relevante Information
Danach wird dir das Geld in deinen online Geldbeutel übertragen. Von dort kannst du dir das Guthaben auszahlen lassen. Die Rechnungen werden immer freitags bearbeitet - d.h. spätestens am Dienstag hast du dein Geld auf deinem Konto.

**Ich will auf eine Einladung zusagen, es gibt aber keinen Button**

Wenn du auf eine Einladung zusagen möchtest, aber keinen Button findest, bedeutet das, dass der Job bereits von einem anderen Masseur besetzt wurde.

**Gibt es demnächst Jobs in meiner Stadt?**

Du kannst gerne den Marketplace nach Jobs in deiner Nähe durchstöbern. Geh dazu auf “Jobs durchsuchen” und gib dazu bei “Suche nach Nachbarschaft” die Stadt ein, und es erscheinen alle zukünftigen Jobs.
Wir laden dich zu jedem Job im Umkreis von 100km ein. Zusätzlich bekommst du jedes Mal eine E-Mail mit der Einladung. Wichtig ist, dass deine Wohnadresse stimmt :)

**Ich habe eine neue Adresse. Wo soll ich die eintragen?**

Du kannst deine Kontaktinformationen auf deinem Profil ändern. Gehe dazu auf “Mein Konto”, und unter “Adresse” kannst du deine aktuelle Adresse eingeben. Danach auf “Speichern” und fertig :)

**Wie funktioniert die Abrechnung?**

Nachdem du den Job beendet hast, musst du den Job im Blue abschließen. Geh dazu in deinem Profil auf “Meine Jobs”, und auf den Job, den du abschließen möchtest. Klick dann auf “als abgeschlossen markieren” und hinterlasse ein Feedback:
- War alles ok?
- Von wann bis wann warst du da
- bei einem Selbstzahler-Job angeben, wie viele Personen massiert wurden
- sonstige relevante Information
Danach wird dir das Geld in deinen online Geldbeutel übertragen. Von dort kannst du dir das Guthaben auszahlen lassen. Die Rechnungen werden immer freitags bearbeitet - d.h. spätestens am Dienstag hast du dein Geld auf deinem Konto.

**Wo finde ich die Informationen zu meinem Job? Parkplatz etc.**

Nachdem dir der Job zugeteilt wurde. findest du die Infos zu Kontaktperson vor Ort, Parkplatz etc. in der Jobbeschreibung "spezielle Anweisungen" - diese sieht nur der zugeteilte Masseur.

**Kommen noch andere Masseure zum Job?**

Wenn in der Jobüberschrift steht “Masseur I / Masseur II / Masseur III,...” bedeutet das, dass noch andere Masseure beim Job dabei sein werden. Wenn nichts dabei steht, ist der Job nur für einen Masseur.

**Was muss ich mitnehmen?**

In der Jobbeschreibung findest du alle Informationen, welches Equipment du mitbringen musst. 
Grundsätzlich sind folgende Items notwendig:
- Massagestuhl oder -liege
- Einmalauflagen
- Desinfektion
- evtl. Entspannungsmusik
Bitte lies die Beschreibung genau durch - dort findest du alle zusätzlichen Details je nach Job.

**Wo kann ich ein Feedback abgeben?**

Nachdem du den Job beendet hast, musst du den Job im Blue abschließen. Geh dazu in deinem Profil auf “Meine Jobs”, und auf den Job, den du abschließen möchtest. Klick dann auf “als abgeschlossen markieren” und hinterlasse ein Feedback:
- War alles ok?
- Von wann bis wann warst du da
- bei einem Selbstzahler-Job angeben, wie viele Personen massiert wurden
- sonstige relevante Information

**Ist der Job am xx.xx. fix? Ich habe nur auf interessiert geklickt und dann passierte erstmal nichts.**

Hallo! Bitte schreib Fragen oder Kommentare immer unter dem Job in den Chat. Auf jeden Fall: wenn ich dich zugeteilt hätte, hättest du eine Bestätigungs-Mail bekommen. Wenn du diese noch nicht hast, hab ich den Job wahrscheinlich noch nicht vergeben.
Die Infos zu Kontaktperson vor Ort etc ... stehen DANN in der Jobbeschreibung "spezielle Anweisungen" - diese sieht nur der zugeteilte Masseur.

**Ich bin noch in Ausbildung.**

Das ist kein Problem. (ausführlicher)

**Ich habe keine Steuernummer da ich noch kein Gewerbe angemeldet habe**

Das ist kein Problem - du kannst in deinem online Geldbeutel unter “Zahlungsinfos hinzufügen” bei Steuernummer: “00000” reinschreiben.

**Ich kann unter “post review” keine Sterne anklicken**

Diese Funktion ist derzeit noch nicht aktiv, da Unternehmen aktuell noch keinen Zugriff auf unser Portal haben. Sobald dieser Zugang in Zukunft möglich ist, wird auch dieses Feedback gewünscht. Aktuell ist das jedoch noch nicht relevant. 🙂

**Ich habe keine IBAN, ich möchte gerne per PayPal bezahlt werden.**

Gerne können wir dich per PayPal bezahlen. Dazu gibst du einfach beim Feld IBAN “00000” ein, und im Feld “PayPal” deine PayPal-Nummer.

---

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
  