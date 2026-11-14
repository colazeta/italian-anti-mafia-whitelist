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


// Publication gap counts only document candidates demonstrably later than
// the exact selected public source edition; it never interprets the count as approvals.
const {robotPublicationGap,robotLastPublishedDate}=require('../public-site/robots.js');
const source=(source_key,population_scope,reference_date,sha256='published-'+source_key,register_key='ordinary')=>
  ({source_key,population_scope,reference_date,sha256,register_key});
const published=[
  source('catania-listed','listed','2026-11-06'),
  source('catania-applicants','applicant','2026-11-06')
];
const listedUrl='https://prefettura.interno.gov.it/sites/default/files/18/2026-11/white-list-iscritti-aggiornato-13-novembre-2026.xlsx';
const applicantsUrl='https://prefettura.interno.gov.it/sites/default/files/18/2026-11/white-list-richiedenti-aggiornato-13-novembre-2026.xlsx';
const publishedUrl='https://prefettura.interno.gov.it/sites/default/files/18/2026-11/white-list-iscritti-aggiornato-06-novembre-2026.xlsx';
const undatedUrl='https://prefettura.interno.gov.it/sites/default/files/18/2026-11/elenco-imprese-iscritte.pdf';
const repeated='https://prefettura.interno.gov.it/sites/default/files/0/2026-11/white-list-iscritti-13-novembre-2026.xlsx';
const newerReport={
  status:'unchanged',pending_urls:[],errors:[],
  document_observations:{[listedUrl]:{first_seen_at:'2026-11-14T08:00:00Z'},
    [applicantsUrl]:{first_seen_at:'2026-11-14T08:00:00Z'}},
  resources:{
    [listedUrl]:{role:'candidate',sha256:'new-listed',archived_sha256:'new-listed',source_keys:[],
      capture_history:[{sha256:'new-listed'},{sha256:'new-listed'}]},
    [applicantsUrl]:{role:'candidate',sha256:'new-applicants',archived_sha256:'new-applicants',source_keys:[]},
    [publishedUrl]:{role:'source',sha256:'published-catania-listed',source_keys:['catania-listed']},
    [undatedUrl]:{role:'candidate',sha256:'undated-revised'},
    [repeated]:{role:'candidate',sha256:'duplicate-discovery'}
  }
};
const gap=robotPublicationGap(newerReport,published);
assert.equal(gap.status,'ok');
assert.equal(gap.count,2); // Listed and applicants count as distinct documents.
assert.deepEqual(new Set(gap.later.map(r=>r.population)),new Set(['listed','applicant']));
assert.equal(gap.unclassified.length,2); // Undated file and discovered-only duplicate are not counted.
assert.equal(gap.incomplete,false);
const unrelated='https://prefettura.interno.gov.it/sites/default/files/18/2026-11/elenco-parcheggi-14-novembre-2026.pdf';
const withUnrelated={...newerReport,resources:{...newerReport.resources,
  [unrelated]:{role:'candidate',sha256:'parking-file',archived_sha256:'parking-file'}}};
assert.equal(robotPublicationGap(withUnrelated,published).count,2);
assert.equal(robotLastPublishedDate(published),'2026-11-06');
assert.equal(robotLastPublishedDate([]),'');
assert.equal(robotPublicationGap(null,published).status,'no_report');
assert.equal(robotPublicationGap(newerReport,[]).status,'no_release');
assert.equal(robotPublicationGap(newerReport,published).later.some(d=>d.url===publishedUrl),false);

// A unique source identity and reference date represent one candidate edition,
// even if the robot discovered several links with different byte identities.
const duplicates={...newerReport,resources:{...newerReport.resources,
  [repeated]:{...newerReport.resources[repeated],source_keys:['catania-listed']},
  [listedUrl]:{...newerReport.resources[listedUrl],source_keys:['catania-listed']}}};
assert.equal(robotPublicationGap(duplicates,published).count,2);

// Compare each population against its own published date, not the prefecture's maximum.
const uneven=[source('listed','listed','2026-11-13'),source('app','applicant','2026-11-06')];
const applicantBetween='https://prefettura.interno.gov.it/sites/default/files/18/2026-11/elenco-richiedenti-10-novembre-2026.pdf';
const applicantReport={status:'unchanged',resources:{[applicantBetween]:{role:'candidate',sha256:'candidate-new',archived_sha256:'candidate-new'}}};
assert.equal(robotPublicationGap(applicantReport,uneven).count,1);

// Ambiguous population/register mapping cannot make an older file appear newer.
const ambiguous='https://prefettura.interno.gov.it/sites/default/files/18/2026-11/elenco-white-list-10-novembre-2026.pdf';
const ambiguousReport={status:'unchanged',resources:{[ambiguous]:{role:'candidate',sha256:'ambiguous-new'}}};
assert.equal(robotPublicationGap(ambiguousReport,uneven).count,0);
assert.equal(robotPublicationGap(ambiguousReport,uneven).unclassified.length,1);

// Repeated captures of one immutable document must not inflate the count.
const repeatReport={status:'unchanged',resources:{[listedUrl]:{role:'candidate',sha256:'new-listed',archived_sha256:'new-listed',
  capture_history:[{sha256:'new-listed'},{sha256:'new-listed'},{sha256:'new-listed'}]}}};
assert.equal(robotPublicationGap(repeatReport,published).count,1);

// Same-day changed files need review; they cannot be counted as later editions.
const sameDay='https://prefettura.interno.gov.it/sites/default/files/18/2026-11/elenco-iscritti-06-novembre-2026.pdf';
assert.equal(robotPublicationGap({status:'unchanged',resources:{[sameDay]:{role:'source',sha256:'changed-same-day'}}},published).count,0);
assert.equal(robotPublicationGap({status:'unchanged',resources:{[sameDay]:{role:'source',sha256:'changed-same-day'}}},published).unclassified.length,1);

// Separate post-earthquake and ordinary registers remain distinct if source-bound.
const bologna=[
  source('prov-listed','listed','2026-08-14','published-prov','ordinary'),
  source('sisma-listed','listed','2026-08-14','published-sisma','post-sisma')
];
const provincial='https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-iscritti-provinciale-10-settembre-2026.pdf';
const sisma='https://prefettura.interno.gov.it/sites/default/files/0/2026-09/elenco-iscritti-post-sisma-10-settembre-2026.pdf';
const bolognaReport={status:'unchanged',resources:{
  [provincial]:{role:'source',sha256:'updated-prov',archived_sha256:'updated-prov',source_keys:['prov-listed']},
  [sisma]:{role:'source',sha256:'updated-sisma',archived_sha256:'updated-sisma',source_keys:['sisma-listed']}
}};
assert.equal(robotPublicationGap(bolognaReport,bologna).count,2);
assert.equal(robotPublicationGap({status:'unchanged',resources:{[listedUrl]:{role:'candidate',sha256:'discovered-only'}}},published).count,0);
assert.equal(robotPublicationGap({status:'unchanged',resources:{[listedUrl]:{role:'candidate',sha256:'discovered-only'}}},published).unclassified.length,1);
assert.equal(robotPublicationGap({...newerReport,status:'partial',pending_urls:[listedUrl]},published).incomplete,true);

// Priority rankings are derived from live source observations, never a fixed top-10 list.
const {robotPriorityRows,robotPriorityCompare,robotPrioritySummary}=require('../public-site/robots.js');
const queue=[
  {authority_key:'catania',name:'Catania',region:'Sicilia',selected_public_sources:published},
  {authority_key:'firenze',name:'Firenze',region:'Toscana',selected_public_sources:[source('firenze-listed','listed','2026-08-31')]},
  {authority_key:'aosta',name:'Aosta',region:'Valle d’Aosta',selected_public_sources:[]},
  {authority_key:'missing',name:'Missing',region:'Unknown',selected_public_sources:[]}
];
const releasedMap=new Map([
  ['catania',{last_source_update:'2026-11-06'}],
  ['firenze',{last_source_update:'2026-08-31'}],
  ['aosta',{last_source_update:null}],
]);
const ranked=robotPriorityRows(queue,{catania:newerReport},releasedMap);
const totals=robotPrioritySummary(ranked);
assert.equal(totals.total,2);
assert.equal(totals.positive,1);
assert.equal(totals.withoutRelease,1);
assert.equal(totals.unavailable,2);
assert.equal(totals.uncertain,2);
assert.equal(ranked.find(x=>x.robot.authority_key==='catania').lastCandidate.date,'2026-11-13');
assert.equal(ranked.find(x=>x.robot.authority_key==='aosta').gap.status,'no_release');
assert.equal(ranked.find(x=>x.robot.authority_key==='missing').gap.status,'unavailable');
assert.deepEqual([...ranked].sort((a,b)=>robotPriorityCompare(a,b)).map(x=>x.robot.authority_key),
  ['catania','aosta','firenze','missing'].sort((a,b)=>{
    // Non-comparable authorities are equally ranked after all quantified rows.
    const ar=a==='catania'?2:-1,br=b==='catania'?2:-1;
    return br-ar||({aosta:1,firenze:2,missing:3}[a]-{aosta:1,firenze:2,missing:3}[b]);
  }));
assert.equal([...ranked].sort((a,b)=>robotPriorityCompare(a,b,'name'))[0].robot.name,'Aosta');
assert.equal(robotPrioritySummary([]).total,0);

console.log('Document history, publication baseline and candidate counts passed');
