INSERT INTO registry.activity_type(code,label) VALUES
('semantic_project','Semantic projection'),
('canonicalise','Canonicalisation')
ON CONFLICT DO NOTHING;

INSERT INTO mapping.canonical_field(
    canonical_path, semantic_domain, definition, datatype, cardinality, standard_uri
) VALUES (
    'procedure.sector_concept',
    'procedure',
    'Canonical White List sector concept requested or concerned by an administrative procedure.',
    'uuid',
    '0..n',
    'http://www.w3.org/2004/02/skos/core#Concept'
)
ON CONFLICT (canonical_path) DO NOTHING;
