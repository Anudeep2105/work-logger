# Desktop client installation

## Client model

The desktop client is an installable Progressive Web App, not a separate role-specific executable. All roles install the same client from the organization server; the authenticated account determines permissions.

## Install on Windows

1. Open the organization HTTPS Worklog URL in Microsoft Edge or Google Chrome.
2. Sign in with the administrator-provided account; change a temporary password when prompted.
3. Select **Install desktop app**, or use Edge **Apps → Install this site as an app** / Chrome **Save and share → Install page as app**.
4. Launch from Start or desktop shortcut. Sign out on shared computers.

Install from HTTPS. Localhost is for local development only. Do not open `index.html` from disk: the client needs the API and service worker on the same origin.

The app requires a network connection. Its service worker caches interface assets only; tasks, feedback, grades, and sessions stay on the server. After the administrator updates client files, close/reopen or reload the PWA.

## Roles

Employee sees own tasks and shared feedback. Manager sees direct reports and can manage tasks/feedback. HR sees shared feedback and reviews it. Admin manages profiles and audit. Installation does not grant an account or access.
