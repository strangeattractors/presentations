# Auth-gating runbook — Cloudflare Access setup

One-time setup to gate `/presentations/*` (except pitch-decks) behind email login.

## Step 1 — Add `strange-attractor.com` to Cloudflare

1. https://dash.cloudflare.com → Add a Site → enter `strange-attractor.com`
2. Choose **Free** plan
3. Cloudflare imports existing DNS records — review and confirm A/AAAA records still point at GitHub Pages (`185.199.108.153` etc.)
4. CF gives you 2 nameservers like `xxx.ns.cloudflare.com`
5. At your registrar (whoever owns strange-attractor.com), replace the existing nameservers with the 2 CF nameservers
6. Wait for propagation (15 min – 24 h, usually <1 h). CF emails when active.

**Verify:** `dig NS strange-attractor.com +short` returns the CF nameservers.

## Step 2 — Create Zero Trust Access Application

1. https://one.dash.cloudflare.com → Zero Trust → Access → Applications → Add an application
2. Type: **Self-hosted**
3. Application name: `YouSquared Presentations`
4. Session duration: `24 hours`
5. **Application domain** — add five entries:
   - `strange-attractor.com/presentations/company-internal/*`
   - `strange-attractor.com/presentations/customer-facing/qbrs/*`
   - `strange-attractor.com/presentations/customer-facing/white-glove-playbooks/*`
   - `strange-attractor.com/presentations/.auth/*` (gate this runbook itself)
   - `strange-attractor.com/presentations/scripts/*` (gate the management scripts)

   (Pitch decks at `/presentations/customer-facing/pitch-decks/*` and the index `/presentations/` are NOT in the app, so they stay public.)

6. Identity providers: **One-time PIN** (no extra config needed; logs in via emailed code)

## Step 3 — Create the access policy

Inside the app, add a policy:
- Name: `YouSquared + grantees`
- Action: **Allow**
- Session duration: inherit (24 h)
- Include rules (add three):
  - **Emails ending in** `@yousquared.ai`
  - **Emails ending in** `@strange-attractor.com`
  - **Emails** (specific list) — start with: `nathan@airstreet.com`

Save. Visiting any gated path now shows the email-OTP login screen.

## Step 4 — Capture IDs for the management scripts

In the app's URL: `…/access/applications/<APP_UUID>/`. Note that UUID.

Inside the app, click the policy → URL has `…/policies/<POLICY_UUID>/`. Note that UUID.

Get your account ID: dashboard URL `…/cloudflare.com/<ACCOUNT_ID>/…`.

Create an API token: My Profile → API Tokens → Create Token → Custom token →
- Permissions: **Account · Access: Apps and Policies · Edit**
- Account Resources: include the YouSquared account
- Save the token (shown once).

Fill in `scripts/.env` (template at `scripts/.env.example`):
```
CF_ACCOUNT_ID=...
CF_ACCESS_APP_ID=...
CF_ACCESS_POLICY_ID=...
CF_API_TOKEN=...
```

## Step 5 — Verify

```bash
scripts/list-access.sh    # prints domain rules + nathan@airstreet.com
scripts/grant-access.sh somebody@example.com
scripts/revoke-access.sh somebody@example.com
```

Test the gate from a private browser window:
- `https://strange-attractor.com/presentations/customer-facing/pitch-decks/all-industries/` → loads (public)
- `https://strange-attractor.com/presentations/company-internal/ltv-cac/` → email-OTP screen

## Notes

- **DNS migration affects all of `strange-attractor.com`**, not just `/presentations/`. Other subpaths/subdomains keep working — Cloudflare proxies them through unchanged.
- **Pitch decks stay public** because they're not in the app's path patterns. Don't add them later by accident.
- **iframe embedding**: `company-strategy/index.html` embeds `ltv-cac/index.html` — both gated, same domain, so the iframe inherits the parent's session cookie. No action needed.
- **Search engine indexing**: gated paths return 302 to login for crawlers, so they won't be indexed. Public paths (pitch decks, index) remain crawlable.
- **Revoking domain access**: removing a `@yousquared.ai` user from the policy individually doesn't override the domain rule. To exclude one person from a domain rule, add a separate **Block** policy above the Allow policy with their specific email.
