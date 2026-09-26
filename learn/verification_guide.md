# Verification guide — the human checklist

> Everything below is a **read-and-confirm** task. For each number: open the filing at the link, find the line in the named statement, and check the **as-reported** figure matches. You do **not** need finance training — just careful reading.

## Before you start — two things to know

1. **Scale.** Filings print numbers in *millions* (a header says `$ in millions`). So the filing shows `416,161` and the system stores `416,161,000,000` — same number, six zeros of scale. This guide shows the **as-reported** form (e.g. `$416,161 million`) so you just match the digits `416,161`.

2. **Where numbers live.** Revenue / net income / EPS → the **income statement**. Total assets → the **balance sheet**. Both are in the 10-K, a bit past the halfway point (look for 'Consolidated Statements of…'). Tick `[x]` as you confirm each.

If a number does **not** match, that's a real finding — note it and stop; it means a data-loading bug the whole system depends on catching.

---

## Part 1 — Company numbers (satisfies the spot-checks, golden bank & execution_v0)

For each company, open its two 10-Ks and confirm the figures. Verifying these covers the overlapping number-checks across all three banks.

### Apple (AAPL)

**FY2025 10-K** — [0000320193-25-000079](https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$416,161 million** | `416161000000` | Income statement |
| [ ] | Net income | **$112,010 million** | `112010000000` | Income statement |
| [ ] | Diluted EPS | **$7.46 per share** | `7.46` | Income statement |
| [ ] | Total assets | **$359,241 million** | `359241000000` | Balance sheet |

**FY2024 10-K** — [0000320193-24-000123](https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$391,035 million** | `391035000000` | Income statement |
| [ ] | Net income | **$93,736 million** | `93736000000` | Income statement |
| [ ] | Diluted EPS | **$6.08 per share** | `6.08` | Income statement |
| [ ] | Total assets | **$364,980 million** | `364980000000` | Balance sheet |

### Caterpillar (CAT)

**FY2025 10-K** — [0000018230-26-000008](https://www.sec.gov/Archives/edgar/data/18230/000001823026000008/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$67,589 million** | `67589000000` | Income statement |
| [ ] | Diluted EPS | **$18.81 per share** | `18.81` | Income statement |
| [ ] | Total assets | **$98,585 million** | `98585000000` | Balance sheet |

**FY2024 10-K** — [0000018230-25-000008](https://www.sec.gov/Archives/edgar/data/18230/000001823025000008/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$64,809 million** | `64809000000` | Income statement |
| [ ] | Diluted EPS | **$22.05 per share** | `22.05` | Income statement |
| [ ] | Total assets | **$87,764 million** | `87764000000` | Balance sheet |

### Costco (COST)

**FY2025 10-K** — [0000909832-25-000101](https://www.sec.gov/Archives/edgar/data/909832/000090983225000101/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$275,235 million** | `275235000000` | Income statement |
| [ ] | Net income | **$8,099 million** | `8099000000` | Income statement |
| [ ] | Diluted EPS | **$18.21 per share** | `18.21` | Income statement |
| [ ] | Total assets | **$77,099 million** | `77099000000` | Balance sheet |

**FY2024 10-K** — [0000909832-24-000049](https://www.sec.gov/Archives/edgar/data/909832/000090983224000049/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$254,453 million** | `254453000000` | Income statement |
| [ ] | Net income | **$7,367 million** | `7367000000` | Income statement |
| [ ] | Diluted EPS | **$16.56 per share** | `16.56` | Income statement |
| [ ] | Total assets | **$69,831 million** | `69831000000` | Balance sheet |

### Deere (DE)

**FY2025 10-K** — [0001104659-25-122321](https://www.sec.gov/Archives/edgar/data/315189/000110465925122321/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$45,684 million** | `45684000000` | Income statement |
| [ ] | Net income | **$5,027 million** | `5027000000` | Income statement |
| [ ] | Diluted EPS | **$18.5 per share** | `18.5` | Income statement |
| [ ] | Total assets | **$105,996 million** | `105996000000` | Balance sheet |

**FY2024 10-K** — [0001558370-24-016169](https://www.sec.gov/Archives/edgar/data/315189/000155837024016169/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$51,716 million** | `51716000000` | Income statement |
| [ ] | Net income | **$7,100 million** | `7100000000` | Income statement |
| [ ] | Diluted EPS | **$25.62 per share** | `25.62` | Income statement |
| [ ] | Total assets | **$107,320 million** | `107320000000` | Balance sheet |

### Johnson & Johnson (JNJ)

**FY2025 10-K** — [0000200406-26-000016](https://www.sec.gov/Archives/edgar/data/200406/000020040626000016/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$94,193 million** | `94193000000` | Income statement |
| [ ] | Net income | **$26,804 million** | `26804000000` | Income statement |
| [ ] | Diluted EPS | **$11.03 per share** | `11.03` | Income statement |
| [ ] | Total assets | **$199,210 million** | `199210000000` | Balance sheet |

**FY2024 10-K** — [0000200406-25-000038](https://www.sec.gov/Archives/edgar/data/200406/000020040625000038/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$88,821 million** | `88821000000` | Income statement |
| [ ] | Net income | **$14,066 million** | `14066000000` | Income statement |
| [ ] | Diluted EPS | **$5.79 per share** | `5.79` | Income statement |
| [ ] | Total assets | **$180,104 million** | `180104000000` | Balance sheet |

### JPMorgan Chase (JPM)

**FY2025 10-K** — [0001628280-26-008131](https://www.sec.gov/Archives/edgar/data/19617/000162828026008131/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$182,447 million** | `182447000000` | Income statement |
| [ ] | Net income | **$57,048 million** | `57048000000` | Income statement |
| [ ] | Diluted EPS | **$20.02 per share** | `20.02` | Income statement |
| [ ] | Total assets | **$4,424,900 million** | `4424900000000` | Balance sheet |

**FY2024 10-K** — [0000019617-25-000270](https://www.sec.gov/Archives/edgar/data/19617/000001961725000270/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$177,556 million** | `177556000000` | Income statement |
| [ ] | Net income | **$58,471 million** | `58471000000` | Income statement |
| [ ] | Diluted EPS | **$19.75 per share** | `19.75` | Income statement |
| [ ] | Total assets | **$4,002,814 million** | `4002814000000` | Balance sheet |

> **JPMorgan note:** it's a bank — it has **no gross profit / gross margin**. The system abstains on those on purpose. Confirm you *can't* find a 'gross profit' line in JPM's filing (banks report 'total net revenue' instead). That abstention is correct behaviour.

### Microsoft (MSFT)

**FY2025 10-K** — [0000950170-25-100235](https://www.sec.gov/Archives/edgar/data/789019/000095017025100235/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$281,724 million** | `281724000000` | Income statement |
| [ ] | Net income | **$101,832 million** | `101832000000` | Income statement |
| [ ] | Diluted EPS | **$13.64 per share** | `13.64` | Income statement |
| [ ] | Total assets | **$619,003 million** | `619003000000` | Balance sheet |

**FY2024 10-K** — [0000950170-24-087843](https://www.sec.gov/Archives/edgar/data/789019/000095017024087843/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$245,122 million** | `245122000000` | Income statement |
| [ ] | Net income | **$88,136 million** | `88136000000` | Income statement |
| [ ] | Diluted EPS | **$11.8 per share** | `11.8` | Income statement |
| [ ] | Total assets | **$512,163 million** | `512163000000` | Balance sheet |

### NVIDIA (NVDA)

**FY2025 10-K** — [0001045810-25-000023](https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$130,497 million** | `130497000000` | Income statement |
| [ ] | Net income | **$72,880 million** | `72880000000` | Income statement |
| [ ] | Diluted EPS | **$2.94 per share** | `2.94` | Income statement |
| [ ] | Total assets | **$111,601 million** | `111601000000` | Balance sheet |

**FY2024 10-K** — [0001045810-24-000029](https://www.sec.gov/Archives/edgar/data/1045810/000104581024000029/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$60,922 million** | `60922000000` | Income statement |
| [ ] | Net income | **$29,760 million** | `29760000000` | Income statement |
| [ ] | Diluted EPS | **$1.19 per share** | `1.19` | Income statement |
| [ ] | Total assets | **$65,728 million** | `65728000000` | Balance sheet |

### Walmart (WMT)

**FY2025 10-K** — [0000104169-25-000021](https://www.sec.gov/Archives/edgar/data/104169/000010416925000021/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$680,985 million** | `680985000000` | Income statement |
| [ ] | Net income | **$19,436 million** | `19436000000` | Income statement |
| [ ] | Diluted EPS | **$2.41 per share** | `2.41` | Income statement |
| [ ] | Total assets | **$260,823 million** | `260823000000` | Balance sheet |

**FY2024 10-K** — [0000104169-24-000056](https://www.sec.gov/Archives/edgar/data/104169/000010416924000056/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$648,125 million** | `648125000000` | Income statement |
| [ ] | Net income | **$15,511 million** | `15511000000` | Income statement |
| [ ] | Diluted EPS | **$1.91 per share** | `1.91` | Income statement |
| [ ] | Total assets | **$252,399 million** | `252399000000` | Balance sheet |

### ExxonMobil (XOM)

**FY2025 10-K** — [0000034088-26-000045](https://www.sec.gov/Archives/edgar/data/34088/000003408826000045/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$332,238 million** | `332238000000` | Income statement |
| [ ] | Net income | **$28,844 million** | `28844000000` | Income statement |
| [ ] | Diluted EPS | **$6.7 per share** | `6.7` | Income statement |
| [ ] | Total assets | **$448,980 million** | `448980000000` | Balance sheet |

**FY2024 10-K** — [0000034088-25-000010](https://www.sec.gov/Archives/edgar/data/34088/000003408825000010/) &nbsp; (Income statement (Consolidated Statements of Operations); balance sheet for assets)

| ✔ | Metric | As reported (match this) | System stored | Where |
|---|--------|--------------------------|---------------|-------|
| [ ] | Revenue | **$349,585 million** | `349585000000` | Income statement |
| [ ] | Net income | **$33,680 million** | `33680000000` | Income statement |
| [ ] | Diluted EPS | **$7.84 per share** | `7.84` | Income statement |
| [ ] | Total assets | **$453,475 million** | `453475000000` | Balance sheet |

---

## Part 2 — Early-earnings (preliminary) figures — AAPL, CAT, COST only

These come from the quarterly **earnings press releases** (8-K, Exhibit 99.1) — the numbers a company announces *before* the full filing. Each row includes the exact **quote** from the release, so you just confirm the number appears as shown. (63 rows; other companies weren't extracted — Gemini free-tier quota, DECISIONS #8.)

### Apple (AAPL) — 24 figures across 8 releases

| ✔ | Quarter | Metric | As reported | Source quote from the release | 8-K |
|---|---------|--------|-------------|-------------------------------|-----|
| [ ] | FY2024 Q1 | diluted_eps | $2.18 | "Diluted $ 2.18 $ 1.88" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019324000005/) |
| [ ] | FY2024 Q1 | net_income | $33,916 million | "Net income $ 33,916 $ 29,998" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019324000005/) |
| [ ] | FY2024 Q1 | revenue | $119,575 million | "Total net sales (1) 119,575 117,154" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019324000005/) |
| [ ] | FY2024 Q2 | diluted_eps | $1.53 | "Diluted $ 1.53 $ 1.52 $ 3.71 $ 3.41" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019324000067/) |
| [ ] | FY2024 Q2 | net_income | $23,636 million | "Net income $ 23,636 $ 24,160 $ 57,552 $ 54,158" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019324000067/) |
| [ ] | FY2024 Q2 | revenue | $90.8 billion | "The Company posted quarterly revenue of $90.8 billion, down 4 percent " | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019324000067/) |
| [ ] | FY2024 Q3 | diluted_eps | $1.40 | "Diluted $1.40 $1.26 $5.11 $4.67" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019324000080/) |
| [ ] | FY2024 Q3 | net_income | $21,448 | "Net income $21,448 $19,881 $79,000 $74,039" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019324000080/) |
| [ ] | FY2024 Q3 | revenue | $85,777 | "Total net sales (1) 85,777 81,797 296,105 293,787" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019324000080/) |
| [ ] | FY2024 Q4 | diluted_eps | $0.97 | "Diluted $ 0.97 $ 1.46 $ 6.08 $ 6.13" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019324000120/) |
| [ ] | FY2024 Q4 | net_income | $14,736 million | "Net income $ 14,736 $ 22,956 $ 93,736 $ 96,995" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019324000120/) |
| [ ] | FY2024 Q4 | revenue | $94.9 billion | "The Company posted quarterly revenue of $94.9 billion, up 6 percent ye" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019324000120/) |
| [ ] | FY2025 Q1 | diluted_eps | $2.40 | "The Company posted quarterly revenue of $124.3 billion, up 4 percent y" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019325000007/) |
| [ ] | FY2025 Q1 | net_income | $36,330 million | "Net income $ 36,330 $ 33,916" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019325000007/) |
| [ ] | FY2025 Q1 | revenue | $124.3 billion | "The Company posted quarterly revenue of $124.3 billion, up 4 percent y" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019325000007/) |
| [ ] | FY2025 Q2 | diluted_eps | $1.65 | "Diluted $1.65 $1.53 $4.05 $3.71" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019325000055/) |
| [ ] | FY2025 Q2 | net_income | $24,780 | "Net income $24,780 $23,636 $61,110 $57,552" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019325000055/) |
| [ ] | FY2025 Q2 | revenue | $95,359 | "Total net sales $95,359 $90,753 $219,659 $210,328" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019325000055/) |
| [ ] | FY2025 Q3 | diluted_eps | $1.57 | "Diluted $ 1.57 $ 1.40 $ 5.62 $ 5.11" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019325000071/) |
| [ ] | FY2025 Q3 | net_income | $23,434 million | "Net income $ 23,434 $ 21,448 $ 84,544 $ 79,000" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019325000071/) |
| [ ] | FY2025 Q3 | revenue | $94,036 million | "Total net sales $ 94,036 $ 85,777 $ 313,695 $ 296,105" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019325000071/) |
| [ ] | FY2025 Q4 | diluted_eps | $1.85 | "Diluted $ 1.85 $ 0.97 $ 7.46 $ 6.08" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019325000077/) |
| [ ] | FY2025 Q4 | net_income | $27,466 million | "Net income $ 27,466 $ 14,736 $ 112,010 $ 93,736" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019325000077/) |
| [ ] | FY2025 Q4 | revenue | $102.5 billion | "The Company posted quarterly revenue of $102.5 billion, up 8 percent y" | [8-K](https://www.sec.gov/Archives/edgar/data/320193/000032019325000077/) |

### Caterpillar (CAT) — 12 figures across 8 releases (+15 rows had no extracted value — skip; extraction gaps)

| ✔ | Quarter | Metric | As reported | Source quote from the release | 8-K |
|---|---------|--------|-------------|-------------------------------|-----|
| [ ] | FY2024 Q1 | diluted_eps | $5.75 | "Three Months Ended March 31, 2024 - U.S. GAAP $ 3,519 22.3 % $ 3,532 $" | [8-K](https://www.sec.gov/Archives/edgar/data/18230/000001823024000016/) |
| [ ] | FY2024 Q1 | net_income | $2,856 million | "Three Months Ended March 31, 2024 - U.S. GAAP $ 3,519 22.3 % $ 3,532 $" | [8-K](https://www.sec.gov/Archives/edgar/data/18230/000001823024000016/) |
| [ ] | FY2024 Q1 | revenue | $15.8 billion | "Sales and revenues for the first quarter of 2024 were $15.8 billion, a" | [8-K](https://www.sec.gov/Archives/edgar/data/18230/000001823024000016/) |
| [ ] | FY2024 Q2 | revenue | $16.7 billion | "Sales and revenues for the second quarter of 2024 were $16.7 billion, " | [8-K](https://www.sec.gov/Archives/edgar/data/18230/000001823024000042/) |
| [ ] | FY2024 Q3 | diluted_eps | 5.06 | "Three Months Ended September 30, 2024 - U.S. GAAP $ 3,147 19.5 % $ 3,0" | [8-K](https://www.sec.gov/Archives/edgar/data/18230/000001823024000050/) |
| [ ] | FY2024 Q3 | net_income | $2,464 million | "Three Months Ended September 30, 2024 - U.S. GAAP $ 3,147 19.5 % $ 3,0" | [8-K](https://www.sec.gov/Archives/edgar/data/18230/000001823024000050/) |
| [ ] | FY2024 Q3 | revenue | $16.1 billion | "Sales and revenues for the third quarter of 2024 were $16.1 billion, a" | [8-K](https://www.sec.gov/Archives/edgar/data/18230/000001823024000050/) |
| [ ] | FY2024 Q4 | revenue | $16.2 billion | "● Fourth-quarter 2024 sales and revenues were $16.2 billion; full-year" | [8-K](https://www.sec.gov/Archives/edgar/data/18230/000001823025000004/) |
| [ ] | FY2025 Q1 | revenue | $14.2 billion | "Sales and revenues for the first quarter of 2025 were $14.2 billion, a" | [8-K](https://www.sec.gov/Archives/edgar/data/18230/000001823025000013/) |
| [ ] | FY2025 Q2 | revenue | $16.569 billion | "Total sales and revenues for the second quarter of 2025 were $16.569 b" | [8-K](https://www.sec.gov/Archives/edgar/data/18230/000001823025000037/) |
| [ ] | FY2025 Q3 | revenue | $17.6 billion | "Sales and revenues for the third quarter of 2025 were $17.6 billion, a" | [8-K](https://www.sec.gov/Archives/edgar/data/18230/000001823025000043/) |
| [ ] | FY2025 Q4 | revenue | $19.1 billion | "● Fourth-quarter 2025 sales and revenues were $19.1 billion; full-year" | [8-K](https://www.sec.gov/Archives/edgar/data/18230/000001823026000003/) |

### Costco (COST) — 12 figures across 4 releases

| ✔ | Quarter | Metric | As reported | Source quote from the release | 8-K |
|---|---------|--------|-------------|-------------------------------|-----|
| [ ] | FY2024 Q1 | diluted_eps | 3.58 | "Diluted $3.58 $3.07" | [8-K](https://www.sec.gov/Archives/edgar/data/909832/000090983223000062/) |
| [ ] | FY2024 Q1 | net_income | 1,589 | "NET INCOME $1,589 $1,364" | [8-K](https://www.sec.gov/Archives/edgar/data/909832/000090983223000062/) |
| [ ] | FY2024 Q1 | revenue | 57,799 | "Total revenue 57,799 54,437" | [8-K](https://www.sec.gov/Archives/edgar/data/909832/000090983223000062/) |
| [ ] | FY2024 Q2 | diluted_eps | 3.92 | "Diluted $ 3.92 $ 3.30 $ 7.49 $ 6.37" | [8-K](https://www.sec.gov/Archives/edgar/data/909832/000090983224000012/) |
| [ ] | FY2024 Q2 | net_income | 1,743 | "NET INCOME $ 1,743 $ 1,466 $ 3,332 $ 2,830" | [8-K](https://www.sec.gov/Archives/edgar/data/909832/000090983224000012/) |
| [ ] | FY2024 Q2 | revenue | 58,442 | "Total revenue 58,442 55,266 116,241 109,703" | [8-K](https://www.sec.gov/Archives/edgar/data/909832/000090983224000012/) |
| [ ] | FY2024 Q3 | diluted_eps | $3.78 | "Diluted $ 3.78 $ 2.93 $ 11.27 $ 9.30" | [8-K](https://www.sec.gov/Archives/edgar/data/909832/000090983224000026/) |
| [ ] | FY2024 Q3 | net_income | $1,681 | "NET INCOME $ 1,681 $ 1,302 $ 5,013 $ 4,132" | [8-K](https://www.sec.gov/Archives/edgar/data/909832/000090983224000026/) |
| [ ] | FY2024 Q3 | revenue | $58,515 | "Total revenue $ 58,515 $ 53,648 $ 174,756 $ 163,351" | [8-K](https://www.sec.gov/Archives/edgar/data/909832/000090983224000026/) |
| [ ] | FY2024 Q4 | diluted_eps | $5.29 | "Diluted $ 5.29 $ 4.86 $ 16.56 $ 14.16" | [8-K](https://www.sec.gov/Archives/edgar/data/909832/000090983224000043/) |
| [ ] | FY2024 Q4 | net_income | $2,354 million | "NET INCOME $ 2,354 $ 2,160 $ 7,367 $ 6,292" | [8-K](https://www.sec.gov/Archives/edgar/data/909832/000090983224000043/) |
| [ ] | FY2024 Q4 | revenue | $79,697 million | "Total revenue 79,697 78,939 254,453 242,290" | [8-K](https://www.sec.gov/Archives/edgar/data/909832/000090983224000043/) |

---

## Part 3 — Metric registry review (~15 min, a little judgment)

Confirm each metric points at the right filing line. Most are obvious; the JPMorgan rows are the ones that matter. File: `fixtures/metric_mappings.yaml`.

| ✔ | Metric | Company | Filing tag / behaviour | Confirm |
|---|--------|---------|------------------------|---------|
| [ ] | revenue | (default) | Revenues | right line item? |
| [ ] | revenue | AAPL | RevenueFromContractWithCustomerExcludingAssessedTax | right line item? |
| [ ] | revenue | MSFT | RevenueFromContractWithCustomerExcludingAssessedTax | right line item? |
| [ ] | revenue | JNJ | RevenueFromContractWithCustomerExcludingAssessedTax | right line item? |
| [ ] | revenue | JPM | Revenues | 'total net revenue' — flagged not-comparable (correct) |
| [ ] | net_income | (default) | NetIncomeLoss | right line item? |
| [ ] | diluted_eps | (default) | EarningsPerShareDiluted | right line item? |
| [ ] | operating_income | (default) | OperatingIncomeLoss | right line item? |
| [ ] | gross_profit | (default) | GrossProfit | right line item? |
| [ ] | gross_profit | JPM | **ABSTAIN** (no such thing for this company) | bank has no gross profit/cost of revenue — **abstain is correct** |
| [ ] | cost_of_revenue | (default) | CostOfGoodsAndServicesSold | right line item? |
| [ ] | cost_of_revenue | JPM | **ABSTAIN** (no such thing for this company) | bank has no gross profit/cost of revenue — **abstain is correct** |
| [ ] | operating_cash_flow | (default) | NetCashProvidedByUsedInOperatingActivities | right line item? |
| [ ] | capital_expenditure | (default) | PaymentsToAcquirePropertyPlantAndEquipment | right line item? |
| [ ] | total_assets | (default) | Assets | right line item? |
| [ ] | total_liabilities | (default) | Liabilities | right line item? |
| [ ] | stockholders_equity | (default) | StockholdersEquity | right line item? |
| [ ] | cash_and_equivalents | (default) | CashAndCashEquivalentsAtCarryingValue | right line item? |

---

## Part 4 — The Johnson & Johnson restatement (1 case, ~5 min)

Johnson & Johnson spun off its consumer-health business (**Kenvue**). Afterwards it **restated** its earlier revenue to remove that business. So the *same* period has two correct numbers depending on when you ask. Confirm both, then set `human_countersigned: true` in `fixtures/supersession_confirmed.json`.

- **As first reported** (H1 2023): $50,276 million — [0000200406-23-000082](https://www.sec.gov/Archives/edgar/data/200406/000020040623000082/)
- **As restated** (in the 2024 filing): $42,413 million — [0000200406-24-000075](https://www.sec.gov/Archives/edgar/data/200406/000020040624000075/)
- Confirm: the later filing shows the **lower** number (consumer health moved out).

---

## Part 5 — Golden-bank text & 'should-refuse' questions (~15 min, no numbers)

File: `golden/factual_v0.yaml`. Two quick confirmations:

**(a) 26 'find the passage' questions** — for a sample, confirm the cited section (e.g. 'Item 1A' = Risk Factors, 'Item 7' = management discussion) is where that answer would live. You don't read the whole thing — just sanity-check the section is right.

**(b) 14 'should refuse' questions** — confirm each is genuinely unanswerable or ambiguous given our data (we have no analyst targets, no intraday prices, no Tesla, etc.):

- [ ] `F21` — *Compare JPMorgan's gross margin to Apple's for fiscal 2025.* → should **clarify**
- [ ] `F22` — *Compare ExxonMobil's revenue to Chevron's for fiscal 2024.* → should **clarify**
- [ ] `F29` — *Which of Walmart's suppliers also supply Costco?* → should **typed_refusal**
- [ ] `F30` — *How is Caterpillar exposed to the same component suppliers as Deere?* → should **typed_refusal**
- [ ] `F31` — *What is NVIDIA's revenue concentration among its largest hyperscaler customers?* → should **typed_refusal**
- [ ] `F32` — *Trace the supply-chain relationship between Apple and its key component vendors.* → should **typed_refusal**
- [ ] `F33` — *What is Apple's CUSIP number?* → should **abstain**
- [ ] `F34` — *What was NVIDIA's stock price at 2 p.m. yesterday?* → should **abstain**
- [ ] `F35` — *What is the current analyst price target for Microsoft?* → should **abstain**
- [ ] `F36` — *What did Apple's CEO say during the analyst Q&A on the last earnings call?* → should **abstain**
- [ ] `F37` — *What was Apple's revenue specifically in Germany in fiscal 2025?* → should **abstain**
- [ ] `F38` — *What was Tesla's revenue for fiscal year 2025?* → should **abstain**
- [ ] `F39` — *What was Apple's Q3 2024 revenue?* → should **clarify**
- [ ] `F40` — *Compare NVIDIA's and Apple's third-quarter revenue.* → should **clarify**

---

## Part 6 — The one key (not verification)

- [ ] Get a free API key at **tiingo.com**, put it in `.env` as `TIINGO_API_KEY`. Then tell me — I run the price backfill and it unblocks the last Phase 2 gate check.


---

## Part 7 — How to work through this, and what happens when you're done

**Pace.** Part 1 is one company per sitting (30–45 min each, 10 sittings). Parts 2–5 are
short. Tick `[x]` as you go — the ticks in this file are the record; nothing else to fill in.

**If a number doesn't match:** don't change anything. Write the value you see next to the
row, note the filing and page, and tell me. One real mismatch matters more than fifty
matches — it means a loading bug the whole system depends on catching.

**When every box is ticked, tell me.** Then I:
1. fill `fixtures/spot_checks.json` (from the template) with the Part 1 figures you confirmed;
2. load the Part 2 rows into the database as `human_verified=true`;
3. confirm the Part 4 countersign is set, and run the price backfill with your Tiingo key;
4. re-run `make gates` — phases 2 and 3 should go fully green;
5. record the first **frozen baselines** in `golden/thresholds.yaml` and mark the golden
   bank frozen;
6. update `STATUS.md`, commit, and tag **`v0.1.0`**.

From that point every "did it improve?" number in the plan is measured against answers
*you* confirmed — that's what makes the rest of the roadmap mean something.
