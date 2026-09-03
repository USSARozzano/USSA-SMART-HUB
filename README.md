# USSA SMART HUB V2 — MEGA PACK 04/09/2026

Target: **1080×1920 portrait · Windows 100% · Microsoft Edge kiosk · touch**.

Questo pacchetto sostituisce integralmente la precedente V2. **Non modifica la V1/main.**

## Contiene
- nuova Home portrait e righe Prossimi Appuntamenti ridisegnate;
- elenco reale squadre 2026/27, allenamenti e staff;
- scheda squadra a contenuto inferiore dinamico;
- pulsanti agonistici mostrati solo quando esistono dati effettivi;
- UNDER 14 con selettore FIGC/CSI;
- database completo calendario U14 FIGC e anagrafica campi/indirizzi/orari forniti;
- Home alimentata dalle gare FIGC reali;
- dettaglio partita futura con campo, indirizzo, casa/trasferta, percorso da USSA Stadium, QR percorso e QR calendario;
- UNDER 13 A 11 TEST CSI mantenuta temporaneamente per test integrazioni CSI;
- dettaglio CSI gara e correzione logica del comando indietro;
- idle screen 90 secondi;
- squadre future nascoste: PRIMI CALCI 2 e UNDER 10 VOLLEY.

## Render
Build: `pip install -r requirements.txt`

Start: `uvicorn server:app --host 0.0.0.0 --port $PORT`

## Nota dati
Il calendario U14 FIGC usa un'unica fonte `fixtures.json`, riutilizzata da Home e scheda squadra. Le date delle trasferte domenicali sono spostate alla domenica del relativo weekend sulla base del giorno/orario campo indicato come definitivo.
