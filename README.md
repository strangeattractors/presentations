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

Gated pages are AES-256 encrypted client-side via [staticrypt](https://github.com/robinmoisson/staticrypt). Same shared password unlocks every gated page; "Remember me" caches it for 30 days. The salt in `.staticrypt.json` is shared across files so unlocking once works everywhere.

| Path | Access |
|---|---|
| `/presentations/` (index) | Public |
| `/presentations/customer-facing/pitch-decks/*` | Public |
| `/presentations/customer-facing/qbrs/*` | Encrypted |
| `/presentations/customer-facing/white-glove-playbooks/*` | Encrypted |
| `/presentations/company-internal/*` | Encrypted |

### Editing an encrypted page

The committed `index.html` is the encrypted blob. To edit:

```bash
# 1. Decrypt in place (asks for password, writes plaintext over encrypted file)
staticrypt --decrypt company-internal/ltv-cac/index.html -p <password> \
           -d company-internal/ltv-cac
# 2. Edit
# 3. Re-encrypt with same flags as original (salt comes from .staticrypt.json)
staticrypt company-internal/ltv-cac/index.html -p <password> --short \
           -d company-internal/ltv-cac --remember 30 \
           --template-button "Unlock" --template-title "YouSquared — Protected" \
           --template-color-primary "#E07A5F" --template-color-secondary "#2D2A26" \
           --template-instructions "Internal page · ask the team for the password"
```

A plaintext backup of the originals is stashed in `/tmp/presentations-plaintext-*` after each encrypt run on this machine — not in the repo.

### Open Graph / link previews

Per-page OG/Twitter card metadata lives in `og-meta.json` at the repo root. After encrypting (which strips the tags), run:

```bash
python3 scripts/inject-og.py
```

The script is idempotent: it replaces an existing `<!-- OG-INJECT:START --> … <!-- OG-INJECT:END -->` block, or inserts one after `<title>` if missing.

To add a new gated page, append an entry in `og-meta.json` keyed by relative path with `page_title`, `og_title`, `og_description`, `og_url`, and (optionally) custom image fields. Defaults to the YouSquared hero illustration if `og_image` is omitted.

### Changing the password

Decrypt every gated file, then re-encrypt with the new password. Update `.staticrypt.json`'s salt only if you also want to invalidate existing browser remember-me sessions.

### Adding a new gated page

Author plaintext, add a link in the parent `index.html`, then run the encrypt command above on the new file. Pitch decks and the root index stay plaintext — don't encrypt them.
