-- Internal blacklist used by the fraud rules. Entries are illustrative demo data.
INSERT INTO blacklist_entries (identifier_type, identifier, reason) VALUES
    ('PAN',   'AADCW5566K',      'Wilful defaulter list (demo entry)'),
    ('PAN',   'AAHFR7788M',      'Prior loan fraud investigation (demo entry)'),
    ('GSTIN', '07AAKCS1234M1ZX', 'GST registration cancelled for fake invoicing (demo entry)');
