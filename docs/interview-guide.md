# Interview Guide — RBI Regulatory Timeline Engine

A study sheet for explaining this project out loud. Read it a few times until you can say
it in **your own words**. You do not need to memorize it — you need to *understand* it.
Everything below is written plainly on purpose.

---

## 0. The one thing to remember

> **Normal AI search gives you the wrong answer for regulations, in two specific ways.
> I proved it with numbers, and I built the system that fixes it.**

If you only remember one sentence, remember that one.

---

## 1. The 30-second pitch (say this first)

> "India's central bank writes the *same* rule slightly differently for each *type* of bank,
> and rules are often published months before they actually take effect. If you search these
> documents with normal AI, it confidently gives you the wrong bank's version, or a rule that
> isn't active yet. My project fixes that: it checks **which bank** and **what date** *before*
> it searches, and it returns the exact official wording — or says 'not yet in force' instead
> of guessing. I also built the normal-AI version side by side to prove the difference: it
> scored 4%, mine scored 69%."

That's the whole thing. Everything else is detail.

---

## 2. The problem — explain it like you're talking to a friend

Two real facts about Indian banking rules make this hard:

1. **Same rule, different "address" for each bank type.**
   The exact same policy becomes *clause 68C* for a Regional Rural Bank but *clause 119C* for a
   Local Area Bank. The text is **95.7% identical** — the only difference is a couple of words.

2. **Published is not the same as active.**
   A rule can be *published* on July 16 but only *take effect* on October 1. In between, the
   **old** rule is still the correct answer.

**Why normal AI search breaks on this:**
Normal AI search matches by *meaning*. But the two banks' rules *mean* almost exactly the same
thing — so it can't tell them apart and often returns the wrong bank's. And it has **no idea what
"as of September" means** — it'll hand you a rule that isn't active yet. It's confident, fluent,
and wrong on both *who* and *when*.

**Analogy you can use:** "It's like a library where every book has a different edition for each
kind of reader, and each edition has a 'valid from' date. If you just search by topic, you grab
the wrong reader's edition, or last year's. My system checks who you are and today's date first,
then hands you the exact right page."

---

## 3. What I built — in plain terms

Instead of "search by meaning and hope," my system does three things in order:

1. **Filter by WHO** — narrow to the right bank type first.
2. **Filter by WHEN** — keep only the version that was actually in force on that date.
3. **Return the exact wording** — pulled word-for-word from the official document.

And critically: **if nothing fits, it says so** ("not yet in force" / "no such rule for this
bank") instead of making something up.

The slogan for this is **"filter before you retrieve."** Let meaning-based search do its job
*only after* the hard facts (bank type, date) have already picked the right slice — so it can't
pick the wrong one.

---

## 4. The live demo — click this, say this

Open the app (4 tabs). Here's the script for each.

### Tab 1 — "As-of explorer" (the money shot)
- **Do:** It opens on a Regional Rural Bank, clause 68C. Point at the indigo "Not yet in force" badge.
- **Say:** "Right now the date is before October 1, so the rule isn't active yet — and the system
  says exactly that."
- **Do:** Drag the slider to the right, past the October marker.
- **Say:** "Watch — as I cross the effective date, the same clause flips to 'In force' and the
  real text appears. Same clause, the answer changes with the date. Normal search ignores this
  completely."

### Tab 2 — "Naive RAG vs full" (the proof)
- **Do:** Pick the first scenario. Point at the two panels.
- **Say:** "Same question on both sides. On the left, my system returns the correct Regional Rural
  Bank rule. On the right, normal AI search returned the **Local Area Bank's** rule — the wrong
  bank — and here's the label flagging that error. This is the core problem, live."

### Tab 3 — "Change feed"
- **Say:** "This shows one policy landing in different clause numbers across bank types — my system
  automatically links them and shows how similar they are (0.977)."

### Tab 4 — "Clause timeline"
- **Say:** "And this is the full version history of a single clause — when it started, and which
  amendment created it."

**The three "wow" moments:** (1) the date flip, (2) the wrong-bank comparison, (3) it admits when
it doesn't know.

---

## 5. How it works under the hood (architecture, simply)

There are two halves. This is the most important distinction to get right:

### Half A — Reading the documents (done ahead of time)
The AI's job is to **read each amendment and file it correctly** — like a librarian. It pulls out:
which bank, which chapter, which clause numbers, and the dates. It turns messy PDF prose into neat,
structured records, and saves them in a database as a **timeline** (each clause, each version, with
"valid from" and "valid to" dates).

### Half B — Answering your question (instant)
When you ask something, there's **no AI involved** — it's just a fast database lookup: filter to the
right bank and date, return the exact text. That's why it's instant and can't make things up.

**The key line to say:** "The AI runs when *reading* documents, not when *answering*. So answers are
fast and always the exact official wording."

### The pieces (if they ask about the stack)
- **Python** does the document processing (reading PDFs, running the local AI models).
- A **local AI model** (runs on my laptop, no cloud cost) turns each amendment into structured data.
- **Postgres** (a database) stores the clause timeline.
- A **Node/Express API** reads the database and serves answers.
- A **React** front-end is the UI you're looking at.

**Whiteboard version (draw this if asked):**
```
PDFs → [AI reads & structures] → Database (clauses + bank + dates)
                                        │
              your question (who? when?) ┘→ filter → exact answer  OR  "not yet / don't know"
```

---

## 6. Why I made each choice (have these ready)

**"Why not just use RAG / normal vector search?"**
> "Because it fails here, and I can prove it. Near-identical texts confuse meaning-based search, and
> it has no sense of dates. I built that version as a baseline — it scored 4% and returned the wrong
> bank half the time. Mine scored 69% with zero wrong-bank errors."

**"Why return exact text instead of a chatbot answer?"**
> "It's legal text — one wrong word changes the meaning. Generating or paraphrasing it would be a
> hallucination risk. So I return the exact official wording, verbatim."

**"Why local AI models instead of a big cloud model?"**
> "Cost control was a real requirement — I kept the whole thing under $20. Local models are free and
> handle the document-reading fine. I reserved the one paid cloud step for an optional
> double-check layer."

**"Why Node/Express and not Python for the API?"**
> "The heavy logic stays in Python; the API just reads the database, so it's a thin layer. I used
> Node because I'm comfortable in it, and I ported the one important piece of logic to JavaScript
> *with its own tests* so the two languages can't disagree."

**"Why does it refuse to answer sometimes?"**
> "For regulations, a confident wrong answer is dangerous. Saying 'I can't resolve this, here's what
> I considered' is safer and more honest — so I made abstention a real, first-class result, not an
> error."

---

## 7. The hard questions (rehearse these — they *will* come up)

**"Isn't this just RAG?"**
> "The naive version is — I built it on purpose as the thing to beat. My real system deliberately
> isn't: instead of searching by meaning, it filters by bank and date first, then does an exact
> lookup. The numbers show why that matters: 4% vs 69%."

**"You only have two documents — isn't it kind of hardcoded?"** *(your biggest question — answer it calmly)*
> "The corpus is small on purpose. I hand-labelled the correct answers so I could measure accuracy
> honestly, and I picked the two real amendments that are the *hardest* case — 95.7% identical text,
> different clause numbers, delayed effective date. Nothing's hardcoded — every answer is a live
> database query; change the bank or the date and it responds. The pipeline handles any amendment;
> I kept the set focused so I could prove correctness with real numbers instead of hand-waving."

**"How do you know it's not hallucinating?"**
> "Two guards. One, the answer text is never generated — it's pulled word-for-word from the source,
> so it can't invent wording. Two, when the AI reads a document it has to quote the exact sentence
> that justifies each extraction, and I check that the quote really appears in the source. If it
> doesn't, the system marks it 'unresolved' instead of guessing."

**"How would this scale to thousands of documents?"**
> "The answering side is just a database lookup, so it scales like any normal app. The reading side
> is heavier — it's an AI step per document — but it's one-time and cached. At scale I'd turn on the
> AWS double-check step for the ambiguous cases, and connect the document scraper to pull new
> amendments automatically."

**"What was the hardest part?"**
> "Getting a small local model to output reliable structured data on a CPU. My first version had it
> reproduce the clause text, which was slow and got cut off mid-sentence. I flipped the design: the
> model only outputs the clause *number* and structure, and my code slices the actual text from the
> source. Faster, more reliable, and it removed a whole class of hallucination."

**"What would you do differently, or do next?"**
> "Next: wire the AWS verification step for a real cost-vs-accuracy number, and expand the corpus
> with the scraper. If I restarted, I'd set up a separate test database sooner — right now my tests
> share the dev database, which I worked around but isn't ideal."

**"Walk me through what happens when I ask a question."**
> "The system works out three things: the bank type, the clause, and the date. It filters the
> database to that bank and clause, then checks which version was valid on that date. If one was, it
> returns that exact text. If the rule wasn't active yet, it says so and shows what it considered —
> it never guesses."

---

## 8. Numbers to have on the tip of your tongue

- **4.2%** — naive AI's accuracy. **68.8%** — my system's accuracy.
- **47.9%** — how often naive AI returned the *wrong bank's* rule. **0%** — mine.
- **16.7%** — how often naive AI returned a *not-yet-active* rule. **0%** — mine.
- **95.7%** — how similar the two banks' texts are (why meaning-search fails).
- **48** — hand-written test questions I graded the system against.
- Answering is a **database lookup** (instant); the **AI runs only when reading documents**.

---

## 9. Mini-glossary (so no word trips you up)

- **RAG** — "Retrieval-Augmented Generation." The standard approach: search documents by meaning,
  then have AI write an answer. My project shows where it fails.
- **Embedding** — turning text into numbers that capture its *meaning*, so you can find "similar"
  text. The tool naive search relies on.
- **Entity** — the type of regulated body (Regional Rural Bank, Local Area Bank, etc.).
- **Clause** — a numbered rule inside a regulation (e.g., 68C).
- **Effective date** — when a rule actually starts applying (vs. when it was published).
- **Abstention** — the system saying "I can't answer this confidently" instead of guessing.
- **Pipeline** — the assembly line that reads a PDF and turns it into structured data.
- **Postgres / pgvector** — the database, and the add-on that lets it store "meaning" vectors.

---

## 10. If you freeze — safe recovery lines

- "Let me show you rather than tell you —" (then click the date flip; it explains itself).
- "The one-sentence version is: it checks *who's asking* and *when* before it answers."
- "I can go deeper on any part — the document reading, the database, or the evaluation?"
  (puts you back in control by letting *them* pick.)

You built a system that finds a real flaw in the most popular AI technique and fixes it, with
measured proof. That's a strong, senior story. Tell it plainly and let the demo do the rest.
