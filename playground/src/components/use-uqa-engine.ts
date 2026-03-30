import { useCallback, useRef, useState } from "react"

import type { Engine, SQLResult } from "@jaepil/uqa"

export interface QueryResult {
  result: SQLResult | null
  error: string | null
  elapsed: number
}

export const SAMPLE_DATA = [
  {
    title: "The Shawshank Redemption",
    director: "Frank Darabont",
    year: 1994,
    genre: "Drama",
    rating: 9.3,
    description:
      "A banker convicted of uxoricide forms a friendship over a quarter century with a hardened convict, while maintaining his innocence and trying to remain hopeful through simple compassion.",
  },
  {
    title: "The Godfather",
    director: "Francis Ford Coppola",
    year: 1972,
    genre: "Crime",
    rating: 9.2,
    description:
      "The aging patriarch of an organized crime dynasty transfers control of his clandestine empire to his reluctant youngest son, exploring themes of power, family loyalty, and moral corruption.",
  },
  {
    title: "The Dark Knight",
    director: "Christopher Nolan",
    year: 2008,
    genre: "Action",
    rating: 9.0,
    description:
      "When a menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest psychological and physical tests of his ability to fight injustice.",
  },
  {
    title: "Pulp Fiction",
    director: "Quentin Tarantino",
    year: 1994,
    genre: "Crime",
    rating: 8.9,
    description:
      "The lives of two mob hitmen, a boxer, a gangster and his wife, and a pair of diner bandits intertwine in four tales of violence and redemption set in Los Angeles.",
  },
  {
    title: "Inception",
    director: "Christopher Nolan",
    year: 2010,
    genre: "Sci-Fi",
    rating: 8.8,
    description:
      "A thief who steals corporate secrets through the use of dream-sharing technology is given the inverse task of planting an idea into the mind of a C.E.O., but his tragic past may doom the project and his team to disaster.",
  },
  {
    title: "Interstellar",
    director: "Christopher Nolan",
    year: 2014,
    genre: "Sci-Fi",
    rating: 8.7,
    description:
      "When Earth becomes uninhabitable in the future, a farmer and ex-NASA pilot is tasked with piloting a spacecraft along with a team of researchers to find a new planet for humans, traveling through a wormhole near Saturn.",
  },
  {
    title: "The Matrix",
    director: "Lana Wachowski",
    year: 1999,
    genre: "Sci-Fi",
    rating: 8.7,
    description:
      "A computer hacker learns from mysterious rebels about the true nature of his reality and his role in the war against its controllers, in a simulated world created by sentient machines.",
  },
  {
    title: "Parasite",
    director: "Bong Joon-ho",
    year: 2019,
    genre: "Thriller",
    rating: 8.5,
    description:
      "Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan, culminating in an unforgettable and shocking climax.",
  },
  {
    title: "Forrest Gump",
    director: "Robert Zemeckis",
    year: 1994,
    genre: "Drama",
    rating: 8.8,
    description:
      "The history of the United States from the 1950s to the 70s unfolds from the perspective of an Alabama man with an IQ of 75, who yearns to be reunited with his childhood sweetheart.",
  },
  {
    title: "Spirited Away",
    director: "Hayao Miyazaki",
    year: 2001,
    genre: "Animation",
    rating: 8.6,
    description:
      "During her family's move to the suburbs, a sullen 10-year-old girl wanders into a world ruled by gods, witches, and spirits, and where humans are changed into beasts.",
  },
  {
    title: "Goodfellas",
    director: "Martin Scorsese",
    year: 1990,
    genre: "Crime",
    rating: 8.7,
    description:
      "The story of Henry Hill and his life in the mob, covering his relationship with his wife Karen Hill and his mob partners Jimmy Conway and Tommy DeVito in the Italian-American crime syndicate.",
  },
  {
    title: "The Silence of the Lambs",
    director: "Jonathan Demme",
    year: 1991,
    genre: "Thriller",
    rating: 8.6,
    description:
      "A young F.B.I. cadet must receive the help of an incarcerated and manipulative cannibal killer to help catch another serial killer, a madman who skins his victims.",
  },
  {
    title: "Schindler's List",
    director: "Steven Spielberg",
    year: 1993,
    genre: "Drama",
    rating: 9.0,
    description:
      "In German-occupied Poland during World War II, industrialist Oskar Schindler gradually becomes concerned for his Jewish workforce after witnessing their persecution by the Nazis.",
  },
  {
    title: "Blade Runner 2049",
    director: "Denis Villeneuve",
    year: 2017,
    genre: "Sci-Fi",
    rating: 8.0,
    description:
      "Young Blade Runner K's discovery of a long-buried secret leads him on a quest to find Rick Deckard, a former Blade Runner who has been missing for thirty years.",
  },
  {
    title: "Whiplash",
    director: "Damien Chazelle",
    year: 2014,
    genre: "Drama",
    rating: 8.5,
    description:
      "A promising young drummer enrolls at a cut-throat music conservatory where his dreams of greatness are mentored by an instructor who will stop at nothing to realize a student's potential.",
  },
  {
    title: "The Grand Budapest Hotel",
    director: "Wes Anderson",
    year: 2014,
    genre: "Comedy",
    rating: 8.1,
    description:
      "A writer encounters the owner of an aging high-class hotel, who tells him of his early years serving as a lobby boy in the hotel's glorious years under an exceptional concierge.",
  },
  {
    title: "Oldboy",
    director: "Park Chan-wook",
    year: 2003,
    genre: "Thriller",
    rating: 8.4,
    description:
      "After being kidnapped and imprisoned for fifteen years, Oh Dae-Su is released, only to find that he must find his captor in five days, uncovering a twisted tale of vengeance and dark secrets.",
  },
  {
    title: "2001: A Space Odyssey",
    director: "Stanley Kubrick",
    year: 1968,
    genre: "Sci-Fi",
    rating: 8.3,
    description:
      "After uncovering a mysterious artifact buried beneath the lunar surface, a spacecraft is sent to Jupiter to find its origins, with the help of the advanced supercomputer H.A.L. 9000.",
  },
  {
    title: "The Truman Show",
    director: "Peter Weir",
    year: 1998,
    genre: "Drama",
    rating: 8.2,
    description:
      "An insurance salesman discovers his whole life is actually a reality TV show, broadcast to millions of viewers worldwide, and must find the courage to escape the fabricated world.",
  },
  {
    title: "Amelie",
    director: "Jean-Pierre Jeunet",
    year: 2001,
    genre: "Romance",
    rating: 8.3,
    description:
      "Amelie is an innocent and naive girl in Paris with her own sense of justice. She decides to help those around her and, along the way, discovers love and the beauty of everyday life.",
  },
  {
    title: "Fight Club",
    director: "David Fincher",
    year: 1999,
    genre: "Drama",
    rating: 8.8,
    description:
      "An insomniac office worker and a devil-may-care soap maker form an underground fight club that evolves into much more, challenging consumerism and modern masculinity.",
  },
  {
    title: "City of God",
    director: "Fernando Meirelles",
    year: 2002,
    genre: "Crime",
    rating: 8.6,
    description:
      "In the slums of Rio de Janeiro, two boys growing up in violent surroundings take different paths: one becomes a photographer, the other a drug dealer, and their stories collide.",
  },
  {
    title: "The Lord of the Rings: The Return of the King",
    director: "Peter Jackson",
    year: 2003,
    genre: "Fantasy",
    rating: 9.0,
    description:
      "Gandalf and Aragorn lead the World of Men against Sauron's army to draw his gaze from Frodo and Sam as they approach Mount Doom with the One Ring to destroy it.",
  },
  {
    title: "The Lord of the Rings: The Fellowship of the Ring",
    director: "Peter Jackson",
    year: 2001,
    genre: "Fantasy",
    rating: 8.8,
    description:
      "A meek Hobbit from the Shire and eight companions set out on a journey to destroy the powerful One Ring and save Middle-earth from the Dark Lord Sauron.",
  },
  {
    title: "The Departed",
    director: "Martin Scorsese",
    year: 2006,
    genre: "Crime",
    rating: 8.5,
    description:
      "An undercover cop and a mole in the police attempt to identify each other while infiltrating an Irish gang in South Boston, leading to a deadly game of deception.",
  },
  {
    title: "The Prestige",
    director: "Christopher Nolan",
    year: 2006,
    genre: "Thriller",
    rating: 8.5,
    description:
      "After a tragic accident, two stage magicians in 1890s London engage in a battle to create the ultimate illusion while sacrificing everything they have to outwit each other.",
  },
  {
    title: "The Lives of Others",
    director: "Florian Henckel von Donnersmarck",
    year: 2006,
    genre: "Drama",
    rating: 8.4,
    description:
      "In 1984 East Berlin, an idealistic agent of the secret police conducting surveillance on a writer and his lover finds himself becoming increasingly absorbed by their lives.",
  },
  {
    title: "Rear Window",
    director: "Alfred Hitchcock",
    year: 1954,
    genre: "Thriller",
    rating: 8.5,
    description:
      "A photographer in a wheelchair spies on his neighbors from his Greenwich Village courtyard apartment window, and becomes convinced one of them has committed murder.",
  },
  {
    title: "Psycho",
    director: "Alfred Hitchcock",
    year: 1960,
    genre: "Horror",
    rating: 8.5,
    description:
      "A secretary on the run checks into a remote motel run by a dutiful young man under the domination of his mother, and the visit turns deadly in the most unexpected way.",
  },
  {
    title: "Alien",
    director: "Ridley Scott",
    year: 1979,
    genre: "Horror",
    rating: 8.5,
    description:
      "The crew of a commercial spacecraft encounters a deadly lifeform after investigating an unknown transmission, and must fight for survival against a creature that hunts them one by one.",
  },
  {
    title: "Gladiator",
    director: "Ridley Scott",
    year: 2000,
    genre: "Action",
    rating: 8.5,
    description:
      "A former Roman General sets out to exact vengeance against the corrupt emperor who murdered his family and sent him into slavery, rising through the ranks of gladiatorial combat.",
  },
  {
    title: "The Pianist",
    director: "Roman Polanski",
    year: 2002,
    genre: "Drama",
    rating: 8.5,
    description:
      "A Polish Jewish musician struggles to survive the destruction of the Warsaw ghetto of World War II, hiding in the ruins of the city while bearing witness to unimaginable atrocities.",
  },
  {
    title: "Memento",
    director: "Christopher Nolan",
    year: 2000,
    genre: "Thriller",
    rating: 8.4,
    description:
      "A man with short-term memory loss attempts to track down his wife's killer using notes and tattoos as clues, with the story told in reverse chronological order.",
  },
  {
    title: "Apocalypse Now",
    director: "Francis Ford Coppola",
    year: 1979,
    genre: "Drama",
    rating: 8.4,
    description:
      "A U.S. Army officer serving in Vietnam is tasked with assassinating a renegade Special Forces colonel who has set himself up as a god among a local tribe across the border in Cambodia.",
  },
  {
    title: "Taxi Driver",
    director: "Martin Scorsese",
    year: 1976,
    genre: "Drama",
    rating: 8.2,
    description:
      "A mentally unstable veteran works as a nighttime taxi driver in New York City, where the perceived decadence and sleaze fuels his unhinged urge for violent action.",
  },
  {
    title: "No Country for Old Men",
    director: "Joel Coen",
    year: 2007,
    genre: "Thriller",
    rating: 8.2,
    description:
      "Violence and mayhem ensue after a hunter stumbles upon a drug deal gone wrong and more than two million dollars in cash near the Rio Grande, pursued by a relentless hitman.",
  },
  {
    title: "Eternal Sunshine of the Spotless Mind",
    director: "Michel Gondry",
    year: 2004,
    genre: "Romance",
    rating: 8.3,
    description:
      "When their relationship turns sour, a couple undergoes a medical procedure to have each other erased from their memories, but the process reveals how much they truly meant to each other.",
  },
  {
    title: "The Social Network",
    director: "David Fincher",
    year: 2010,
    genre: "Drama",
    rating: 7.8,
    description:
      "As Harvard student Mark Zuckerberg creates the social networking site that would become known as Facebook, he is sued by the twins who claimed he stole their idea and by the co-founder who was later squeezed out of the business.",
  },
  {
    title: "Arrival",
    director: "Denis Villeneuve",
    year: 2016,
    genre: "Sci-Fi",
    rating: 7.9,
    description:
      "A linguist works with the military to communicate with alien lifeforms after twelve mysterious spacecraft appear around the world, discovering that their language holds a profound secret about the nature of time.",
  },
  {
    title: "Everything Everywhere All at Once",
    director: "Daniel Kwan",
    year: 2022,
    genre: "Sci-Fi",
    rating: 7.8,
    description:
      "A middle-aged Chinese immigrant is swept up into an insane adventure in which she alone can save existence by exploring other universes and connecting with the lives she could have led.",
  },
  {
    title: "Mad Max: Fury Road",
    director: "George Miller",
    year: 2015,
    genre: "Action",
    rating: 8.1,
    description:
      "In a post-apocalyptic wasteland, a woman rebels against a tyrannical ruler in search of her homeland with the aid of a group of female prisoners, a psychotic worshipper, and a drifter named Max.",
  },
  {
    title: "Pan's Labyrinth",
    director: "Guillermo del Toro",
    year: 2006,
    genre: "Fantasy",
    rating: 8.2,
    description:
      "In the Falangist Spain of 1944, the bookish young stepdaughter of a sadistic army officer escapes into an eerie but captivating fantasy world, completing dangerous tasks given by a mysterious faun.",
  },
  {
    title: "The Seventh Seal",
    director: "Ingmar Bergman",
    year: 1957,
    genre: "Drama",
    rating: 8.1,
    description:
      "A knight returning from the Crusades plays a game of chess with Death while plague ravages the land around him, seeking answers about life, faith, and the silence of God.",
  },
  {
    title: "In the Mood for Love",
    director: "Wong Kar-wai",
    year: 2000,
    genre: "Romance",
    rating: 8.1,
    description:
      "Two neighbors in 1960s Hong Kong discover that their spouses are having an affair, and slowly develop feelings for each other while struggling to keep their relationship platonic.",
  },
  {
    title: "Rashomon",
    director: "Akira Kurosawa",
    year: 1950,
    genre: "Crime",
    rating: 8.2,
    description:
      "The rape of a bride and the murder of her samurai husband are recalled from the perspectives of a bandit, the bride, the samurai's ghost, and a woodcutter, each telling a different version of events.",
  },
  {
    title: "Seven Samurai",
    director: "Akira Kurosawa",
    year: 1954,
    genre: "Action",
    rating: 8.6,
    description:
      "A poor village under attack by bandits recruits seven unemployed samurai to help them defend themselves, leading to an epic battle between honor and survival in feudal Japan.",
  },
  {
    title: "Stalker",
    director: "Andrei Tarkovsky",
    year: 1979,
    genre: "Sci-Fi",
    rating: 8.1,
    description:
      "A guide leads two men through an area known as the Zone to find a room that grants a person's innermost desires, exploring themes of faith, hope, and the nature of human wishes.",
  },
  {
    title: "There Will Be Blood",
    director: "Paul Thomas Anderson",
    year: 2007,
    genre: "Drama",
    rating: 8.2,
    description:
      "A ruthless silver miner turned oil prospector moves to oil-rich California at the turn of the century, where his ambition and greed bring him into conflict with a young preacher.",
  },
  {
    title: "Memories of Murder",
    director: "Bong Joon-ho",
    year: 2003,
    genre: "Crime",
    rating: 8.1,
    description:
      "In a small Korean province in 1986, three detectives struggle with the case of multiple young women being found raped and murdered by an unknown assailant, South Korea's first serial murder case.",
  },
  {
    title: "12 Angry Men",
    director: "Sidney Lumet",
    year: 1957,
    genre: "Drama",
    rating: 9.0,
    description:
      "The jury in a New York City murder trial is frustrated by a single holdout juror who insists on discussing the case before voting, forcing the others to reconsider the evidence and their own prejudices.",
  },
]

function esc(s: string): string {
  return s.replace(/\\/g, "\\\\").replace(/'/g, "\\'")
}

let engineInstance: Engine | null = null
let enginePromise: Promise<Engine> | null = null

async function getEngine(): Promise<Engine> {
  if (engineInstance) return engineInstance

  if (enginePromise) return enginePromise

  enginePromise = (async () => {
    const { Engine } = await import("@jaepil/uqa")
    const engine = new Engine()

    await engine.sql(`
      CREATE TABLE movies (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        director TEXT NOT NULL,
        year INTEGER NOT NULL,
        genre TEXT NOT NULL,
        rating REAL NOT NULL,
        description TEXT NOT NULL
      )
    `)

    await engine.sql(`
      CREATE INDEX idx_movies_fts ON movies
      USING gin (title, director, genre, description)
    `)

    for (const movie of SAMPLE_DATA) {
      await engine.sql(
        `INSERT INTO movies (title, director, year, genre, rating, description)
         VALUES ($1, $2, $3, $4, $5, $6)`,
        [
          movie.title,
          movie.director,
          movie.year,
          movie.genre,
          movie.rating,
          movie.description,
        ],
      )
    }

    await engine.sql("SELECT * FROM create_graph('cinema')")

    const directorSet = new Set<string>()
    const genreSet = new Set<string>()
    for (const m of SAMPLE_DATA) {
      directorSet.add(m.director)
      genreSet.add(m.genre)
    }

    for (let i = 0; i < SAMPLE_DATA.length; i++) {
      const m = SAMPLE_DATA[i]
      await engine.sql(
        `SELECT * FROM cypher('cinema', $$
          CREATE (:Movie {movie_id: ${i + 1}, title: '${esc(m.title)}', year: ${m.year}, rating: ${m.rating}})
        $$) AS (v agtype)`,
      )
    }

    for (const name of directorSet) {
      await engine.sql(
        `SELECT * FROM cypher('cinema', $$
          CREATE (:Director {name: '${esc(name)}'})
        $$) AS (v agtype)`,
      )
    }

    for (const name of genreSet) {
      await engine.sql(
        `SELECT * FROM cypher('cinema', $$
          CREATE (:Genre {name: '${esc(name)}'})
        $$) AS (v agtype)`,
      )
    }

    for (let i = 0; i < SAMPLE_DATA.length; i++) {
      const m = SAMPLE_DATA[i]
      await engine.sql(
        `SELECT * FROM cypher('cinema', $$
          MATCH (mv:Movie {movie_id: ${i + 1}}), (d:Director {name: '${esc(m.director)}'})
          CREATE (mv)-[:DIRECTED_BY]->(d)
        $$) AS (v agtype)`,
      )
      await engine.sql(
        `SELECT * FROM cypher('cinema', $$
          MATCH (mv:Movie {movie_id: ${i + 1}}), (g:Genre {name: '${esc(m.genre)}'})
          CREATE (mv)-[:HAS_GENRE]->(g)
        $$) AS (v agtype)`,
      )
    }

    engineInstance = engine
    return engine
  })()

  return enginePromise
}

export function useUQAEngine() {
  const [loading, setLoading] = useState(false)
  const [ready, setReady] = useState(false)
  const engineRef = useRef<Engine | null>(null)

  const initialize = useCallback(async () => {
    if (engineRef.current) {
      setReady(true)
      return
    }

    setLoading(true)
    const engine = await getEngine()
    engineRef.current = engine
    setLoading(false)
    setReady(true)
  }, [])

  const executeSQL = useCallback(
    async (query: string): Promise<QueryResult> => {
      const engine = engineRef.current
      if (!engine) {
        return { result: null, error: "Engine not initialized", elapsed: 0 }
      }

      const start = performance.now()
      try {
        const result = await engine.sql(query)
        const elapsed = performance.now() - start

        if (result) {
          return {
            result: {
              columns: [...result.columns],
              rows: result.rows.map((row) => ({ ...row })),
            },
            error: null,
            elapsed,
          }
        }

        return { result: { columns: [], rows: [] }, error: null, elapsed }
      } catch (err) {
        const elapsed = performance.now() - start
        return {
          result: null,
          error: err instanceof Error ? err.message : String(err),
          elapsed,
        }
      }
    },
    [],
  )

  return { loading, ready, initialize, executeSQL }
}
