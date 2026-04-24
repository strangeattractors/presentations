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

## Roadmap — Phase 2: auth gating

Current state: **public** (served by GitHub Pages, no auth).

Planned: Cloudflare Access in front of `/presentations/*` so only authorized viewers can see content.

### Policy design
- `@strange-attractor.com` and `@yousquared.ai` emails → automatic access (domain rule)
- Individual YouSquared users granted ad-hoc → listed in `.auth/allowed.json` (emails)
- Cohorts (e.g. All Access plan users) → resolved to emails via prod DB query, appended to list
- Login via email one-time-PIN (no Google account required)

### Tasks
- [ ] Move `strange-attractor.com` DNS to Cloudflare
- [ ] Create Zero Trust Access Application scoped to `/presentations/*`
- [ ] Seed `.auth/allowed.json` with team emails + initial grants
- [ ] Write `scripts/grant-access.sh <email-or-user>`
- [ ] Write `scripts/revoke-access.sh <email>`
- [ ] Document grant-by-cohort flow (e.g. "all All-Access users")
