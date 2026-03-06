-- UQA demo script for usql
-- Run: python usql.py examples/demo.sql

CREATE TABLE papers (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    year INTEGER NOT NULL,
    venue TEXT,
    field TEXT,
    citations INTEGER DEFAULT 0
);

INSERT INTO papers (title, year, venue, field, citations) VALUES
    ('attention is all you need', 2017, 'NeurIPS', 'nlp', 90000),
    ('bert pre-training', 2019, 'NAACL', 'nlp', 75000),
    ('graph attention networks', 2018, 'ICLR', 'graph', 15000),
    ('vision transformer', 2021, 'ICLR', 'cv', 25000),
    ('scaling language models', 2020, 'arXiv', 'nlp', 8000);

ANALYZE papers;

-- Basic queries
SELECT title, year FROM papers ORDER BY year DESC;
SELECT field, COUNT(*) AS cnt FROM papers GROUP BY field ORDER BY cnt DESC;

-- Full-text search
SELECT title, _score FROM papers
WHERE text_match(title, 'attention') ORDER BY _score DESC;

-- Filter + text search
EXPLAIN SELECT title FROM papers
WHERE text_match(title, 'attention') AND year >= 2020;
