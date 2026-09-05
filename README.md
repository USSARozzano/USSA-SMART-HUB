USSA SMART HUB — V2.4.20

Novità V2.4.20:
- pulsanti delle schede squadra su due righe: ATLETI + STAFF, poi le funzioni sportive disponibili;
- fascia allenamenti compatta, con sede comune separata e giorni/orari affiancati;
- tastierino PIN numerico integrato, centrale e compatto;
- cifre del PIN sempre mascherate da asterischi;
- scelta atleta bloccata fino alla verifica del PIN.

Fix principale:
- nuova area INFO con Segreteria, Social, Dirigenza, Partner & Sponsor;
- Spikey usato solo nella landing INFO, senza modifiche alla canotta;
- organigramma senza foto inventate;
- sezione ATLETI per tutte le squadre con 15 placeholder;
- votazione Migliore in Campo con PIN squadra, sblocco automatico a +45 minuti e blocco doppio voto;
- backoffice mensile su /backoffice;
- modalità test voto: aggiungere ?testVote=1 all'URL del totem.

Persistenza voti:
- il database SQLite viene creato automaticamente;
- per Render produzione impostare VOTES_DB_PATH verso un disco persistente (es. /var/data/votes.db) oppure collegare storage persistente.

IMPORTANTE:
- PIN_VOTAZIONE_USSA.txt contiene PIN in chiaro: NON caricarlo su GitHub.
- vote_pins.json contiene solo hash/salt e va caricato.
- non caricare cartelle __pycache__ se dovessero comparire localmente.
