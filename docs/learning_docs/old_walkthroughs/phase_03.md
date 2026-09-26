> **Old walkthrough — being replaced.** Parts of this no longer match the code; see `README.md` in this folder before relying on it.

# Phase 3 in plain words — the ruler and the search

*(Terms: golden bank, recall@k, MRR, nDCG, dense/sparse, RRF, look-ahead → `glossary.md`.)*

Phase 2 stocked the pantry. Phase 3 does two things: it builds the **ruler** that says
whether the system is any good, and it builds the **search** that finds relevant text.
The ruler comes first — on purpose.

## Idea 1: you can't improve what you can't measure

Before touching search quality, we wrote **60 questions with known-correct answers** and
froze them (the "golden bank"): 40 about text, 20 about numbers, deliberately including
the nasty cases (fiscal-label traps, point-in-time windows, and six that *should be
refused*). The rule, straight from the plan: *the measuring stick exists before anything
is tuned.* Otherwise "it feels better" is the only evidence you have, and that's not
evidence. We even lint the questions so they don't leak their own answers.

## Idea 2: two searches, because each is bad where the other is good

- **Keyword search** matches the actual words — great for tickers and exact terms, bad
  when the filing phrases an idea differently than the question.
- **Meaning search** matches ideas via embeddings — great across wording, bad at exact
  tokens.

We run both (top-50 each) and **merge** them with Reciprocal Rank Fusion: each result
scores `1/(60 + its rank)` in each list, summed. A passage both searches like floats up;
one only a single search liked still gets a fair shot. The merged top-20 is "what's
relevant." (A fancier re-ranking step is deliberately deferred to a later milestone.)

## Idea 3: the cardinal rule, enforced mechanically

Every search carries the question's **as-of date**, and the "only what was public by then"
filter lives *inside* both database queries (`knowledge_time <= as_of`) — not as an
afterthought that strips future results later. A passage newer than the question's date
can never even be considered. A dedicated **look-ahead gate** runs historical questions
and fails the build if any future document sneaks through. On this corpus it found **zero
leaks**, with six genuinely historical questions that *would* leak if the filter ever broke
— so the test has teeth.

## Idea 4: measuring retrieval

Three standard scores, all computed against the golden answers: **recall@10** (did the
right passage make the top 10?), **MRR** (how near the top was the first right one?), and
**nDCG@10** (are the good ones ranked high?). The first honest run: the hybrid scored
**0.71 recall@10**, beating meaning-alone (0.63) and keyword-alone (0.15) — which is
exactly the sanity check that proves the hybrid is worth the complexity.

## What "tested" means here

The fusion math and metrics are pure functions with unit tests; the look-ahead gate and
the "hybrid beats each single leg" check run against the live corpus. The recall *baseline*
is frozen only after you verify the 60 answers — a number you can't trust yet shouldn't
become the bar everything else must clear.

## Exercise — Reciprocal Rank Fusion by hand (~30 min)

```
uv run python learn/exercises/phase03_rrf_exercise.py
```

Implement `rrf()` until the checks pass. When stuck, read `rrf_fuse` in
`src/us_rag/query/retrieve.py`.

**You've consolidated this phase when you can answer, in your own words:**
1. Why build the 60-question ruler *before* improving the search?
2. Why keep both a keyword and a meaning search instead of just the better one?
3. Why is the as-of filter inside the database query rather than applied afterwards?
