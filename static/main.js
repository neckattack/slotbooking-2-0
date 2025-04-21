// Hilfsfunktion zum Laden und Anzeigen der Termine
function loadAndDisplayAppointments(datum, isCronjobPreview = false) {
    // TEST: Hole alle Slots inkl. Slot-ID, Status, Kunde/E-Mail
    fetch(`/api/slots?datum=${datum}`)
        .then(response => response.json())
        .then(data => {
            const div = document.getElementById("termine");
            div.innerHTML = "";
            if (!Array.isArray(data) || data.length === 0) {
                div.innerHTML = `<div class="alert alert-info"><i class="bi bi-info-circle"></i> Keine Slots für dieses Datum gefunden.</div>`;
                document.getElementById("delete_confirm").style.display = "none";
                return;
            }
            let html = `<div class="alert alert-warning"><b>Testmodus:</b> Alle Slots mit Slot-ID, Status, ggf. Kunde/E-Mail</div>`;
            data.forEach(company => {
                html += `<h4>${company.firma} (date_id: ${company.date_id})</h4>`;
                html += `<table class="table table-sm table-bordered"><thead><tr><th>Zeit</th><th>Slot-ID</th><th>Status</th><th>Kunde</th><th>E-Mail</th></tr></thead><tbody>`;
                company.slots.forEach(slot => {
                    html += `<tr>
                        <td>${slot.time_start}</td>
                        <td>${slot.time_id}</td>
                        <td>${slot.frei ? '<span class="badge bg-success">frei</span>' : '<span class="badge bg-danger">belegt</span>'}</td>
                        <td>${slot.kunde ? slot.kunde : '-'}</td>
                        <td>${slot.kunde_email ? `<a href="mailto:${slot.kunde_email}">${slot.kunde_email}</a>` : '-'}</td>
                    </tr>`;
                });
                html += `</tbody></table>`;
            });
            div.innerHTML = html;
            document.getElementById("delete_confirm").style.display = "none";
        })
        .catch(err => {
            document.getElementById("termine").innerHTML = `<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> Fehler beim Laden der Slots.</div>`;
            document.getElementById("delete_confirm").style.display = "none";
        });
    return;

    fetch(`/api/termine?datum=${datum}`)
        .then(response => response.json())
        .then(data => {
            const div = document.getElementById("termine");
            div.innerHTML = "";
            if (data.length === 0) {
                div.innerHTML = `
                    <div class="alert alert-info">
                        <i class="bi bi-info-circle"></i> Keine Termine für dieses Datum gefunden.
                    </div>`;
                document.getElementById("delete_confirm").style.display = "none";
                return;
            }

            // Gruppiere nach Firma und Masseur
            const groupedByCompany = {};
            let hasTermineToDelete = false;

            data.forEach(t => {
                if (!groupedByCompany[t.firma]) {
                    groupedByCompany[t.firma] = {
                        masseur: t.masseur,
                        masseur_email: t.masseur_email,
                        termine: {}
                    };
                }
                // Speichere den Termin mit der Startzeit als Schlüssel
                const startTime = t.zeit.split(" - ")[0];
                groupedByCompany[t.firma].termine[startTime] = t;
            });

            // Generiere alle möglichen Zeitslots
            const allTimeSlots = [];
            for (let hour = 10; hour <= 17; hour++) {
                for (let minute = 0; minute < 60; minute += 20) {
                    const time = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}:00`;
                    allTimeSlots.push(time);
                }
            }

            // Sortiere Firmen alphabetisch
            const sortedCompanies = Object.keys(groupedByCompany).sort();

            let html = "";
            if (isCronjobPreview) {
                html += `
                    <div class="alert alert-warning mb-4">
                        <h4 class="alert-heading">
                            <i class="bi bi-exclamation-triangle"></i> Cronjob Vorschau
                        </h4>
                        <p class="mb-0">
                            Rot markierte Termine würden gelöscht werden (freie Termine vor dem ersten besetzten Termin).
                        </p>
                    </div>`;
            }

            // Sammle alle zu löschenden Termine
            const termineToDelete = [];

            sortedCompanies.forEach(firma => {
                const { masseur, masseur_email, termine } = groupedByCompany[firma];
                
                // Finde den ersten besetzten Termin
                let firstBookedSlot = null;
                for (const time of allTimeSlots) {
                    if (termine[time]) {
                        firstBookedSlot = time;
                        break;
                    }
                }
                
                html += `
                <div class="company-section">
                    <div class="company-header">
                        <h3 class="mb-2">
                            <i class="bi bi-building"></i> ${firma}
                        </h3>
                        <div>
                            <i class="bi bi-person-badge"></i> <strong>${masseur}</strong>
                            ${masseur_email ? `
                                <br>
                                <a href="mailto:${masseur_email}" class="email-link">
                                    <i class="bi bi-envelope"></i> ${masseur_email}
                                </a>
                            ` : ''}
                        </div>
                    </div>
                    
                    <div class="table-responsive">
                        <table class="table table-bordered">
                            <thead>
                                <tr>
                                    <th class="time-column">Zeit / Slot-ID</th>
                                    <th>Status / Kunde</th>
                                </tr>
                            </thead>
                            <tbody>`;

                // Füge alle Zeitslots hinzu
                allTimeSlots.forEach(time => {
                    const termin = termine[time];
                    const isFree = !termin;
                    const shouldDelete = isCronjobPreview && isFree && (!firstBookedSlot || time < firstBookedSlot);
                    
                    if (shouldDelete) {
                        hasTermineToDelete = true;
                        termineToDelete.push({
                            firma,
                            time,
                            datum  // Füge das Datum hinzu
                        });
                    }
                    
                    let rowClass = isFree ? 'free-slot' : 'booked-slot';
                    if (shouldDelete) rowClass = 'delete-slot';
                    
                    html += `
                        <tr class="${rowClass}">
                            <td class="time-column">
                                <span class="time-badge">${time}</span>
                                <br>
                                <small class="text-muted">ID: ${termin.time_id || '-'}</small>
                            </td>
                            <td>
                                ${isFree ? `
                                    <i class="bi bi-calendar-check"></i> 
                                    ${shouldDelete ? 'WIRD GELÖSCHT' : 'FREI'}
                                ` : `
                                    <div>
                                        <strong>
                                            <i class="bi bi-person"></i> ${termin.kunde || '-'}
                                        </strong>
                                        ${termin.kunde_email ? `
                                            <br>
                                            <a href="mailto:${termin.kunde_email}" class="email-link">
                                                <i class="bi bi-envelope"></i> ${termin.kunde_email}
                                            </a>
                                        ` : ''}
                                    </div>
                                `}
                            </td>
                        </tr>`;
                });

                html += `
                            </tbody>
                        </table>
                    </div>
                </div>`;
            });
            
            div.innerHTML = html;

            // Zeige oder verstecke den Löschen-Button
            const deleteButton = document.getElementById("delete_confirm");
            if (isCronjobPreview && hasTermineToDelete) {
                deleteButton.style.display = "block";
                // Speichere die zu löschenden Termine am Button
                deleteButton.setAttribute('data-termine', JSON.stringify(termineToDelete));
            } else {
                deleteButton.style.display = "none";
            }
        })
        .catch(err => {
            document.getElementById("termine").innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i> Fehler beim Laden der Termine.
                </div>`;
            document.getElementById("delete_confirm").style.display = "none";
        });
}

// Event Listener für den normalen "Termine anzeigen" Button
document.getElementById("laden").addEventListener("click", function() {
    const datum = document.getElementById("datum").value;
    if (!datum) {
        alert("Bitte ein Datum wählen!");
        return;
    }
    loadAndDisplayAppointments(datum, false);
});

// Event Listener für den Cronjob-Button
document.getElementById("cronjob").addEventListener("click", function() {
    const datum = document.getElementById("cronjob_datum").value;
    if (!datum) {
        alert("Bitte ein Datum für den Cronjob wählen!");
        return;
    }
    
    // Setze das normale Datum auch auf das Cronjob-Datum für die Anzeige
    document.getElementById("datum").value = datum;
    
    // Zeige die Vorschau an
    loadAndDisplayAppointments(datum, true);
});

// Event Listener für den Löschen bestätigen Button
document.getElementById("delete_confirm").addEventListener("click", async function() {
    const termineToDelete = JSON.parse(this.getAttribute('data-termine') || '[]');
    if (!termineToDelete.length) {
        alert("Keine Termine zum Löschen gefunden!");
        return;
    }

    if (!confirm(`Möchten Sie wirklich ${termineToDelete.length} freie Termine löschen?`)) {
        return;
    }

    try {
        const response = await fetch('/api/termine/delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(termineToDelete)
        });

        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || 'Fehler beim Löschen der Termine');
        }

        // Erfolgreiche Löschung
        alert(`${result.deleted_count} Termine wurden erfolgreich gelöscht.`);
        
        // Aktualisiere die Ansicht
        const datum = document.getElementById("datum").value;
        loadAndDisplayAppointments(datum, false);
        
        // Verstecke den Löschen-Button
        this.style.display = "none";
        
    } catch (error) {
        alert(`Fehler: ${error.message}`);
    }
});
