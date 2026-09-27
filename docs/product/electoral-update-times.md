# Tempi di aggiornamento degli scrutini

La scheda **Tempi elettorali** del portale White List visualizza un dominio di ricerca territoriale separato dai record delle imprese. Il file pubblico `public-site/data/electoral.json` è prodotto da `scripts/elections/build_electoral_data.py`. I file sorgente non sono duplicati nel repository: l'output contiene URL di provenienza e impronte SHA-256 dei file precisi usati per la derivazione.

## Consultazioni incluse

| Consultazione | Perimetro nell'estratto | Province complete |
| --- | ---: | ---: |
| Europee 2024 | 107 | 101 |
| Politiche 2022, Camera | 106 | 100 |
| Politiche 2022, Senato | 104 | 97 |
| Referendum abrogativi 2022, quesiti 1–5 | 107 per quesito | 107 per quesito |
| Referendum costituzionale 2020 | 107 | 107 |

Il dataset delle politiche 2022 conserva alcuni grandi comuni in più righe di collegio; le sezioni di quelle righe vengono sommate, mentre il numero dei comuni distinti usa il codice Istat. Valle d'Aosta e altre aree con modalità di scrutinio o archiviazione particolari non sono colmate artificialmente nei perimetri Camera/Senato. Ogni quesito referendario 2022 è una consultazione distinta: riunire i cinque `dt_agg` in uno solo cancellerebbe l'ordine dello scrutinio.

## Misure e interpretazione

Il tempo zero è la **chiusura delle urne** nella data e ora locale italiana pertinente: 21 settembre 2020 alle 15:00; 12 giugno 2022 alle 23:00; 25 settembre 2022 alle 23:00; 9 giugno 2024 alle 23:00. L'inizio effettivo dello spoglio può essere successivo per riscontro dei votanti e per l'ordine prescritto delle schede: nel 2022 il Senato precede la Camera. Il tempo zero non va interpretato come identico inizio operativo dei diversi scrutini.

Per ogni riga comunale o di collegio, il numero delle sezioni è `sz_tot` (nel referendum 2020 `sezioni_totali`), e il timestamp è `dt_agg` (nel 2020 `dataAggiornamentoDati`). Un territorio è classificabile solo quando tutte le righe presenti nell'estratto hanno sezioni pervenute uguali al totale, valori validi e un timestamp. Le altre rimangono visibili fuori classifica.

* **Ultimo aggiornamento:** massimo dei timestamp delle righe, espresso in ore dalla chiusura delle urne.
* **Media ponderata:** somma dei tempi delle righe moltiplicati per il loro numero di sezioni, divisa per le sezioni totali.
* **90° percentile ponderato:** primo tempo in ordine crescente per cui il peso cumulato raggiunge il 90% delle sezioni.

Le ultime due misure attribuiscono convenzionalmente a **tutte le sezioni di una riga l'orario di aggiornamento della riga**. Non sono tempi rilevati sezione per sezione. Il significato operativo di `dt_agg` non è stato validato sui log SIEL: può includere correzioni posteriori. Il rank è descrittivo dell'estratto; non misura le risorse, l'efficienza o il ritardo imputabile alla Prefettura. Non è previsto un punteggio composito tra consultazioni.

## Provenienza e rigenerazione

Sorgenti onData (attribuzione nella pagina; verificare le condizioni di riuso di ciascun repository):

* `https://github.com/ondata/elezioni_europee_2024` — `data/insieme.csv`;
* `https://github.com/ondata/elezioni-politiche-2022` — `affluenza-risultati/dati/risultati/{camera,senato}-italia-comune_anagrafica.csv`;
* `https://github.com/ondata/elezioni_2022` — `referendum/output/{scrutini.csv,scrutini-anagrafica.csv}`;
* `https://github.com/ondata/elezioni_2020` — `referendum/output/scrutiniComuni.csv`.

Lo script accetta i sei percorsi con le opzioni `--european`, `--camera`, `--senate`, `--referendum-results`, `--referendum-registry`, `--referendum-2020` e l'output `--output public-site/data/electoral.json`. Verificare l'impronta dell'output prima di rigenerarlo con versioni diverse delle sorgenti. I dati finali degli archivi ministeriali non bastano a ricostruire l'istante della **prima** completezza; occorrono snapshot intermedi o log di trasmissione e validazione.

Fonti istituzionali per orari e ordine: [referendum 2020](https://dait.interno.gov.it/elezioni/faq/faq-referendum-2020), [referendum 2022](https://www.interno.gov.it/it/notizie/elezioni-amministrative-e-referendum-indicazioni-operative-voto-e-scrutini), [politiche 2022](https://dait.interno.gov.it/elezioni/faq/faq-elezioni-politiche-2022), [europee 2024](https://www.interno.gov.it/it/notizie/elezioni-2024-affluenza-europee-4969).
