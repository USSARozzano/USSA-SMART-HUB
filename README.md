# USSA SMART HUB V2.4.6 — LAYOUT RECOVERY

Ripristino controllato della V2 dopo la regressione introdotta dalle ultime patch.

- base grafica ripresa dalla V2.4.2/V2.4.1, cioè dalla versione precedente alla spaginazione;
- un solo header globale, fisso e sempre visibile;
- nessun doppio padding/offset nelle viste interne;
- schermata PARTITA torna immediatamente sotto l'header;
- STATS, loghi, data/ora, regole casa/trasferta e QR mantenuti;
- mappe cartografiche mantenute;
- percorsi stradali restano pre-generati al deploy tramite `build_routes.py` e letti da `routes.json` durante l'uso del kiosk;
- nessun routing live durante l'apertura della schermata.

Target: 1080×1920 portrait, Windows scaling 100%, Edge kiosk.
