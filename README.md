USSA SMART HUB — V2.4.27

Novità V2.4.27:
- pagina INFO riorganizzata con contenuti più ricchi e meglio distribuiti;
- inseriti i loghi ufficiali di sponsor e partner con QR verso i rispettivi siti;
- SPONSOR: TEMPOCASA ROZZANO e SOUTH BARBER;
- PARTNER: CERBA HEALTHCARE, GOLEE, RAREDREAMS MILANO e PARMA CALCIO ACADEMY;
- denominazioni aziendali testuali uniformate in maiuscolo;
- card della Dirigenza ridisegnate con lo stesso formato verticale delle figurine Atleti;
- card Staff e Collaboratori uniformate per dimensioni e proporzioni in tutte le squadre.

Novità V2.4.26:
- aggiunte alla dashboard 14 amichevoli interne di settembre 2026;
- squadre indicate sempre per esteso, con denominazioni BLUE e YELLOW;
- amichevoli mostrate come righe informative non cliccabili, senza dettaglio gara, QR o collegamenti ulteriori.

Correzioni V2.4.25:
- eliminate le sovrapposizioni tra le figurine con righe indipendenti ad altezza naturale;
- griglia Atleti riportata a tre colonne, con fotografia verticale e nome più grande;
- struttura della scheda squadra resa fissa fin dall'apertura, eliminando il movimento quando si preme ATLETI;
- icona sportiva e nome squadra ulteriormente ingranditi nei pulsanti della Home.

Novità V2.4.24:
- nella scheda ATLETI restano fissi intestazione, squadra, allenamenti e pulsanti; scorre soltanto la griglia delle figurine;
- figurine ridisegnate in formato verticale, già predisposto per fotografie a pieno riquadro;
- icone sportive e nomi delle squadre ulteriormente ingranditi nella Home;
- eliminata la didascalia sul numero di allenamenti settimanali;
- nei box allenamento giorno, orario e impianto occupano tre spazi identici.

Novità V2.4.23:
- importati 266 atleti dai tabulati Golee e assegnati alle rispettive squadre;
- esclusi Andrea Cimbali e Marco Paolini; Ivan Fichera resta solo in Eccellenza Yellow e Roberto Novella solo in Eccellenza Blue;
- PIN della squadra UNDER 13 A 11 · TEST CSI impostato a 000000;
- pulsanti squadra della Home riempiti meglio, con icona sportiva più grande e nome sotto più leggibile;
- proporzioni di ORA IN CAMPO e INFO riequilibrate;
- allenamenti disposti in due box completi con giorno, orario e impianto centrati;
- eliminato il riquadro introduttivo vuoto nelle schede squadra;
- statistiche del dettaglio gara raccolte in una fascia più compatta;
- testi e comportamento touch dei tastierini PIN rifiniti.

Correzione V2.4.22:
- pressione prolungata sul logo resa stabile sui touchscreen;
- il logo trattiene il puntatore per tutti i 5 secondi senza annullarsi per piccoli movimenti;
- il tocco breve continua a riportare alla Home.

Novità V2.4.21:
- accesso nascosto al backoffice tenendo premuto il logo USSA per 5 secondi;
- nuovo PIN backoffice: 021982;
- tastierino numerico compatto e mascherato anche nel backoffice;
- pulsante di ritorno diretto allo SMART HUB;
- scritte del tastierino voto riequilibrate e su una sola riga;
- eliminata ogni illuminazione dei tasti durante la pressione.

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
