# USSA SMART HUB V2.4 — MEGA FIX

Aggiornamento V2 per kiosk 1080×1920.

Principali interventi:
- header universale sempre visibile; logo USSA centrale = Home immediata;
- tasto indietro mantiene la navigazione locale;
- dettaglio partita riproporzionato e data/ora perfettamente unificati;
- nuovo blocco STATS comparativo, già pronto anche con pochi/zero risultati;
- gare in casa compatte: niente mappa/percorso/QR percorso;
- trasferte: percorso indicativo locale e istantaneo, senza routing live;
- una sola mappa nella scheda, ingrandibile nella pagina MAPPA;
- QR calendario sempre; QR percorso solo trasferta;
- righe Home con geometria identica per CASA/TRASFERTA;
- routes.json locale: nessuna chiamata di routing necessaria all'apertura.

Caricare tutti i file nel branch V2 sostituendo gli omonimi. Non modificare main/V1.


## V2.4.4 — Header + percorsi indicativi
- Header globale invariato nella posizione ma riproporzionato: nessun taglio, logo centrale più leggibile, USSA giallo e SMART HUB bianco.
- Percorsi delle trasferte restano completamente statici: nessun routing live durante l’uso del totem.
- Le geometrie sono salvate in routes.json come tracciati indicativi a più punti, pensati per rendere visivamente un possibile percorso sulla cartografia.
- Distanze e tempi restano indicativi.
