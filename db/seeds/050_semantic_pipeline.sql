INSERT INTO registry.activity_type(code,label) VALUES
('semantic_project','Semantic projection'),
('canonicalise','Canonicalisation')
ON CONFLICT DO NOTHING;
