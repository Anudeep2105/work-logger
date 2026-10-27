# Worklog V3

Worklog is a role-based work tracking and performance feedback application. It stores user accounts, tasks, manager feedback, employee correction requests, HR reviews, sessions, and audit events in SQLite.

## Quick start

1. Install Python 3.10 or newer.
2. Run `Start_Worklog.bat`.
3. Visit `http://127.0.0.1:8765` and create the initial administrator.
4. Create user profiles and reporting relationships.

For multi-desktop use, install the server on a managed host and publish it through HTTPS. Employees, managers, HR, and administrators install the same browser client; their server-side role controls available actions. Follow [server installation](docs/server-installation.md) and [desktop client installation](docs/desktop-client-installation.md).

## Documentation

Start at the [documentation index](docs/README.md). It links architecture, user and administrator guides, API/database references, security and privacy notes, operations, troubleshooting, acceptance checks, and the management BRD, FRD, and project plan.

## Important use boundary

Ratings and grades are human-authored decision-support records, not an automated appraisal or a sole measure of employee performance. This application does not claim legal compliance and does not provide SSO/MFA, automated retention, notifications, or HR-platform integration. Review [security and privacy](docs/security-and-privacy.md) before using real employee data.
