# USSA SMART HUB · V2 portrait

V2 parte dalla V1 e introduce il layout kiosk verticale.

## Home
- Header compatto con logo ufficiale USSA, titolo, data/ora.
- Blocco alto: prossimi appuntamenti (solo gare future + eventi USSA), scroll manuale verso il futuro.
- Blocco centrale: ORA IN CAMPO + INFO; la segreteria viene evidenziata solo durante l'orario di apertura.
- Blocco basso: griglia squadre.
- Messaggi di attesa neutri: nessun riferimento alla sorgente CSI.

## Scheda squadra
Predisposta per allenamenti, staff, rosa, classifica completa, marcatori, gare disputate e prossime partite.

## Dati
- `teams.json`: anagrafica squadra + collegamenti sorgenti + training/staff/roster.
- `events.json`: eventi USSA extra-CSI.
- `hub.json`: Stadium, segreteria, contatti e impostazioni generali.
- Il parser V1 resta come fallback durante la migrazione progressiva a CSI LIVE; i campi `csi_live_url` già verificati sono salvati in `teams.json`.

## Avvio
`pip install -r requirements.txt`
`uvicorn server:app --host 0.0.0.0 --port 8000`
