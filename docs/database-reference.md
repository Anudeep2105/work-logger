# Database Reference

## Storage

Worklog uses SQLite through Python's standard `sqlite3` module. The default file is `server/data/worklog.sqlite3` (or `data/worklog.sqlite3` when running from the project root, depending on launch location). Set `WORKLOG_DB_PATH` to an absolute persistent path before starting the service. Back up the database only after stopping the service or using a consistent SQLite backup procedure.

## Tables

| Table | Purpose | Key relationships |
|---|---|---|
| `users` | Login identity, role, active state, reporting-manager link, password hash and salt | Self-reference for manager assignment |
| `sessions` | Hashed session token and expiration | User |
| `tasks` | Work assignment, owner, status, due date and performance-related flag | Employee and manager |
| `evaluations` | Manager rating, narrative, share state and correction history | Task, employee, manager |
| `hr_reviews` | Independent HR grade, note and disposition | Evaluation, employee, HR reviewer |
| `corrections` | Employee requests and manager decision/resolution | Task or evaluation, requester, resolver |
| `audit_events` | Security-relevant mutation event metadata | Actor |

Refer to `server.py` for authoritative column names, constraints, and indexes. Schema is initialized at service startup. Do not edit production database rows manually; use the application so validations and audit records apply.

## Data lifecycle

The current version does not automate retention, archival, anonymization, or deletion. The organization must define an approved retention schedule and correction/deletion workflow before using real employee records. Backups contain sensitive employee information and must receive equivalent access restrictions and retention controls.

## Development reset

For a disposable local development instance only, stop the server and move or delete its SQLite file; the next launch initializes an empty database. This permanently removes accounts and records, so never do this to a pilot or production database.
