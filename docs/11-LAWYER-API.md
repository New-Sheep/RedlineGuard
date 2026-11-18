# Lawyer API (thin JSON)

**Purpose:** Route cheat sheet for session-auth JSON. Runbook: [`../README.md`](../README.md).

Session auth when `REQUIRE_AUTH=1` (default outside tests). Mutating calls need CSRF (`X-CSRFToken` or form token). Roles: **lawyer** (decide/undo/delete-one), **admin** (lab resets).

| Method | Path | Who | Purpose |
|--------|------|-----|---------|
| GET | `/api/contracts/?page=&status=` | auth | Paginated contracts |
| DELETE | `/api/contracts/<uuid>/` | lawyer | Delete contract + unlearn linked Chroma |
| GET | `/api/findings/?contract_id=` | auth | Findings list |
| GET/PATCH/DELETE | `/api/decisions/<uuid>/` | lawyer | Detail; DELETE=undo; PATCH redo |
| GET | `/api/overrides/` | auth | Override file JSON |
| DELETE | `/api/overrides/<rule_id>/?contract_id=` | lawyer | Revoke override |
| GET | `/api/playbook/` | auth | Active playbook + versions |
| POST | `/api/playbooks/activate-restore/` | lawyer | Body `{"version":"…"}` |
| GET | `/api/security-events/` | auth | Security events |
| GET | `/api/audit/` | auth | AuditEvent log (append-only) |
| GET | `/api/memory/` | auth | Precedents |
| DELETE | `/api/memory/<id>/` | lawyer | Unlearn |
| POST | `/api/admin/reset-decisions/` | admin | `{"confirm":"RESET"}` (Decisions + Chroma) |
| POST | `/api/admin/reset-contracts/` | admin | `{"confirm":"RESET"}` |
| POST | `/api/admin/reset-overrides/` | admin | `{"confirm":"RESET"}` |
| POST | `/api/admin/reset-onboarding/` | admin | `{"confirm":"RESET"}` |

HTML: `/login/`, `/onboarding/`, `/contracts/`, `/history/`, `/audit/`, `/help/`, `/trust/`, `/memory/`, `/playbook/`, `/lab/`.

Demo users (`bootstrap_demo_users`): `lawyer` / `lawyer-demo-2026`, `admin` / `admin-demo-2026`.
