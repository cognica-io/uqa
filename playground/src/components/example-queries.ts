export interface ExampleQuery {
  label: string
  category: "basic" | "search" | "aggregate" | "graph" | "advanced"
  description: string
  query: string
}

export const EXAMPLE_QUERIES: ExampleQuery[] = [
  // Basic SQL
  {
    label: "Select all movies",
    category: "basic",
    description: "Retrieve all movies from the database",
    query: "SELECT title, director, year, genre, rating\nFROM movies\nORDER BY rating DESC",
  },
  {
    label: "Filter by year",
    category: "basic",
    description: "Find movies released after 2010",
    query: "SELECT title, director, year, rating\nFROM movies\nWHERE year >= 2010\nORDER BY year DESC",
  },
  {
    label: "Filter by genre",
    category: "basic",
    description: "Find all Sci-Fi movies sorted by rating",
    query: "SELECT title, director, year, rating\nFROM movies\nWHERE genre = 'Sci-Fi'\nORDER BY rating DESC",
  },
  {
    label: "Top 5 by rating",
    category: "basic",
    description: "Get the top 5 highest rated movies",
    query: "SELECT title, director, year, genre, rating\nFROM movies\nORDER BY rating DESC\nLIMIT 5",
  },

  // Full-Text Search
  {
    label: "Full-text: text_match",
    category: "search",
    description: "Search for movies about 'war' using BM25 scoring",
    query: "SELECT title, genre, _score\nFROM movies\nWHERE text_match(description, 'war')\nORDER BY _score DESC",
  },
  {
    label: "Full-text: @@ operator",
    category: "search",
    description: "Boolean text search with AND/OR operators",
    query: "SELECT title, genre, _score\nFROM movies\nWHERE description @@ 'crime AND family'\nORDER BY _score DESC",
  },
  {
    label: "Multi-field search",
    category: "search",
    description: "Search across title, description, and director fields",
    query: "SELECT title, director, _score\nFROM movies\nWHERE multi_field_match(title, description, director, 'Nolan')\nORDER BY _score DESC",
  },
  {
    label: "Search + filter",
    category: "search",
    description: "Full-text search combined with year and rating filters",
    query: "SELECT title, year, rating, _score\nFROM movies\nWHERE text_match(description, 'dream OR reality')\n  AND year >= 1990\n  AND rating > 8.0\nORDER BY _score DESC",
  },

  // Aggregation
  {
    label: "Count by genre",
    category: "aggregate",
    description: "Count the number of movies per genre",
    query: "SELECT genre, COUNT(*) AS count\nFROM movies\nGROUP BY genre\nORDER BY count DESC",
  },
  {
    label: "Avg rating by genre",
    category: "aggregate",
    description: "Average rating per genre with movie count",
    query: "SELECT genre,\n  COUNT(*) AS count,\n  ROUND(AVG(rating), 2) AS avg_rating\nFROM movies\nGROUP BY genre\nORDER BY avg_rating DESC",
  },
  {
    label: "Movies by decade",
    category: "aggregate",
    description: "Count movies by decade with average rating",
    query: "SELECT (year / 10) * 10 AS decade,\n  COUNT(*) AS count,\n  ROUND(AVG(rating), 2) AS avg_rating\nFROM movies\nGROUP BY decade\nORDER BY decade",
  },
  {
    label: "Director stats",
    category: "aggregate",
    description: "Directors with multiple movies and their average ratings",
    query: "SELECT director,\n  COUNT(*) AS movie_count,\n  ROUND(AVG(rating), 2) AS avg_rating\nFROM movies\nGROUP BY director\nHAVING COUNT(*) > 1\nORDER BY avg_rating DESC",
  },

  // Graph (Cypher)
  {
    label: "All graph nodes",
    category: "graph",
    description: "List all Movie nodes in the cinema graph",
    query: "SELECT * FROM cypher('cinema', $$\n  MATCH (m:Movie)\n  RETURN m.title AS title, m.year AS year, m.rating AS rating\n  ORDER BY m.rating DESC\n$$) AS (title agtype, year agtype, rating agtype)",
  },
  {
    label: "Director's filmography",
    category: "graph",
    description: "Find all movies directed by Christopher Nolan via graph traversal",
    query: "SELECT * FROM cypher('cinema', $$\n  MATCH (m:Movie)-[:DIRECTED_BY]->(d:Director {name: 'Christopher Nolan'})\n  RETURN m.title AS title, m.year AS year, m.rating AS rating\n  ORDER BY m.year\n$$) AS (title agtype, year agtype, rating agtype)",
  },
  {
    label: "Movies by genre",
    category: "graph",
    description: "Traverse the graph to find all Sci-Fi movies",
    query: "SELECT * FROM cypher('cinema', $$\n  MATCH (m:Movie)-[:HAS_GENRE]->(g:Genre {name: 'Sci-Fi'})\n  RETURN m.title AS title, m.year AS year, m.rating AS rating\n  ORDER BY m.rating DESC\n$$) AS (title agtype, year agtype, rating agtype)",
  },
  {
    label: "Shared genre peers",
    category: "graph",
    description: "Find movies that share the same genre as Inception",
    query: "SELECT * FROM cypher('cinema', $$\n  MATCH (m:Movie {title: 'Inception'})-[:HAS_GENRE]->(g:Genre)<-[:HAS_GENRE]-(peer:Movie)\n  RETURN peer.title AS title, g.name AS genre, peer.rating AS rating\n  ORDER BY peer.rating DESC\n$$) AS (title agtype, genre agtype, rating agtype)",
  },
  {
    label: "Director-genre pairs",
    category: "graph",
    description: "Find which directors work in which genres via 2-hop traversal",
    query: "SELECT * FROM cypher('cinema', $$\n  MATCH (d:Director)<-[:DIRECTED_BY]-(m:Movie)-[:HAS_GENRE]->(g:Genre)\n  RETURN d.name AS director, g.name AS genre, COUNT(m) AS movie_count\n  ORDER BY movie_count DESC\n$$) AS (director agtype, genre agtype, movie_count agtype)",
  },

  // Advanced
  {
    label: "Subquery: above avg",
    category: "advanced",
    description: "Find movies with above-average rating",
    query: "SELECT title, rating, genre\nFROM movies\nWHERE rating > (SELECT AVG(rating) FROM movies)\nORDER BY rating DESC",
  },
  {
    label: "CASE expression",
    category: "advanced",
    description: "Categorize movies by era using CASE",
    query: "SELECT title, year,\n  CASE\n    WHEN year < 1980 THEN 'Classic'\n    WHEN year < 2000 THEN 'Modern'\n    WHEN year < 2010 THEN '2000s'\n    ELSE 'Recent'\n  END AS era,\n  rating\nFROM movies\nORDER BY year",
  },
  {
    label: "Text search + aggregation",
    category: "advanced",
    description: "Search for action-oriented movies then aggregate by genre",
    query: "SELECT genre,\n  COUNT(*) AS count,\n  ROUND(AVG(_score), 4) AS avg_relevance\nFROM movies\nWHERE text_match(description, 'fight OR war OR battle OR injustice')\nGROUP BY genre\nORDER BY avg_relevance DESC",
  },
  {
    label: "Window: rank by genre",
    category: "advanced",
    description: "Rank movies within each genre by rating",
    query: "SELECT title, genre, rating,\n  RANK() OVER (PARTITION BY genre ORDER BY rating DESC) AS genre_rank\nFROM movies\nORDER BY genre, genre_rank",
  },
]

export const CATEGORY_LABELS: Record<ExampleQuery["category"], string> = {
  basic: "Basic SQL",
  search: "Full-Text Search",
  aggregate: "Aggregation",
  graph: "Graph (Cypher)",
  advanced: "Advanced",
}
