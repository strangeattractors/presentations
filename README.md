# presentations

Customer-facing decks, QBRs, and playbooks for YouSquared.

Published at: https://strange-attractor.com/presentations/

## Structure

```
/
├── all-industries/          # Industry-agnostic pitch deck
├── oncology/                # Oncology pitch deck
├── pharmacy/                # Pharmacy pitch (FR)
├── pharmacy-en/             # Pharmacy pitch (EN)
├── qbrs/
│   └── hair-shunnarah-*/    # Customer QBRs
├── white-glove-playbook/    # Proactive support playbook
├── yousquared-value-report/ # Value report
├── .templates/              # Shared templates for new decks
└── .scripts/                # QBR harvesting tooling
```

## Adding a new deck

1. Create a subfolder: `<name>/` with `index.html`
2. Add a link row to the root `index.html`
3. Commit + push to `gh-pages` — deploys automatically

## PII policy

All customer/user full names must be redacted to initials (e.g. "J.S." not "John Smith") per company-wide rule. Call recordings (MP3s) and unmasked phone numbers are not permitted in this public repo — strip before committing.

## Roadmap — Phase 2: auth gating

Current state: **public** (served by GitHub Pages, no auth).

Planned: Cloudflare Access in front of `/presentations/*` so only authorized viewers can see content.

### Policy design
- Anyone with a `@strange-attractor.com` or `@yousquared.ai` email → automatic access (domain rule)
- Individual YouSquared users granted ad-hoc → listed in `.auth/allowed.json` (emails)
- Cohorts (e.g. "All Access plan users") → resolved to emails via prod DB query, appended to list
- Login via email one-time-PIN (no Google account required)

### Tasks
- [ ] Move `strange-attractor.com` DNS to Cloudflare
- [ ] Create Zero Trust Access Application scoped to `/presentations/*`
- [ ] Seed `.auth/allowed.json` with team emails + initial grants
- [ ] Write `scripts/grant-access.sh <email-or-user>` — updates JSON, syncs to CF Access API, commits
- [ ] Write `scripts/revoke-access.sh <email>` — inverse
- [ ] Document process here
