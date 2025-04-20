// Hilfsfunktion zum Laden und Anzeigen der Termine
function loadAndDisplayAppointments(datum, isCronjobPreview = false) {
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
                return;
            }

            // Gruppiere nach Firma und Masseur
            const groupedByCompany = {};
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

            // Generiere alle möglichen Zeitslots (von 10:00 bis 18:00 im 20-Minuten-Takt)
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
                        <table class="table table-bordered table-hover">
                            <thead class="table-light">
                                <tr>
                                    <th class="time-column">Zeit</th>
                                    <th>Status / Kunde</th>
                                </tr>
                            </thead>
                            <tbody>`;

                // Füge alle Zeitslots hinzu
                allTimeSlots.forEach(time => {
                    const termin = termine[time];
                    const isFree = !termin;
                    const shouldDelete = isCronjobPreview && isFree && (!firstBookedSlot || time < firstBookedSlot);
                    
                    html += `
                        <tr class="${shouldDelete ? 'slot-to-delete' : (isFree ? 'slot-free' : 'slot-booked')}">
                            <td class="time-column">
                                <i class="bi bi-clock"></i> ${time}
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
        })
        .catch(err => {
            document.getElementById("termine").innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i> Fehler beim Laden der Termine.
                </div>`;
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
    // Setze das Datum auf übermorgen
    const dayAfterTomorrow = new Date();
    dayAfterTomorrow.setDate(dayAfterTomorrow.getDate() + 2);
    const datum = dayAfterTomorrow.toISOString().split('T')[0];
    
    // Setze das Datum im Input-Feld
    document.getElementById("datum").value = datum;
    
    // Zeige die Vorschau an
    loadAndDisplayAppointments(datum, true);
});
