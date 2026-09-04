# USSA SMART HUB V2.4.5 — FIX REALE

Correzioni:
- header globale fisso e non ricreato, con layout canonico 1080×1920;
- USSA giallo / SMART HUB bianco;
- spazi delle schermate interni riallineati sotto header;
- percorsi trasferte generati una sola volta in fase di deploy tramite viabilità reale OSRM e salvati in routes.json;
- nessun routing live durante l’uso del totem;
- nessuna linea retta/fittizia se la generazione del percorso fallisce.

Caricare TUTTO il contenuto nel branch V2. Render eseguirà `build_routes.py` durante il build.
