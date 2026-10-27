# Administrator guide

## First setup

The first-admin web setup appears only when the database has no profiles. Choose a unique username and a password of at least 12 characters. The CLI alternative is `python server.py create-admin`.

## Create profiles

1. Open **User profiles** as Admin.
2. Enter full name, unique username, role, team/department, and temporary password (12+ characters).
3. Create Manager profiles before Employees; assign each Employee to a reporting Manager.
4. Give temporary credentials through an approved channel. The user must change the password at first sign-in.

Grant Admin sparingly. HR profiles do not need a reporting manager.

## Account lifecycle

- **Reset password:** set temporary password; existing sessions are revoked and user must change it at next sign-in.
- **Deactivate:** blocks future sign-in and revokes sessions; historical records remain.
- The current UI does not edit a profile’s role, team, or manager relationship after creation. Plan an admin workflow before production if those changes are required.

## Audit and recovery

Admin UI shows the latest 200 audit events. Audit retention/export policy is not automated. There is no self-service recovery email. If all Admin accounts are locked out, stop the service, create a verified DB backup, and follow an approved database recovery procedure; do not edit password hashes casually.
