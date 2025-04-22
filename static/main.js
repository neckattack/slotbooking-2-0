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
                // --- Freie Termine sammeln und Löschen-Button aktivieren ---
let freieTermine = [];
data.forEach(company => {
    // Slots robust nach Zeit sortieren (immer mit führenden Nullen!)
    const slots = [...company.slots].sort((a, b) => {
        const pad = t => t.split(':').map(x => x.padStart(2, '0')).join(':');
        return pad(a.time_start).localeCompare(pad(b.time_start));
    });
    // Finde Index des ersten belegten Slots
    let firstBookedIdx = slots.findIndex(slot => slot.frei === false);
    if (firstBookedIdx === -1) {
        // Wenn kein Termin belegt ist, KEINE freien Slots zum Löschen vorschlagen
        return;
    }
    // Alle freien Slots vor dem ersten belegten Slot sammeln
    for (let i = 0; i < firstBookedIdx; i++) {
        if (slots[i].frei === true) {
            freieTermine.push({
                firma: company.firma,
                datum: datum,
                zeit: slots[i].time_start,
                time_id: slots[i].time_id
            });
        }
    }
});
const deleteButton = document.getElementById("delete_confirm");
deleteButton.style.display = "block";
if (freieTermine.length > 0) {
    deleteButton.setAttribute('data-termine', JSON.stringify(freieTermine));
} else {
    deleteButton.setAttribute('data-termine', '[]');
}
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
            // --- Freie Termine sammeln und Löschen-Button aktivieren ---
let freieTermine = [];
data.forEach(company => {
    // Slots robust nach Zeit sortieren (immer mit führenden Nullen!)
    const slots = [...company.slots].sort((a, b) => {
        const pad = t => t.split(':').map(x => x.padStart(2, '0')).join(':');
        return pad(a.time_start).localeCompare(pad(b.time_start));
    });
    // Finde Index des ersten belegten Slots
    let firstBookedIdx = slots.findIndex(slot => slot.frei === false);
    if (firstBookedIdx === -1) {
        // Wenn kein Termin belegt ist, KEINE freien Slots zum Löschen vorschlagen
        return;
    }
    // Alle freien Slots vor dem ersten belegten Slot sammeln
    for (let i = 0; i < firstBookedIdx; i++) {
        if (slots[i].frei === true) {
            freieTermine.push({
                firma: company.firma,
                datum: datum,
                zeit: slots[i].time_start,
                time_id: slots[i].time_id
            });
        }
    }
});
const deleteButton = document.getElementById("delete_confirm");
deleteButton.style.display = "block";
if (freieTermine.length > 0) {
    deleteButton.setAttribute('data-termine', JSON.stringify(freieTermine));
} else {
    deleteButton.setAttribute('data-termine', '[]');
}
        })
        .catch(err => {
            document.getElementById("termine").innerHTML = `<div class="alert alert-danger"><i class="bi bi-exclamation-triangle"></i> Fehler beim Laden der Slots.</div>`;
            // --- Freie Termine sammeln und Löschen-Button aktivieren ---
let freieTermine = [];
data.forEach(company => {
    // Slots robust nach Zeit sortieren (immer mit führenden Nullen!)
    const slots = [...company.slots].sort((a, b) => {
        const pad = t => t.split(':').map(x => x.padStart(2, '0')).join(':');
        return pad(a.time_start).localeCompare(pad(b.time_start));
    });
    // Finde Index des ersten belegten Slots
    let firstBookedIdx = slots.findIndex(slot => slot.frei === false);
    if (firstBookedIdx === -1) {
        // Wenn kein Termin belegt ist, KEINE freien Slots zum Löschen vorschlagen
        return;
    }
    // Alle freien Slots vor dem ersten belegten Slot sammeln
    for (let i = 0; i < firstBookedIdx; i++) {
        if (slots[i].frei === true) {
            freieTermine.push({
                firma: company.firma,
                datum: datum,
                zeit: slots[i].time_start,
                time_id: slots[i].time_id
            });
        }
    }
});
const deleteButton = document.getElementById("delete_confirm");
deleteButton.style.display = "block";
if (freieTermine.length > 0) {
    deleteButton.setAttribute('data-termine', JSON.stringify(freieTermine));
} else {
    deleteButton.setAttribute('data-termine', '[]');
}
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
                // --- Freie Termine sammeln und Löschen-Button aktivieren ---
let freieTermine = [];
data.forEach(company => {
    // Slots robust nach Zeit sortieren (immer mit führenden Nullen!)
    const slots = [...company.slots].sort((a, b) => {
        const pad = t => t.split(':').map(x => x.padStart(2, '0')).join(':');
        return pad(a.time_start).localeCompare(pad(b.time_start));
    });
    // Finde Index des ersten belegten Slots
    let firstBookedIdx = slots.findIndex(slot => slot.frei === false);
    if (firstBookedIdx === -1) {
        // Wenn kein Termin belegt ist, KEINE freien Slots zum Löschen vorschlagen
        return;
    }
    // Alle freien Slots vor dem ersten belegten Slot sammeln
    for (let i = 0; i < firstBookedIdx; i++) {
        if (slots[i].frei === true) {
            freieTermine.push({
                firma: company.firma,
                datum: datum,
                zeit: slots[i].time_start,
                time_id: slots[i].time_id
            });
        }
    }
});
const deleteButton = document.getElementById("delete_confirm");
deleteButton.style.display = "block";
if (freieTermine.length > 0) {
    deleteButton.setAttribute('data-termine', JSON.stringify(freieTermine));
} else {
    deleteButton.setAttribute('data-termine', '[]');
}
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
                let firstBookedSlotIdx = allTimeSlots.findIndex(time => termine[time]);
                // Wenn kein Termin belegt ist, keine Löschkandidaten für diese Firma
                if (firstBookedSlotIdx === -1) firstBookedSlotIdx = null;
                
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
                allTimeSlots.forEach((time, idx) => {
                    const termin = termine[time];
                    const isFree = !termin;
                    // Löschkandidat: Slot ist frei UND liegt vor dem ersten belegten Slot dieser Firma
                    const shouldDelete = isCronjobPreview && isFree && (firstBookedSlotIdx !== null && idx < firstBookedSlotIdx);
                    
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
            // --- Freie Termine sammeln und Löschen-Button aktivieren ---
let freieTermine = [];
data.forEach(company => {
    // Slots robust nach Zeit sortieren (immer mit führenden Nullen!)
    const slots = [...company.slots].sort((a, b) => {
        const pad = t => t.split(':').map(x => x.padStart(2, '0')).join(':');
        return pad(a.time_start).localeCompare(pad(b.time_start));
    });
    // Finde Index des ersten belegten Slots
    let firstBookedIdx = slots.findIndex(slot => slot.frei === false);
    if (firstBookedIdx === -1) {
        // Wenn kein Termin belegt ist, KEINE freien Slots zum Löschen vorschlagen
        return;
    }
    // Alle freien Slots vor dem ersten belegten Slot sammeln
    for (let i = 0; i < firstBookedIdx; i++) {
        if (slots[i].frei === true) {
            freieTermine.push({
                firma: company.firma,
                datum: datum,
                zeit: slots[i].time_start,
                time_id: slots[i].time_id
            });
        }
    }
});
const deleteButton = document.getElementById("delete_confirm");
deleteButton.style.display = "block";
if (freieTermine.length > 0) {
    deleteButton.setAttribute('data-termine', JSON.stringify(freieTermine));
} else {
    deleteButton.setAttribute('data-termine', '[]');
}
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
    // Zeige den Löschen bestätigen Button IMMER an
    document.getElementById("delete_confirm").style.display = "block";
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

// --- Chat Button & Widget ---
(function() {
    const chatBtn = document.getElementById('chat_button');
    const chatWidget = document.getElementById('chat_widget');
    const chatClose = document.getElementById('chat_close');
    const chatSend = document.getElementById('chat_send');
    const chatInput = document.getElementById('chat_input');
    const chatMessages = document.getElementById('chat_messages');

    if (chatBtn && chatWidget && chatClose && chatSend && chatInput && chatMessages) {
        chatBtn.addEventListener('click', () => {
            chatWidget.style.display = 'block';
            chatInput.focus();
        });
        chatClose.addEventListener('click', () => {
            chatWidget.style.display = 'none';
        });
        function sendChatMsg() {
            const msg = chatInput.value.trim();
            if (!msg) return;
            const msgDiv = document.createElement('div');
            msgDiv.className = 'mb-2';
            msgDiv.innerHTML = `<span class="badge bg-primary me-2">Du</span> ${msg}`;
            chatMessages.appendChild(msgDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
            chatInput.value = '';
        }
        chatSend.addEventListener('click', sendChatMsg);
        chatInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                sendChatMsg();
                e.preventDefault();
            }
        });
    }
})();

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
