# Historical project material

This directory preserves earlier design coursework and standalone SQL Server
experiments. It is not part of the supported Django/React application.

- `phase-1-and-2/`: original design documents and diagram.
- `phase-3/`: standalone SQL queries, CRUD scripts, and reporting experiments.

These artifacts predate the current models, migrations, authentication, and
transactional services. Do not run the historical write scripts against an
application database or treat their schemas as migration instructions. Their
local SQL Server connection defaults are examples, not deployment configuration.
Binary documents have not been exhaustively checked for personal information or
embedded metadata; review them before publishing if that is a concern.

Any locally excluded `PROJECT.md`, `TEST_INFRA.md`, or `TEST_READY.md` files in this
directory are historical agent-coordination notes. They contain outdated counts
and milestone claims and are not maintained public documentation.

For current behavior, start with the [root README](../../README.md), the
[architecture guide](../ARCHITECTURE.md), and the [audit report](../AUDIT_REPORT.md).
