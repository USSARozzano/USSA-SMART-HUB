# USSA SMART HUB V2.4.8 — PREVIEW HOME FIX

Fix cumulativo basato sulla V2.4.7.

## Correzione anteprima temporale
La modalità preview ora è gestita direttamente dal frontend e non dipende dall'endpoint Render per gli allenamenti.

Esempio venerdì ore 18:15:
`?previewWeekday=5&previewTime=18:15`

Con questi parametri vengono simulati insieme:
- ORA IN CAMPO (allenamenti, con rotazione)
- stato SEGRETERIA APERTA ORA

Rimuovendo completamente i parametri dall'URL, entrambe le funzioni tornano automaticamente a giorno e ora reali.

Il calendario generale continua volutamente a usare le date reali.
