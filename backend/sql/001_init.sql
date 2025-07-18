CREATE TABLE IF NOT EXISTS time_entry (
    id SERIAL PRIMARY KEY,
    uloha TEXT NOT NULL,
    autor TEXT NOT NULL,
    datum DATE NOT NULL,
    hodiny INTEGER NOT NULL CHECK (hodiny >= 0),
    minuty INTEGER NOT NULL CHECK (minuty BETWEEN 0 AND 59),
    jira TEXT,
    popis TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    submitted_to_metaapp_at TIMESTAMPTZ NULL,
    jira_name TEXT,
    uloha_name TEXT,
    metaapp_vykaz_id INTEGER
);
