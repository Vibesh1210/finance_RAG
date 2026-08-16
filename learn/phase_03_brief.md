# Phase 3 brief — the measuring stick and the search

*Plain-language, written before building (learning loop, DECISIONS #6). Glossary
terms are explained in place — no assumed jargon.*

## Where this sits

Phases 0–2 built the **pantry**: the filings are downloaded, the numbers are loaded,
the text is chopped into searchable pieces and turned into "meaning fingerprints"
(embeddings). Nothing has *answered a question* yet. Phase 3 is where the system
starts to find things — and, just as importantly, where we build the **ruler** that
tells us whether it finds them well.

## The two things we build (and why the ruler comes first)

**1. The measuring stick (the "golden bank").** Sixty questions with known-correct
answers, written down and frozen. Forty are about *text* ("what risks did Apple
flag?") and twenty are about *numbers* ("what was NVIDIA's FY2025 revenue?"). Each
question is labelled with what a right answer must contain — which filing, which
section, which exact figure.

Why build this *first*: without a ruler, "improving" the search is guessing. You
change something, it feels better, you ship it — and you have no idea if it actually
got better or worse. The rule we follow (straight from the plan) is **the measuring
stick exists before anything is tuned.** Measure, then improve, then measure again.

**2. The search itself ("hybrid retrieval").** Given a question, find the ~20 most
relevant text pieces. "Hybrid" because it runs **two different searches and merges
them**, since each is good at what the other is bad at:

- **Keyword search** — matches the actual words. Great for exact things: a ticker,
  "gross margin," a product name. Bad when the filing says the same idea in different
  words than the question.
- **Meaning search** — matches *ideas*, using those embedding fingerprints. Great when
  the wording differs ("headwinds" vs "challenges"). Bad at exact tokens and numbers.

Each search returns its top 50. Then we **merge the two ranked lists** with a simple,
well-known recipe called Reciprocal Rank Fusion: a piece that both searches rank
highly floats to the top; a piece only one search liked still gets a fair shot. The
merged top 20 is the answer to "what's relevant." (There's a fancier polishing step
called *reranking* — that's deliberately **later**, in M1/Phase 8, not now.)

## The one rule that cannot bend: no looking into the future

Every search carries a date — the **"as of"** date — meaning *"answer as if today
were this date."* A text piece is only allowed to be found if it was **already public
on that date**. This is the cardinal rule of the whole project: answering a
"what did we know in October?" question using a document that came out in December is
the one unforgivable bug (it silently ruins any historical analysis).

We enforce it the strong way: the date filter lives **inside the database query
itself** (`knowledge_time <= as_of`), in *both* searches — not as an afterthought
that strips future results later. A piece newer than the question's date can never
even be considered. And Phase 3 ships a dedicated test (the **look-ahead gate**) that
tries historical questions and fails the build if any future document sneaks through.

## How we'll know Phase 3 is done (its gate)

- The 60 questions are written, frozen, and pass a "no leaks" lint (the question text
  doesn't accidentally give away the answer).
- On the text questions, the search finds the right passage often enough to clear a
  recorded baseline (measured with standard search-quality scores — think "how often
  is the right answer in the top 10, and how near the top").
- The look-ahead gate is green (no future documents, ever).
- The merged search beats *either* single search alone — proof the hybrid is worth it.

## Build order (what I'll do, and what needs you)

1. **The retriever** (pure engineering — building now): the two searches + the merge +
   the as-of filter, tested on the real, now-fully-embedded corpus.
2. **The eval harness**: the code that runs a question through the retriever and scores
   it against the golden answer.
3. **The golden bank** (collaborative): I draft the 60 questions to the required mix;
   **you** confirm the correct answers against the filings (~2 hours — the same kind of
   by-hand check as the Phase 2 spot-checks, and the quant answers actually lean on
   those spot-checks).
4. **The look-ahead gate** and the **Phase 3 gate** that ties it all together.

Note: the numbers half of the golden bank stays *provisional* until the Phase 2
spot-checks are done, because a "correct number" answer is only as trustworthy as the
data it's checked against (DECISIONS.md #12).
