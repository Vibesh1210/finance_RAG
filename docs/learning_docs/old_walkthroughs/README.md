# Old walkthroughs — raw material, being replaced

These are the per-phase notes written while M0 was built (phases 0–5) plus the earlier
"whole thing" overview. They are kept only as raw material for the new learning docs,
which are organised by system part (see `../00_how_to_understand_this_project.md`, §8).
Each file is deleted once the new doc covering it is written.

**Known inaccuracies — do not learn these from here:**

| File | Says | Actually |
|---|---|---|
| `00_the_whole_thing.md`, `phase_05.md` | The checker compares every number in the answer and throws the answer away; "regenerate once, then abstain" | No regenerate step exists. Number answers are written by code; numbers inside AI-written prose are not checked |
| `00_the_whole_thing.md` | "Exactly one place calls a language model" | Two: answer writing (`generate.py`) and press-release extraction (`headline.py`) |
| `00_the_whole_thing.md` | Search scores measured on 60 questions | Measured on the 26 questions that have gold passages |
| `phase_03.md` | The 60 questions are "frozen" | Not frozen until M0 sign-off |
| `phase_04.md` | The AI fills in the query templates / picks the metric name | No AI in the numbers lane: keyword rules pick the metric and period |
| `phase_05.md` | For text questions the AI writes the answer | The AI is off by default; you get pointers to the passages |
| `phase_02.md` | "One parse of a filing fans out to both stores" | Numbers come from the SEC's JSON file; only text comes from parsing the filing |
| `00_the_whole_thing.md`, `phase_05.md` | Router scores 100% | True, but against labels derived by a helper in the gate script, not human labels |

| Old file | Replaced by |
|---|---|
| `00_the_whole_thing.md` | `00_how_to_understand_this_project.md` (done) + 01 |
| `phase_00.md`, `phase_01.md` | 02 The store (+ parts of 07) |
| `phase_02.md` | 01 The raw material, 03 Getting data in |
| `phase_03.md` | 05 The words lane, 07 Measuring it |
| `phase_04.md` | 04 The numbers lane |
| `phase_05.md` | 06 Answering |
