# Robot di acquisizione per Prefettura

## Copertura e confine operativo

`data/source_registry/prefecture_robots.json` contiene **106 profili**, uno per ciascuna autorità canonica. Ogni profilo è eseguibile individualmente e dichiara pagine di partenza, origini HTTPS ammesse, risorse già associate, parser esistenti e limiti di richieste/profondità/durata. Il motore è condiviso in `acquisition/prefecture_robots.py`: correggere trasporto, confronto o archiviazione migliora tutti i robot senza duplicare 106 implementazioni.

Le fonti e i parser approvati coprono attualmente 74 autorità. Per le altre 32 il robot acquisisce la pagina censita dall'indice e cerca allegati pertinenti, mantenendo esplicita la necessità di qualificare le popolazioni e validare l'estrazione. La presenza di un robot non promuove l'autorità a fonte completa o a registro pubblicato.

## Uso

La scheda **Robot** del portale permette di cercare una Prefettura, vedere l'ultimo tentativo e aprire il workflow [Prefecture robots](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/workflows/prefecture-robots.yml). In **Run workflow**:

* `authority`: chiave indicata nella scheda (per esempio `cosenza`) oppure `all`;
* `mode=check`: controlla pagine, collegamenti e contenuto delle risorse;
* `mode=capture`: esegue il controllo e conserva gli originali acquisiti nell'archivio privato delle evidenze;
* `force=true`: scarica nuovamente i byte anche quando il server dispone di ETag/Last-Modified.

Esecuzione locale dal repository:

```bash
PYTHONPATH=src python -m white_list_archive.acquisition.prefecture_robots \
  --authority cosenza --mode check --state previous.json --output report.json
PYTHONPATH=src python -m white_list_archive.acquisition.prefecture_robots \
  --authority cosenza --mode capture --state previous.json --output report.json
```

Il secondo comando richiede il consueto `StoreConfig` e le credenziali del deposito. L'assenza del deposito impedisce di dichiarare l'acquisizione conservata. Il controllo di sola lettura funziona senza credenziali del deposito.

## Aggiornamenti e versioni

1. Si acquisiscono le pagine di partenza, incluse le pagine stabili di navigazione, e si seguono soltanto collegamenti pertinenti entro i limiti dichiarati. Il dominio condiviso del Ministero non consente a un robot di visitare altre Prefetture attraverso il menu nazionale.
2. Le risorse conosciute vengono confrontate con la rilevazione precedente, usando richieste condizionali quando possibili. Una prima rilevazione può usare l'impronta della fonte già approvata. La prima acquisizione dopo un `check` forza il download se un 304 non fornisce i byte da archiviare.
3. Le impronte SHA-256 distinguono i contenuti anche quando l'URL resta uguale. Collegamenti nuovi, errori, redirect fuori origine e limiti di scansione restano espliciti. Una risposta HTML a un URL documentale è un errore, non un PDF acquisito.
4. In `capture`, il meccanismo `archive_payload` salva l'oggetto immutabile e il manifesto di acquisizione, rileggendoli e verificandoli prima di dichiarare il successo. Un originale già visto non viene sovrascritto.
5. Risorse già associate conservano il proprio `source_key`; le risorse scoperte senza associazione vengono conservate sotto `<authority>-robot-discovery`. È uno spazio di quarantena per la scoperta, non una nuova SourceSeries qualificata: il nome del file non determina popolazione, regime, parser o data dell'edizione. `reference_date` resta sconosciuta.
6. Acquisizione, estrazione e pubblicazione restano passaggi distinti. Per accettare una nuova versione si verificano fonte, associazione, parser e risultati secondo i controlli già esistenti; nessun robot modifica automaticamente gli hash approvati o il registro delle imprese.

Gli stati `baseline`, `unchanged` e `changed` descrivono i byte e i collegamenti dell'ambito controllato. `partial` conserva gli errori e l'ultimo stato valido: non azzera impronte o acquisizioni precedenti. La variazione HTML può dipendere da elementi di pagina; non viene chiamata automaticamente “nuova edizione”.

Le scansioni che superano il limite riprendono al controllo successivo dalla coda persistita, conservando profondità e ruolo dei collegamenti. `cycle_started_at` indica l'inizio del ciclo; i documenti già verificati in quel ciclo non consumano di nuovo il limite. Pagine di partenza e fonti approvate vengono comunque ricontrollate a ogni tentativo, così possono emergere nuovi allegati durante la prosecuzione. I documenti nuovi e quelli controllati meno recentemente hanno precedenza; a parità l'ordine URL decrescente favorisce gli allegati con percorsi recenti senza attribuire una data amministrativa dal nome. Il ciclo completo può quindi richiedere più esecuzioni giornaliere, ma la coda non riparte sempre dai primi allegati. Quando termina, il tentativo seguente avvia un nuovo ciclo. Il limite di profondità vale anche per le pagine riprese dalla coda.

## Esecuzione nazionale e persistenza

Il workflow esegue il giro nazionale ogni giorno alle **04:17 UTC**, con verifica completa dei byte la domenica. Dodici gruppi e al massimo tre esecuzioni contemporanee limitano il carico sui siti. Ogni autorità conserva un esito indipendente; il fallimento di una non interrompe le altre. L'esecuzione manuale di una sola autorità usa un solo gruppo. Cambiamenti al motore o alla configurazione avviano una verifica dopo il merge su `main`.

Il ramo `robot-state` conserva soltanto metadati tecnici: orari, URL pubblici, impronte, metadati HTTP, ricevute di acquisizione, errori e collegamenti al run. I commit mantengono la cronologia dei controlli; gli artifact temporanei sono solo un passaggio di consegna tra i job. Nessun originale, credenziale, coordinata del deposito o riga d'impresa viene pubblicato in questo ramo. Le esecuzioni sono serializzate per impedire aggiornamenti concorrenti dello stato. Un report mancante non elimina lo stato della Prefettura.

La scheda pubblica carica i rapporti dal ramo `robot-state`, indicando separatamente un rapporto assente o non raggiungibile. Questo permette di visualizzare l'esito dei robot senza ricostruire o ripubblicare il registro delle imprese.

## Manutenzione

Quando cambiano pagine verificate, inventario, fonti approvate o autorità, rigenerare il catalogo e la directory pubblica:

```bash
PYTHONPATH=src python -m white_list_archive.acquisition.prefecture_robots --generate-catalog
PYTHONPATH=src python -m white_list_archive.publishing.public_robots
```

La CI verifica corrispondenza con le fonti di configurazione, copertura esatta delle autorità, isolamento delle origini, errori parziali, 304, confronto a URL invariato e conservazione degli originali. I test browser controllano anche la directory dei robot e la consultazione da mobile.
