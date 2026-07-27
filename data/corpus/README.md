# Corpus — synthetic example amendments

The two documents in `data/samples/` are **real** RBI amendments (verified from source PDFs).

The `.txt` files here are **synthetic** — written by hand to follow the exact same RBI
amendment format — so the pipeline can exercise paths the two real inserts don't cover:

- **`rrb-68c-third-amendment-2027.txt`** — a *substitute* that revises RRB clause 68C effective
  1 Apr 2027. This is what gives clause 68C a real version history (two versions on the timeline)
  and makes the date-flip show *changing* text rather than text merely appearing.
- **`sfb-second-amendment.txt`** — the SNFA insert for a third entity (Small Finance Banks,
  clauses 133C/133D), so the corpus spans more than two entity types.

`make db-sync` ingests both the real PDFs and these text amendments, in effective-date order.
They are clearly separated so it's always honest which documents are real and which are examples.
