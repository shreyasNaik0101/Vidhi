-- The 11 consolidation categories. The 8 marked (batch) received the 16 Jul 2026 SNFA change.
INSERT INTO entity_type (code, name) VALUES
    ('LAB',  'Local Area Banks'),                  -- batch
    ('RRB',  'Regional Rural Banks'),              -- batch
    ('RCB',  'Rural Co-operative Banks'),          -- batch
    ('UCB',  'Urban Co-operative Banks'),          -- batch
    ('AIFI', 'All India Financial Institutions'),  -- batch
    ('NBFC', 'Non-Banking Financial Companies'),   -- batch
    ('SFB',  'Small Finance Banks'),               -- batch
    ('SCB',  'Commercial Banks'),                  -- batch
    ('PB',   'Payments Banks'),
    ('HFC',  'Housing Finance Companies'),
    ('ARC',  'Asset Reconstruction Companies')
ON CONFLICT (code) DO NOTHING;
