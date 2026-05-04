# presentations

Customer decks, QBRs, playbooks, and internal growth/velocity reports for YouSquared.

Published at: https://strange-attractor.com/presentations/

## Structure

```
/
├── customer-facing/
│   ├── pitch-decks/
│   │   ├── all-industries/       # AI Secretary for Service Businesses
│   │   ├── oncology/
│   │   ├── pharmacy/             # FR
│   │   └── pharmacy-en/
│   ├── qbrs/
│   │   └── hair-shunnarah-*/     # Customer QBRs
│   └── white-glove-playbooks/
│       └── seller-playbook/      # Proactive support playbook
├── company-internal/
│   ├── dev-velocity/             # PR merge rate & review times
│   ├── ltv-cac/                  # Monthly LTV:CAC growth dashboard
│   ├── subscriber-retention/     # (coming soon)
│   └── who-gets-value/           # Value report
├── .templates/                   # Shared templates for new decks
└── .scripts/                     # QBR harvesting tooling
```

## Adding a new deck

1. Create a subfolder under the right category: `<category>/<name>/` with `index.html`
2. Add a link row to the parent category's `index.html` and the root `index.html`
3. Commit + push to `gh-pages` — deploys automatically

## PII policy

All customer/user full names must be redacted to initials (e.g. "J.S." not "John Smith") per company policy. Call recordings (MP3s) and unmasked phone numbers are not permitted in this public repo — strip before committing.

## Auth gating

Cloudflare Access gates `/presentations/*` except pitch decks and the index.

| Path | Access |
|---|---|
| `/presentations/` (index) | Public |
| `/presentations/customer-facing/pitch-decks/*` | Public |
| `/presentations/customer-facing/qbrs/*` | Gated |
| `/presentations/customer-facing/white-glove-playbooks/*` | Gated |
| `/presentations/company-internal/*` | Gated |

Login: email one-time PIN. Allowed: anyone `@yousquared.ai`, anyone `@strange-attractor.com`, plus specific grants.

**Setup runbook**: [.auth/RUNBOOK.md](.auth/RUNBOOK.md) (Cloudflare dashboard steps).

**Manage grants**:
```bash
scripts/list-access.sh                    # show current rules
scripts/grant-access.sh user@example.com  # add specific email
scripts/revoke-access.sh user@example.com # remove specific email
```
Scripts read CF API credentials from `scripts/.env` (gitignored; template at `scripts/.env.example`).
