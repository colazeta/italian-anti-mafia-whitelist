const assert=require('node:assert/strict');
const {robotDateInText,robotDocumentDate,robotDocumentHistory,robotLatestDocument,robotLatestFile}=require('../public-site/robots.js');
assert.equal(robotDocumentDate('https://example.org/white_list_06_11_2026.pdf'),'2026-11-06');
assert.equal(robotDocumentDate('https://example.org/white_list_2026-11-13.xlsx'),'2026-11-13');
assert.equal(robotDocumentDate('https://example.org/elenco-iscritte-4-settembre-2026.pdf'),'2026-09-04');
assert.equal(robotDocumentDate('https://example.org/white-list-iscritti-aggiornato-13-novembre-2026.xlsx'),'2026-11-13');
assert.equal(robotDocumentDate('https://example.org/elenco_29_FEBBRAIO_2024.pdf'),'2024-02-29');
assert.equal(robotDocumentDate('https://example.org/elenco_31-aprile-2026.pdf'),'');
assert.equal(robotDocumentDate('https://example.org/white_list_2026-02-30.pdf'),'');
assert.equal(robotDocumentDate('https://example.org/2026-11/elenco-imprese-iscritte.pdf'),'');
assert.equal(robotDocumentDate('https://example.org/white-list-06-11-2026-13-novembre-2026.pdf'),'');
assert.equal(robotDateInText('Elenco aggiornato al 4 settembre 2026'),'2026-09-04');
assert.equal(robotDateInText('Elenco senza data'),'');
assert.equal(robotDocumentDate(null),'');
const dated='https://prefettura.interno.gov.it/sites/default/files/white_list_06_11_2026.pdf';
const undated='https://prefettura.interno.gov.it/sites/default/files/elenco-imprese-iscritte.pdf';
const other='https://prefettura.interno.gov.it/sites/default/files/elenco-imprese-richiedenti.pdf';
const irrelevant='https://prefettura.interno.gov.it/sites/default/files/elenco-mezzi-sequestrati.pdf';
const report={
  document_observations:{
    [dated]:{first_seen_at:'2026-11-13T12:00:00Z'},
    [undated]:{first_seen_at:'2026-11-14T13:00:00Z'},
    [other]:{first_seen_at:'2026-11-14T11:00:00Z'},
    [irrelevant]:{first_seen_at:'2026-11-14T15:00:00Z'}
  },
  discovered_documents:[dated,undated,other,irrelevant],
  resources:{
    [dated]:{role:'candidate',capture_history:[{sha256:'a'},{sha256:'a'},{sha256:'b'}]},
    [undated]:{role:'candidate',capture_history:[{sha256:'c'}]},
    [other]:{role:'candidate'}
  }
};
assert.equal(robotDocumentHistory(report).length,3);
assert.equal(robotDocumentHistory(report).find(d=>d.url===dated).versions,2);
assert.equal(robotLatestDocument(report),'2026-11-06');
assert.equal(robotLatestFile(report).url,dated);
const noDated={...report,resources:{[undated]:report.resources[undated],[other]:report.resources[other]},
  document_observations:{[undated]:report.document_observations[undated],[other]:report.document_observations[other]},
  discovered_documents:[undated,other]};
assert.equal(robotLatestDocument(noDated),'');
assert.equal(robotLatestFile(noDated).url,undated);
assert.equal(robotLatestFile(noDated).date,'');
assert.equal(robotLatestFile(noDated).name,'elenco-imprese-iscritte.pdf');
assert.deepEqual(robotDocumentHistory(null),[]);
assert.equal(robotLatestFile(null),null);
console.log('Document history and filename-date checks passed');
