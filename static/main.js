document.getElementById("laden").addEventListener("click", function() {
    const datum = document.getElementById("datum").value;
    if (!datum) {
        alert("Bitte ein Datum wählen!");
        return;
    }
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

            // Sortiere nach Zeit
            data.sort((a, b) => {
                const timeA = a.zeit.split(" - ")[0];
                const timeB = b.zeit.split(" - ")[0];
                return timeA.localeCompare(timeB);
            });

            let html = "";
            data.forEach(t => {
                html += `
                <div class="card shadow-sm">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <span class="time-badge">
                                <i class="bi bi-clock"></i> ${t.zeit}
                            </span>
                            <span class="badge bg-primary">
                                <i class="bi bi-building"></i> ${t.firma}
                            </span>
                        </div>
                        
                        <div class="row g-3">
                            <div class="col-md-6">
                                <h5 class="card-subtitle mb-2">
                                    <i class="bi bi-person"></i> Kunde
                                </h5>
                                <p class="card-text">
                                    ${t.kunde ? t.kunde : "-"}<br>
                                    ${t.kunde_email ? `<small class="text-muted"><i class="bi bi-envelope"></i> ${t.kunde_email}</small>` : ""}
                                </p>
                            </div>
                            
                            <div class="col-md-6">
                                <h5 class="card-subtitle mb-2">
                                    <i class="bi bi-person-badge"></i> Masseur
                                </h5>
                                <p class="card-text">
                                    ${t.masseur}<br>
                                    ${t.masseur_email ? `<small class="text-muted"><i class="bi bi-envelope"></i> ${t.masseur_email}</small>` : ""}
                                </p>
                            </div>
                        </div>
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
});
