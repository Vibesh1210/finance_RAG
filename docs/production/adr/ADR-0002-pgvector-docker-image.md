# ADR-0002: Use the `pgvector/pgvector:pg16` image for Postgres

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-10 |
| **Type** | Architecture |

## Context

Pin U12 says "postgres:16 + pgvector". The stock `postgres:16` image does not ship the pgvector extension.

## Decision

Use the official `pgvector/pgvector:pg16` image (postgres 16 with the extension compiled in) instead of building a custom image. The extension is enabled at first start by `db/init/01_extensions.sql`; CI enables it with an explicit `psql` step because CI service containers cannot mount the repo.

## Consequences

No custom image to maintain. Local and CI databases are identical apart from how the extension is switched on.
