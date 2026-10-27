# Server installation

## Requirements

Python 3.10+; no third-party Python packages; persistent writable database directory; HTTPS proxy and organization DNS for remote desktops; approved backup owner and location.

## Windows Server

1. Extract `Worklog_Server_Version.zip` to a controlled staging folder.
2. Install Python 3.10+ and verify `python` is available.
3. Review hostname, service identity, database directory, and backup/security plan.
4. Run `Install_Worklog_Server.ps1` in elevated PowerShell. It copies the package to `%ProgramData%\\Worklog`, registers a Task Scheduler startup task as SYSTEM, and starts it.
5. Configure HTTPS reverse proxy from the organization hostname to `127.0.0.1:8765`. Do not expose port 8765 directly.
6. Open the HTTPS site, create the first Admin, then create roles and manager relationships.

For a temporary foreground run, use `Start_Worklog_Server.bat`; keep its window open.

## Linux

Install Python 3, create a restricted `worklog` service account, extract to `/opt/worklog`, and grant that account write access to `/opt/worklog/data`. Review `systemd/worklog.service`, install as `/etc/systemd/system/worklog.service`, then run `systemctl daemon-reload` and `systemctl enable --now worklog`. Configure HTTPS proxy to loopback.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `WORKLOG_HOST` | `127.0.0.1` | Listener; keep loopback behind a same-host proxy. |
| `WORKLOG_PORT` | `8765` | Listener port. |
| `WORKLOG_DB_PATH` | `<server>/data/worklog.sqlite3` | Persistent database path. |

## First Admin and health

First-admin setup is available only when there are no profiles. Choose a unique username and password of at least 12 characters. The CLI alternative is `python server.py create-admin`. `GET /api/health` returns database health; `/api/setup-status` reports setup completion.

## Client updates

The server package includes `client/`. To update the UI independently, replace those files with the contents of `Worklog_Desktop_Client_Version.zip`; keep client and API same-origin. Reload/reopen installed clients after update.
