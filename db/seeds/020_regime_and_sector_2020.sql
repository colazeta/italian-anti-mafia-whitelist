INSERT INTO whitelist.white_list_regime(
    regime_code, preferred_label, description, legal_basis_uri, effective_period
) VALUES (
    'WL-REGIME-L190-2012',
    'White List antimafia - legge 190/2012',
    'Ordinary Prefectural White List regime under article 1, paragraphs 52-57, Law 190/2012 and subsequent amendments.',
    'https://www.normattiva.it/',
    daterange('2013-08-14'::date, NULL, '[)')
) ON CONFLICT (regime_code) DO NOTHING;

WITH regime AS (
    SELECT regime_id FROM whitelist.white_list_regime WHERE regime_code='WL-REGIME-L190-2012'
)
INSERT INTO whitelist.sector_scheme_version(regime_id, version_code, legal_basis_uri, effective_period)
SELECT regime_id, 'L190-2020',
       'https://www.normattiva.it/atto/caricaDettaglioAtto?atto.codiceRedazionale=20G00060',
       daterange('2020-06-07'::date, NULL, '[)')
FROM regime
ON CONFLICT (regime_id, version_code) DO NOTHING;

INSERT INTO whitelist.sector_concept(concept_code) VALUES
('WL-ACT-INERT-MATERIALS'),
('WL-ACT-CONCRETE-BITUMEN'),
('WL-ACT-COLD-MACHINERY-RENTAL'),
('WL-ACT-WORKED-IRON'),
('WL-ACT-HOT-RENTAL'),
('WL-ACT-THIRD-PARTY-HAULAGE'),
('WL-ACT-CONSTRUCTION-SITE-GUARDING'),
('WL-ACT-FUNERAL-CEMETERY'),
('WL-ACT-CATERING'),
('WL-ACT-ENVIRONMENTAL-SERVICES')
ON CONFLICT (concept_code) DO NOTHING;

WITH labels(concept_code,label) AS (VALUES
('WL-ACT-INERT-MATERIALS','Estrazione, fornitura e trasporto di terra e materiali inerti'),
('WL-ACT-CONCRETE-BITUMEN','Confezionamento, fornitura e trasporto di calcestruzzo e di bitume'),
('WL-ACT-COLD-MACHINERY-RENTAL','Noli a freddo di macchinari'),
('WL-ACT-WORKED-IRON','Fornitura di ferro lavorato'),
('WL-ACT-HOT-RENTAL','Noli a caldo'),
('WL-ACT-THIRD-PARTY-HAULAGE','Autotrasporti per conto di terzi'),
('WL-ACT-CONSTRUCTION-SITE-GUARDING','Guardiania dei cantieri'),
('WL-ACT-FUNERAL-CEMETERY','Servizi funerari e cimiteriali'),
('WL-ACT-CATERING','Ristorazione, gestione delle mense e catering'),
('WL-ACT-ENVIRONMENTAL-SERVICES','Servizi ambientali')
)
INSERT INTO whitelist.sector_concept_label(sector_concept_id,label,label_type_code,language_code,effective_period)
SELECT c.sector_concept_id, labels.label, 'preferred', 'it', daterange('2020-06-07'::date,NULL,'[)')
FROM labels JOIN whitelist.sector_concept c ON c.concept_code=labels.concept_code
ON CONFLICT DO NOTHING;

WITH scheme AS (
    SELECT sv.scheme_version_id
    FROM whitelist.sector_scheme_version sv
    JOIN whitelist.white_list_regime r USING(regime_id)
    WHERE r.regime_code='WL-REGIME-L190-2012' AND sv.version_code='L190-2020'
), vals(notation,concept_code,legal_label) AS (VALUES
('I','WL-ACT-INERT-MATERIALS','Estrazione, fornitura e trasporto di terra e materiali inerti'),
('II','WL-ACT-CONCRETE-BITUMEN','Confezionamento, fornitura e trasporto di calcestruzzo e di bitume'),
('III','WL-ACT-COLD-MACHINERY-RENTAL','Noli a freddo di macchinari'),
('IV','WL-ACT-WORKED-IRON','Fornitura di ferro lavorato'),
('V','WL-ACT-HOT-RENTAL','Noli a caldo'),
('VI','WL-ACT-THIRD-PARTY-HAULAGE','Autotrasporti per conto di terzi'),
('VII','WL-ACT-CONSTRUCTION-SITE-GUARDING','Guardiania dei cantieri'),
('VIII','WL-ACT-FUNERAL-CEMETERY','Servizi funerari e cimiteriali'),
('IX','WL-ACT-CATERING','Ristorazione, gestione delle mense e catering'),
('X','WL-ACT-ENVIRONMENTAL-SERVICES','Servizi ambientali, comprese le attività di raccolta, di trasporto nazionale e transfrontaliero, anche per conto di terzi, di trattamento e di smaltimento dei rifiuti, nonché le attività di risanamento e di bonifica e gli altri servizi connessi alla gestione dei rifiuti')
)
INSERT INTO whitelist.sector_scheme_membership(
    scheme_version_id, sector_concept_id, notation, legal_label, effective_period
)
SELECT scheme.scheme_version_id, c.sector_concept_id, vals.notation, vals.legal_label,
       daterange('2020-06-07'::date, NULL, '[)')
FROM scheme CROSS JOIN vals
JOIN whitelist.sector_concept c ON c.concept_code=vals.concept_code
ON CONFLICT (scheme_version_id, notation) DO NOTHING;
