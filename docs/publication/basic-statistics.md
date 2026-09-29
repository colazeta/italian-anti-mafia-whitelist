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

## Grafici e filtri

| Grafico | Numeratore | Denominatore / scala | Filtro |
| --- | --- | --- | --- |
| In istruttoria · data di invio | Righe `pending` con `application_date` interpretabile nel mese/anno | Conteggi, scala verticale comune alle due distribuzioni; riconciliazione con tutte le righe `pending` selezionate | Prefettura, anni inclusivi, mese/anno |
| Aggiornamento in corso · data di scadenza | Righe `renewal_update_in_progress` con `observed_expiry_date` interpretabile nel mese/anno | Conteggi, scala verticale comune alle due distribuzioni; riconciliazione con tutte le righe di questo stato selezionate | Gli stessi filtri della distribuzione delle istruttorie |
| Presenze per stato riportato | Righe selezionate con quello `source_status` | Tutte le righe selezionate, inclusi gli altri stati; percentuale arrotondata a due decimali | Prefettura |
| Presenze per Prefettura e stato | Righe selezionate dell'autorità con stato `listed` oppure `pending`, separatamente | Scala comune al massimo conteggio delle due serie; nessuna percentuale | Tutte le Prefetture pubblicate |

La Prefettura è l'autorità che pubblica, non la sede dell'impresa. Rinnovi,
scadenze e altri esiti restano distinti nel primo grafico; non vengono ricondotti
arbitrariamente a iscrizioni o istruttorie. Le percentuali arrotondate possono
non sommare esattamente a 100. Le date delle fonti possono differire: la tabella
Edizioni utilizzate mostra ciascun documento, data e collegamento ufficiale.

Ogni barra dei grafici per stato e per Prefettura è un pulsante accessibile anche da tastiera. Apre il registro con
Prefettura, stato e ultime edizioni coerenti con il conteggio, azzerando ricerca
e filtro di registro precedenti. Il filtro delle ultime edizioni è esplicito e
reversibile; la consultazione normale del registro mantiene il comportamento
precedente.

## Distribuzioni delle date riportate

Questi istogrammi descrivono le date delle presenze con i due stati nelle ultime
edizioni pubblicate. Non ricostruiscono lo stock storico delle pratiche pendenti,
il flusso complessivo delle istanze presentate, né i tempi di lavorazione.
`renewal_requested` resta separato da `renewal_update_in_progress`. La scadenza
osservata non determina una revoca, un rigetto o la perdita di efficacia legale.

`calendarDate` condivide la lettura delle date con `displayDate`: accetta solo
date complete ISO `YYYY-MM-DD` e italiane `D/M/YYYY`, validate sul calendario
gregoriano, senza conversione di fuso. Date parziali, formati ambigui e date
impossibili restano non interpretabili; null, stringa vuota e campo assente sono
mancanti. Non si usano date di riferimento, acquisizione o altri campi come
sostituti. Le righe e i valori originali non vengono modificati.

La selezione delle ultime edizioni e della Prefettura è la stessa degli altri
conteggi. Ogni presenza appartiene esattamente a una delle seguenti categorie:

`totale = nel periodo + prima del periodo + dopo il periodo + data mancante + data non interpretabile`.

Il periodo iniziale comprende dieci anni fino all'anno della massima data delle
edizioni pubblicate, più l'anno seguente per includere scadenze future. È stabile
rispetto all'orologio del visitatore e non cambia al cambio di Prefettura. Anni
iniziale/finale e raggruppamento per anno o mese sono modificabili. Le barre
includono intervalli a zero, partono da zero e condividono assi e scala verticale.
Il limite di rendering è 1.200 intervalli: una richiesta più ampia mostra un
errore e rimuove i grafici precedenti, senza troncamenti o cambi di granularità
impliciti. Tutti i valori esatti e gli anni fuori periodo sono consultabili in
una tabella espandibile da tastiera; i grafici mensili possono scorrere
orizzontalmente senza allargare la pagina mobile.

Una data valida sul calendario non è necessariamente una data corretta della
fonte. Gli anni estremi rimangono nei conteggi fuori periodo e possono essere
ispezionati modificando il periodo. Per le istruttorie viene inoltre indicato
quante date di invio sono successive alla data del relativo elenco: è un
segnale di verifica, sovrapposto alle categorie precedenti, non una correzione
né una categoria sottratta dal totale. Le scadenze future restano ammesse.

### Riscontro sullo snapshot pubblico del 29 settembre 2026

Selettore invariato: `public-data-36342687206-1`. Periodo iniziale 2017–2027.

| Stato / data | Totale | Nel periodo | Prima | Dopo | Mancante | Non interpretabile |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| In istruttoria / invio | 19.841 | 17.279 | 304 | 11 | 2.247 | 0 |
| Aggiornamento in corso / scadenza | 16.134 | 14.779 | 62 | 2 | 1.291 | 0 |

Le date interpretabili sono rispettivamente 17.594 e 14.843. Sono presenti
valori estremi negli anni 1202, 2204 e 5201 per l'invio e 2525 per la scadenza;
23 date di invio sono successive alla data dell'elenco. Questi dati pubblicati
richiedono verifica sulle fonti: la nuova presentazione li rende espliciti senza
correggerli o ripubblicare il dataset. Non sono prove di tempi amministrativi.

I test unitari verificano le partizioni, le date bisestili, l'assenza di
sostituzioni, le edizioni superate, il filtro, gli stati separati, gli estremi,
i mesi vuoti e i limiti. Il gate Pages esegue questi test prima del build e
verifica nel browser lo snapshot approvato a 1440, 768, 390 e 320 pixel:
parità con i conteggi, cambio Prefettura/periodo/granularità, dati mancanti,
errore senza grafico obsoleto, tabelle da tastiera e assenza di overflow esterno.

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
