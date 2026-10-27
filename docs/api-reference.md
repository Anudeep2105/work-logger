# API reference

Same-origin JSON API. Authenticated routes use the `worklog_session` cookie. Mutation requests check `Origin` when supplied. API responses are `no-store`.

## Authentication

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET | `/api/health` | Public | Health and database type. |
| GET | `/api/setup-status` | Public | First-admin setup state. |
| POST | `/api/setup` | One-time | Create first Admin; rejected after a user exists. |
| POST | `/api/login` | Public | Verify credentials and create session. |
| POST | `/api/logout` | Signed in | Revoke current session. |
| GET | `/api/me` | Signed in | Return current profile. |
| POST | `/api/password` | Signed in | Change password. |

## Business routes

| Method | Path | Access | Purpose |
|---|---|---|---|
| GET/POST | `/api/users` | Admin; Manager GET sees direct reports | List/create profiles. |
| PATCH | `/api/users/{id}/active` | Admin | Activate/deactivate; revoke sessions. |
| POST | `/api/users/{id}/reset-password` | Admin | Reset temporary password; revoke sessions. |
| GET | `/api/tasks` | Scoped by role | List permitted tasks; HR sees tasks linked to shared feedback. |
| POST | `/api/tasks` | Manager/Admin | Create for direct report (Manager) or active employee (Admin). |
| PUT/PATCH | `/api/tasks/{id}` | Employee own status; Manager team; Admin all | Update task within scope. |
| GET | `/api/feedback` | Scoped by role | Manager authored; Employee shared own; HR shared; Admin all. |
| POST | `/api/feedback` | Manager | Create 1–5 rating, narrative, optional task link, optional share. |
| PUT | `/api/feedback/{id}` | Authoring Manager | Correct feedback; clears old HR review when shared. |
| POST | `/api/feedback/{id}/share` | Authoring Manager | Share draft with employee/HR. |
| POST | `/api/feedback/{id}/review` | HR | Save grade, review, and disposition for shared feedback. |
| GET/POST | `/api/corrections` | Scoped GET; Employee POST | View/create correction requests. |
| PATCH | `/api/corrections/{id}` | Manager of requester/Admin | Accept/decline with resolution note. |
| POST | `/api/import-tasks` | Admin | Import up to 5,000 V1/V2 backup tasks by unique employee name/team. |
| GET | `/api/audit` | Admin | Recent audit events. |

## Error responses

- `400`: invalid request; includes `error` message.
- `401`: missing/expired session.
- `403`: authenticated user lacks role/scope permission.
- `409`: database uniqueness/constraint conflict.
- `500`: unexpected error; details are server-side only.

No OpenAPI document, pagination, API version prefix, rate limiting, or request IDs are implemented yet.
