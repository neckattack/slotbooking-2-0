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
                div.innerHTML = "<div class='alert alert-info'>Keine Termine gefunden.</div>";
                return;
            }
            let html = "<div class='list-group'>";
            data.forEach(t => {
                html += `
                <div class="list-group-item">
                    <strong>Zeit:</strong> ${t.zeit}<br>
                    <strong>Kunde:</strong> ${t.kunde ? t.kunde : "-"}<br>
                    <strong>Kunden-E-Mail:</strong> ${t.kunde_email ? t.kunde_email : "-"}<br>
                    <strong>Firma:</strong> ${t.firma}<br>
                    <strong>Masseur:</strong> ${t.masseur}<br>
                    <strong>Masseur-E-Mail:</strong> ${t.masseur_email ? t.masseur_email : "-"}
                </div>`;
            });
            html += "</div>";
            div.innerHTML = html;
        })
        .catch(err => {
            document.getElementById("termine").innerHTML =
                "<div class='alert alert-danger'>Fehler beim Laden der Termine.</div>";
        });
});
