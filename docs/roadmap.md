# Roadmap and Open Decisions

This page separates implemented behavior from work that requires product and operational decisions.

## Implemented in V3

- Persistent SQLite storage for user accounts, tasks, manager evaluations, HR reviews, correction requests, sessions, and audit events.
- Admin, manager, employee, and HR roles with server-side role and reporting-line checks.
- Manager task assignment, narrative ratings and sharing; employee task updates and correction requests; manager resolution; independent HR grades and dispositions.
- Browser-based desktop client delivered from the server as a PWA.

## Candidate next steps

1. Pilot with synthetic data; record usability issues and acceptance checklist results.
2. Select production identity approach: MFA/SSO, password policy, recovery process, and account provisioning.
3. Decide scale, availability, and database requirements; assess managed PostgreSQL and migration plan if multiple hosts or higher concurrency are required.
4. Approve retention, deletion, employee notice, correction, and access-review policies.
5. Add organization-approved notifications and HR-system integration only after defining data ownership and consent/access rules.
6. Add operational monitoring, structured logs, security review, and tested disaster recovery.

## Decisions needed from the organization

- Expected concurrent users, availability target, hosting environment, and support owner.
- Approved identity provider and account lifecycle process.
- Retention period and who can approve record deletion or correction.
- Which HR evaluation workflow and categories should be configured, if any.
- Supported desktop browsers, endpoint deployment method, and update cadence.
- Data export and reporting requirements.

No HR integration, automated performance decision, notification delivery, SSO/MFA, or automated retention is included in the current implementation.
