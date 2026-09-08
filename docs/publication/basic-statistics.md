# Statistiche pubbliche di base

## Ambito e unità di conteggio

La pagina Statistiche usa esclusivamente `public-site/data/registry.json`, già
soggetto al contratto pubblico e alla selezione esplicita delle fonti pubblicabili.
Non aggiunge campi al contratto, dati interni o collegamenti al Dataset Explorer.
Una presenza è una riga pubblicata: non una nuova domanda nel periodo e non
un'impresa unica. La stessa impresa può contribuire a più presenze. Il registro,
le identità e le osservazioni storiche non vengono modificati.

Per ogni combinazione di autorità, registro e serie di fonte (`source_key`),
si seleziona la massima `reference_date` presente nelle osservazioni pubblicate.
Le date devono essere ISO complete e valide. Due contenuti diversi alla stessa
ultima data per la stessa serie bloccano le statistiche anziché introdurre una
scelta implicita. L'ordine delle righe non influenza la selezione. Edizioni
precedenti restano disponibili nel registro disattivando il filtro delle ultime
edizioni. Non si seleziona l'ultima osservazione per impresa, che potrebbe
riportare imprese scomparse da edizioni successive.

Il contratto attuale richiede osservazioni per ogni fonte pubblicata: non
descrive un'eventuale edizione vuota. L'espressione «ultima edizione disponibile»
si riferisce quindi all'archivio pubblicato, non a una verifica in tempo reale
di tutte le fonti ufficiali. Prima di pubblicare serie con edizioni vuote occorre
rappresentarle esplicitamente e adeguare questa selezione con test dedicati.

## I due grafici

| Grafico | Numeratore | Denominatore / scala | Filtro |
| --- | --- | --- | --- |
| Presenze per stato riportato | Righe selezionate con quello `source_status` | Tutte le righe selezionate, inclusi gli altri stati; percentuale arrotondata a due decimali | Prefettura, applicato solo a questo grafico |
| Presenze per Prefettura e stato | Righe selezionate dell'autorità con stato `listed` oppure `pending`, separatamente | Scala comune al massimo conteggio delle due serie; nessuna percentuale | Tutte le Prefetture pubblicate |

La Prefettura è l'autorità che pubblica, non la sede dell'impresa. Rinnovi,
scadenze e altri esiti restano distinti nel primo grafico; non vengono ricondotti
arbitrariamente a iscrizioni o istruttorie. Le percentuali arrotondate possono
non sommare esattamente a 100. Le date delle fonti possono differire: la tabella
Edizioni utilizzate mostra ciascun documento, data e collegamento ufficiale.

Ogni barra è un pulsante accessibile anche da tastiera. Apre il registro con
Prefettura, stato e ultime edizioni coerenti con il conteggio, azzerando ricerca
e filtro di registro precedenti. Il filtro delle ultime edizioni è esplicito e
reversibile; la consultazione normale del registro mantiene il comportamento
precedente.

## Verifica della versione iniziale

Il dataset approvato contiene 5.052 presenze nelle ultime edizioni di 8 fonti,
relative a 5 registri di 4 Prefetture. Non contiene ancora più edizioni per serie.

| Prefettura | Iscritte | In istruttoria |
| --- | ---: | ---: |
| Bologna | 1.178 | 479 |
| Cosenza | 461 | 657 |
| Parma | 375 | 235 |
| Pistoia | 215 | 45 |

Gli altri stati contano: rinnovo/aggiornamento in corso 1.203, rinnovo richiesto
14, scadenza osservata 171, esiti negativi 12, cancellazione 2, altro/non
specificato 5. Questi conteggi sono osservazioni delle fonti alle date indicate.

Test automatici: selezione temporale e indipendenza dall'ordine, serie separate,
ambiguità di contenuto, date invalide, conservazione dei dati, denominatori con
filtro, altri stati e selezione vuota. L'accettazione browser del build Pages
verifica i due grafici e il passaggio al registro, tastiera, date/fonti e assenza
di overflow esterno a 1440 e 390 pixel. Rimangono attivi tutti i test del registro,
le verifiche dei link ufficiali e il controllo del confine di pubblicazione.
