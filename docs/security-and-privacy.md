# Security and Privacy

## Current controls

- Passwords use salted PBKDF2-HMAC-SHA256 hashes; plaintext passwords are not stored.
- Session tokens are random, stored as hashes, carried in HttpOnly and SameSite cookies, and expire after one day.
- API authorization is enforced by role and, for managers, direct-report relationships.
- Same-origin validation applies to mutating requests; input validation is performed server-side.
- User and workflow mutations are recorded in the audit-events table.

## Deployment safeguards

The built-in HTTP service is for a controlled, single-host pilot. For network use, place it behind a maintained HTTPS reverse proxy, restrict host and firewall access, use a persistent protected database path, and limit operating-system access to the service account and backups. Do not expose the development HTTP port directly to the internet. The service does not currently implement MFA/SSO, login rate limiting, centralized security monitoring, or automated patch management.

## Data minimization and appraisal use

Collect only work details needed for task coordination and review. Avoid sensitive personal or health information in task descriptions, ratings, feedback, and HR notes. Provide employees access to their own tasks and shared feedback, and use the correction-request process for disputed records. Unshared manager feedback is not visible to employees or HR through normal role workflows; shared feedback is visible to HR for independent review.

Manager ratings and HR grades are decision-support records. They must not be used as the sole basis for employment decisions or treated as a fully objective measure. Human reviewers should consider role expectations, quality, collaboration, dependencies, workload, changed priorities, and employee context.

## Governance still required

Before broader use, the organization must set retention and deletion rules, access-review cadence, incident response, backup handling, employee notices and correction procedures, and applicable privacy/security review. This application does not certify or guarantee legal compliance.
