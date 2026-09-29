# Robot di acquisizione per Prefettura

## Copertura e confine operativo

`data/source_registry/prefecture_robots.json` contiene **106 profili**, uno per ciascuna autorità canonica. Ogni profilo è eseguibile individualmente e dichiara pagine di partenza, origini HTTPS ammesse, risorse già associate, parser esistenti e limiti di richieste/profondità/durata. Il motore è condiviso in `acquisition/prefecture_robots.py`: correggere trasporto, confronto o archiviazione migliora tutti i robot senza duplicare 106 implementazioni.

Le fonti e i parser approvati coprono attualmente 74 autorità. Per le altre 32 il robot acquisisce la pagina censita dall'indice e cerca allegati pertinenti, mantenendo esplicita la necessità di qualificare le popolazioni e validare l'estrazione. La presenza di un robot non promuove l'autorità a fonte completa o a registro pubblicato.

## Uso

La scheda **Robot** del portale permette di cercare una Prefettura, vedere l'ultimo tentativo e aprire il workflow [Prefecture robots](https://github.com/colazeta/italian-anti-mafia-whitelist/actions/workflows/prefecture-robots.yml). In **Run workflow**:

* `authority`: chiave indicata nella scheda (per esempio `cosenza`) oppure `all`;
* `mode=capture`: controlla pagine, collegamenti e risorse, conservando gli originali acquisiti nell'archivio privato delle evidenze;
* `mode=check`: alias di compatibilità di `capture`, con lo stesso obbligo di conservazione;
* `force=true`: richiede il recupero completo anche quando il server dispone di ETag/Last-Modified; per fonti e documenti candidati questo è già necessario a ogni acquisizione.

Esecuzione locale dal repository:

```bash
PYTHONPATH=src python -m white_list_archive.acquisition.prefecture_robots \
  --authority cosenza --mode capture --state previous.json --output report.json
```

Ogni acquisizione richiede il consueto `StoreConfig` e le credenziali del deposito, verificati prima di scaricare fonti. Dal 29 settembre 2026 `check` non consente più di scaricare e scartare byte: resta accettato per compatibilità dei comandi, ma il report indica `mode=capture` e conserva separatamente `requested_mode=check`. Il default locale è `capture`. I report storici non vengono riscritti; un vecchio controllo privo di ricevuta rimane privo di prova di conservazione. La sola generazione del catalogo non acquisisce fonti e non richiede credenziali.

## Aggiornamenti e versioni

1. Si acquisiscono le pagine di partenza, incluse le pagine stabili di navigazione, e si seguono soltanto collegamenti pertinenti entro i limiti dichiarati. Il dominio condiviso del Ministero non consente a un robot di visitare altre Prefetture attraverso il menu nazionale.
2. Le risorse conosciute vengono confrontate con la rilevazione precedente. Una prima rilevazione può usare l'impronta della fonte già approvata. Fonti e documenti candidati richiedono direttamente i byte completi, evitando la doppia richiesta condizionale più download. Se il server restituisce comunque 304, si ritenta una volta il recupero completo: il solo 304 non crea una nuova cattura verificata.
3. Le impronte SHA-256 distinguono i contenuti anche quando l'URL resta uguale. Collegamenti nuovi, errori, redirect fuori origine e limiti di scansione restano espliciti. Una risposta HTML/XHTML a un URL documentale viene conservata prima di essere respinta: è evidenza del tentativo, non un PDF valido né una nuova edizione amministrativa. Non viene esplorata come pagina di navigazione.
4. In `capture`, il meccanismo `archive_payload` salva l'oggetto immutabile e il manifesto di acquisizione, rileggendoli e verificandoli prima di dichiarare il successo. Per una risorsa `source` o `candidate`, ogni acquisizione riuscita produce un distinto capture/check anche quando i byte sono identici: il `ContentObject` viene riutilizzato per SHA-256, mentre identità e orario del nuovo controllo restano separati. Un ritorno HTTP 304 viene quindi seguito da un recupero completo dei byte quando serve materializzare il nuovo capture/check. Le sole pagine di navigazione restano invece archiviate al primo contenuto o al cambio di byte, per non trasformare il polling del menu in falsa evidenza di una nuova versione documentale.
5. `capture_history` conserva nello stato corrente la sequenza append-only delle identità di acquisizione per ciascuna risorsa, inclusi `capture_id`, `source_key`, SHA-256, dimensione, MIME, `captured_at`, `reference_date` e stato HTTP quando realmente disponibili. Gli stati precedenti che conservavano soltanto `capture_ids` vengono migrati in compatibilità senza inventare timestamp o metadati mancanti: i campi non storicamente registrati restano `null`.
6. Risorse già associate conservano il proprio `source_key`; le risorse scoperte senza associazione vengono conservate sotto `<authority>-robot-discovery`. È uno spazio di quarantena per la scoperta, non una nuova SourceSeries qualificata: il nome del file non determina popolazione, regime, parser o data dell'edizione. `reference_date` resta sconosciuta.
7. Acquisizione, estrazione e pubblicazione restano passaggi distinti. Per accettare una nuova versione si verificano fonte, associazione, parser e risultati secondo i controlli già esistenti; nessun robot modifica automaticamente gli hash approvati o il registro delle imprese.

Gli stati `baseline`, `unchanged` e `changed` descrivono i byte e i collegamenti dell'ambito controllato. `partial` conserva gli errori e l'ultimo stato valido: non azzera impronte o acquisizioni precedenti. La variazione HTML può dipendere da elementi di pagina; non viene chiamata automaticamente “nuova edizione”.

`capture_history` comprende anche le catture conservate prima di un rifiuto o del fallimento di una successiva associazione. I campi correnti `sha256`, `capture_ids` e `last_checked_at` mantengono invece l'ultimo stato che ha superato i controlli; se non esiste ancora, possono essere assenti. `captured_urls` indica gli URL con almeno una nuova cattura verificata nel tentativo, anche in quarantena. Ogni errore identifica `stage` (`state_validation`, `acquisition`, `archive`, `response_validation`, `discovery`) e gli eventuali `verified_capture_ids` di quel tentativo: nessun messaggio del provider o coordinata privata entra nel report. Un errore di archivio senza ricevuta non prova che i byte siano mancanti dal deposito.

Le scansioni che superano il limite riprendono al controllo successivo dalla coda persistita, conservando profondità e ruolo dei collegamenti. `cycle_started_at` indica l'inizio del ciclo; i documenti già verificati in quel ciclo non consumano di nuovo il limite. Pagine di partenza e fonti approvate vengono comunque ricontrollate a ogni tentativo, così possono emergere nuovi allegati durante la prosecuzione. I documenti nuovi e quelli controllati meno recentemente hanno precedenza; a parità l'ordine URL decrescente favorisce gli allegati con percorsi recenti senza attribuire una data amministrativa dal nome. Il ciclo completo può quindi richiedere più esecuzioni giornaliere, ma la coda non riparte sempre dai primi allegati. Quando termina, il tentativo seguente avvia un nuovo ciclo. Il limite di profondità vale anche per le pagine riprese dalla coda.

Le pagine regionali dentro una cartella `white_list/` mantengono la navigazione in quella cartella, escludendo i menu generali (per esempio allerte sanitarie o portali d'impresa); gli allegati dinamici `allegato.aspx` restano acquisibili. Per le esportazioni CSV Google Sheets già su un'origine configurata è ammesso lo specifico salto HTTPS dal percorso `/spreadsheets/d/e/<id>/pub?output=csv` a `/pub/` sui server `doc-*-sheets.googleusercontent.com`. Il 27 settembre 2026 entrambe le esportazioni approvate di Lodi hanno restituito un 307 verso `doc-10-c0-sheets.googleusercontent.com`. Questa regola del fornitore non amplia i domini ammessi per la scoperta e non accetta altri percorsi, protocolli o host Google.

## Esecuzione nazionale e persistenza

Il workflow esegue il giro nazionale ogni giorno alle **04:17 UTC**, con verifica completa dei byte la domenica. Dodici gruppi e al massimo tre esecuzioni contemporanee limitano il carico sui siti. Ogni autorità conserva un esito indipendente; il fallimento di una non interrompe le altre. L'esecuzione manuale di una sola autorità usa un solo gruppo. Cambiamenti al motore o alla configurazione avviano una verifica dopo il merge su `main`.

Il ramo `robot-state` conserva soltanto metadati tecnici: orari, URL pubblici, impronte, metadati HTTP, identità e cronologia dei capture/check, errori e collegamenti al run. La cronologia Git dello stato è un indice operativo utile, ma non è il deposito degli originali e non sostituisce la prova di conservazione: l'autorità per i byte è il `ContentObject` nel backend privato governato, mentre l'autorità per la provenienza temporale è il relativo record immutabile nel `CaptureCatalogue`, entrambi riletti e verificati prima del successo. Gli artifact temporanei sono solo un passaggio di consegna tra i job. Nessun originale, credenziale, coordinata del deposito o riga d'impresa viene pubblicato in questo ramo. Le esecuzioni sono serializzate per impedire aggiornamenti concorrenti dello stato. Un report mancante non elimina lo stato della Prefettura.

La scheda pubblica carica i rapporti dal ramo `robot-state`, indicando separatamente un rapporto assente o non raggiungibile. Questo permette di visualizzare l'esito dei robot senza ricostruire o ripubblicare il registro delle imprese.

## Manutenzione

Quando cambiano pagine verificate, inventario, fonti approvate o autorità, rigenerare il catalogo e la directory pubblica:

```bash
PYTHONPATH=src python -m white_list_archive.acquisition.prefecture_robots --generate-catalog
PYTHONPATH=src python -m white_list_archive.publishing.public_robots
```

La CI verifica corrispondenza con le fonti di configurazione, copertura esatta delle autorità, isolamento delle origini, errori parziali, 304, confronto a URL invariato e conservazione degli originali. I test browser controllano anche la directory dei robot e la consultazione da mobile.
