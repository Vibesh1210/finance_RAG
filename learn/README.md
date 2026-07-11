# Learning track

This folder exists because the project has **two goals with equal weight**: a
working system, and you being able to explain and rebuild its core ideas.

## How the loop works (agreed 2026-07-12)

For every phase from here on:

1. **Before building** — `learn/phase_NN_brief.md`: the concept in plain words.
   What problem this phase solves, why it matters, what choices we have. No
   unexplained jargon, ever. You read this BEFORE any code exists.
2. **Build** — Claude builds at full speed (technical writeup goes to
   `phases_docs/phase_NN.md` as before).
3. **After the gate is green** — `learn/phase_NN.md`: a plain-language
   walkthrough of what was actually built, plus **one exercise** where you
   rebuild the phase's core idea yourself, small enough for an evening.
4. **Q&A** — ask anything, any level, at any time. "What does X even mean" is
   always a good question. When you can explain the phase back in your own
   words, it's consolidated.

The exercises are self-checking wherever possible — you run them and they tell
you if you're right, the same way the gates tell the build if it's right.

## Read in this order

| File | What it gives you |
|---|---|
| `glossary.md` | Every term the project uses, in plain words, with examples from our own repo |
| `phase_00.md` | What Phase 0 built and why + a break-it-on-purpose exercise |
| `phase_01.md` | What Phase 1 built (the heart of the system) + the as-of exercise |
| `exercises/` | Runnable exercise files |

## The honest rule

If a walkthrough or brief uses a term that isn't in the glossary and isn't
explained inline, that's a bug in the document — say so and it gets fixed.
