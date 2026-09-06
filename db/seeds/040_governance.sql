INSERT INTO governance.dissemination_policy(policy_code, description) VALUES
('public','May be included in the public dataset as stored.'),
('public_transformed','May be published only after the specified transformation.'),
('requires_review','Requires legal/data-governance review before public bulk distribution.'),
('internal_only','Retained internally and excluded from public distribution.')
ON CONFLICT (policy_code) DO NOTHING;

INSERT INTO governance.dissemination_profile(profile_code, description) VALUES
('public_bulk_v1','Default public bulk-download profile; field-level decisions are attached explicitly.')
ON CONFLICT (profile_code) DO NOTHING;
