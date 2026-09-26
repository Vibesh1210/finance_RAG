# ADR-0008: Zero-cost LLM policy: Gemini free tier replaces the Anthropic API

| | |
|---|---|
| **Status** | Accepted (amended same day) |
| **Date** | 2026-07-19 |
| **Type** | Architecture |

## Context

The design names the Anthropic API for model calls (press-release extraction now, answer writing from Phase 5). The user asked for zero API cost.

## Decision

Model calls use the Gemini API (`google-genai`, `GEMINI_API_KEY`, free tier). Amended the same day: the free tier allowed only 20 requests/day for `gemini-2.5-flash`, so `GEMINI_MODEL` was switched to `gemini-2.5-flash-lite`, which has a larger daily quota.

## Consequences

Safe for extraction because its quality is not load-bearing: a fail-closed normaliser and 100% human verification catch any model's mistakes. Inputs are public SEC filings, so the free tier's data terms are a non-issue. Future model call sites default to the free tier; revisit if a gate shows quality is insufficient. Extraction is resumable if a daily quota runs out.
