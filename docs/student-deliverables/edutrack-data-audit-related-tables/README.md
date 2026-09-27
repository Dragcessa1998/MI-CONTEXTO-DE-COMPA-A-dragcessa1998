# EduTrack Data Audit — Related Tables

This deliverable implements the 4Geeks project criteria for the normalized EduTrack
schema.

## Files

- `edutrack_v2.sql` — official schema and seed data used for the audit.
- `queries.sql` — ten JOIN-based queries, including INNER JOIN, LEFT JOIN,
  `GROUP BY`/`HAVING`, revenue, and foreign-key integrity checks.
- `analysis_report.md` — results and operational conclusions for every query.
- `diagram.png` — entity relationship diagram for `students`, `courses`, and
  `enrollments`.

## Validation

The schema was loaded into an in-memory SQLite database and all ten queries were
executed successfully. The query counts are Q1 16, Q2 6, Q3 4, Q4 1, Q5 1, Q6 7,
Q7 4, Q8 4, Q9 0, and Q10 0. PostgreSQL/Supabase syntax is preserved (`TRUE`,
`ROUND`, and standard JOIN clauses).

Every query contains at least one JOIN and no query uses a subquery, matching the
project constraint.
