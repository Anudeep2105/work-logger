# Operations

## Start and stop

For a local demonstration, run `Start_Worklog.bat` or `python -u server.py` from the project folder. The process must remain running. Stop it with Ctrl+C in its terminal. The default bind address is loopback (`127.0.0.1`) and port `8765`; configure the reverse proxy and host environment deliberately for managed network access.

## Backups and recovery

1. Define an approved backup schedule and retention window before storing employee data.
2. Use SQLite's online backup mechanism or stop the service before copying the database.
3. Store encrypted backups with access limited to designated administrators.
4. Periodically restore a backup to a separate test location and verify login and sample records.
5. Record who performed backup and restore operations.

The app does not create backups automatically. Do not include the database, passwords, or session data in source-control commits or distributable archives.

## Updates

Back up the database first. Stage the new application files, preserve the configured database path, stop the existing service, replace code, start the service, and perform the manual smoke checks in [acceptance checklist](acceptance-checklist.md). Keep a recoverable copy of the previous application version and database backup until the update is accepted.

## Monitoring and incident handling

The current service has no centralized monitoring or alerting. Operators should monitor process availability, disk space, database access, reverse-proxy TLS, and backup success using organization-approved tools. For suspected account compromise, disable the account, preserve relevant audit and proxy logs, rotate credentials, and follow the organization's incident process.
