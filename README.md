# USSA SMART HUB V2.3 — Calendario / Partita / Mappa

Pacchetto cumulativo per branch `V2`. Non usare su `main`.

Aggiornamenti di questa build:
- correzione layout righe gare casalinghe nella dashboard (stessa geometria delle trasferte, nessun contenitore ereditato dalla Home);
- schermata PARTITA riorganizzata: data + ora in un unico blocco, rimosse etichette Trasferta/Andata;
- campo + indirizzo + distanza/tempo (solo trasferta) in un unico pannello;
- gara in casa: nessun percorso, nessun QR percorso, nessuna anteprima mappa, nessun pulsante mappa; resta QR calendario;
- gara in trasferta: una sola anteprima del tragitto USSA Stadium → campo, più pulsante per vista grande;
- mappe: corretto endpoint percorso con geometria stradale OSRM; renderer interno senza dipendenza da librerie mappe CDN; tile OpenStreetMap servite tramite backend;
- navigazione: MAPPA → indietro → PARTITA; PARTITA → indietro → provenienza (Home o scheda squadra);
- QR calendario e percorso mantenuti secondo il contesto.

Caricare tutti i file nel branch `V2`, sostituendo gli omonimi.
