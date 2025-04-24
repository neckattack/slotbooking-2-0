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

- Hier können beliebige Markdown-Dokumente ergänzt werden.
