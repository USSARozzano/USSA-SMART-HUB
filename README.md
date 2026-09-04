# USSA SMART HUB V2.4.10 — U14 FIGC PROSSIME PARTITE

Fix mirata della scheda UNDER 14 > FIGC:
- PROSSIME PARTITE carica le fixture FIGC reali già usate dal calendario Home.
- Le card gara sono cliccabili con listener JS affidabile (niente onclick inline annidati).
- Toccando una gara si apre la stessa scheda PARTITA usata dal calendario generale Home.
- Il tasto indietro torna alla scheda UNDER 14 FIGC con PROSSIME PARTITE selezionato.
- GARE DISPUTATE usa la stessa infrastruttura quando esisteranno gare passate.
- Fallback su /api/home/upcoming se l'endpoint squadra non restituisce dati.

Include anche tutte le modifiche della V2.4.9 perché parte dal pacchetto completo V2.4.8 con index V2.4.9.
