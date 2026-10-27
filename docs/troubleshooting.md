# Troubleshooting

## Page does not load

- Confirm the server process is running and inspect its terminal output.
- Confirm the configured address and port; defaults are `127.0.0.1:8765`.
- If a firewall or reverse proxy is used, verify its listener and route to the configured server port.
- The app is a PWA and requires HTTPS for installation on other desktops; localhost is allowed for local development.

## Login fails

- Confirm username spelling and that the account is active.
- An administrator can issue a temporary password; the user must change it at next login.
- If this is the first run, create the initial administrator using the setup screen.
- If the app loads but reports a workspace loading error after login, check the server terminal for the failed API request and confirm the database is writable.

## Data seems missing

- Verify `WORKLOG_DB_PATH` and service working directory; a different path creates a different database.
- Confirm the service account has read/write access to the database directory.
- Do not delete or replace the database while troubleshooting. Take a backup before any recovery action.

## Desktop install option missing

- Ensure the app is served through HTTPS and has loaded successfully at least once.
- Use the browser's Install app option or create a desktop shortcut from the browser menu. Installation steps differ by browser and organizational policy.

## Port already in use

- Check whether another Worklog server is already running. Stop only the intended process or choose a different `WORKLOG_PORT`; update the reverse proxy accordingly.
