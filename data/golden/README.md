# Golden set — hand-labelled ground truth

`questions.jsonl` is **hand-authored** and **committed**. Never regenerate it
(CLAUDE.md §13) — every accuracy number in the project depends on it staying stable.

48 questions, 8 per category:

| Category | What it tests | Expected behaviour |
|---|---|---|
| `lookup` | clause in force, correct entity | return the text |
| `temporal_trap` | `as_of` before the 2026-10-01 effective date | abstain: `not_yet_in_force` |
| `entity_trap` | one entity asked using another's clause number | abstain: `no_provision` (never return the other entity's text) |
| `cross_entity` | "the RRB equivalent of LAB 119C?" | the equivalent clause number |
| `non_existent` | a clause (or family) that does not exist | abstain: `no_provision` |
| `cascade` | the fan-out / parent-amendment relationships | the related entities/documents |

## Schema (one JSON object per line)

- `id` — `g001`… unique
- `category` — one of the six above
- `question` — natural-language question
- `entity_type` — entity code (`RRB`,`LAB`,`SFB`,…); may be null for corpus-level cascade Qs
- `md_family` — default `IRACP`
- `clause` — the clause asked about (nullable)
- `as_of` — ISO date (nullable for cross-entity/cascade)
- `expected_status` — `in_force` | `not_yet_in_force` | `no_provision` | `equivalence` | `cascade`
- `expected_clause` — the clause that should be cited / the equivalent (nullable)
- `expected_entities` — list, for cascade/cross-entity fan-out
- `expected_contains` — a verbatim substring the correct in-force answer must contain
- `reference_entity` / `reference_clause` — the "given" side of a cross-entity or entity-trap question
- `note` — why the answer is what it is (absolute dates; today = 2026-07-24)

## Grounding

Facts are from the two verified sample PDFs (RRB 68C/68D, LAB 119C/119D; issued
2026-07-16, effective 2026-10-01) and Week-1 recon (SFB 133C/133D; the 8-entity
batch). `tests/test_golden.py` cross-checks the `lookup`/`temporal_trap`/
`entity_trap`/`non_existent` labels against the resolver on a known timeline.
