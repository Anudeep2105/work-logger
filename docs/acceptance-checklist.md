# Acceptance Checklist

Use this checklist for a supervised release review. It is a manual procedure, not evidence that these checks have already passed. Record date, build identifier, reviewer, result, and any issue for each item.

## Setup and access

- [ ] Fresh installation starts and the initial administrator can be created.
- [ ] Administrator can create manager, HR, and employee profiles and assign reporting relationships.
- [ ] Temporary password is changed at first login; inactive users cannot sign in.
- [ ] Sign out and session expiration return the user to login.

## Role workflows

- [ ] Manager can create a task for a direct report and cannot manage unrelated employees.
- [ ] Manager can rate with narrative, save private feedback, share feedback, and correct it.
- [ ] Employee sees own tasks and shared feedback, can update permitted status fields, and can request a correction.
- [ ] Manager can record an accept/decline decision with resolution note for a direct-report correction.
- [ ] HR can review shared feedback, independently grade it, add a note, and set disposition.
- [ ] Manager edits to shared feedback invalidate the prior HR review for reevaluation.
- [ ] Administrator can inspect audit events and manage accounts.

## Persistence and deployment

- [ ] Data remains after a clean service restart and after a verified backup restore.
- [ ] Desktop browser reaches service over HTTPS through the approved reverse proxy.
- [ ] Direct internet access to the development HTTP port is blocked.
- [ ] Backup permissions and restore procedure meet organization policy.
- [ ] Privacy notice, retention policy, access review, and employee correction procedure are approved before real data use.

## Human review

- [ ] Reviewers understand ratings and HR grades are decision-support inputs, not an automated or sole appraisal measure.
- [ ] Reviewers consider role context, quality, workload, dependencies, changed priorities, and employee explanations.
