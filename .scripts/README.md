# QBR generator — 3-layer architecture

Automate the boring parts, keep editorial judgment human-curated.

## Quick start

From anywhere, invoke the slash command:

```
/qbr <customer name or slug>
```

Claude drives the whole flow: identifies the customer, runs parallel research
(Slack, Gmail, prod DB, customer web), asks a single batched question for the
unknowables (onsite date, primary contact, flywheel on/off), harvests data,
QAs lead values, drafts editorial content for review, builds the HTML, and
pushes.

The command definition lives at `~/.claude/commands/qbr.md`.

The layers below are the plumbing `/qbr` orchestrates.

## Layer 1 — Data harvester

```bash
bash scripts/qbr_harvest.sh <customer-slug> <receiver_id> <window_start> [tz]
```

Pulls from prod and writes:
- `qbrs/<slug>/data/stats.json` — monthly volume, 24h, off-hours, totals
- `qbrs/<slug>/assets/leads-backing.json` — classified leads from `sales_leads` (anonymized)

Requires: `cloud-sql-proxy` on port 5432 (script starts one if not running), `uv`, GCP IAM auth.

No editorial decisions — deterministic, rerunnable.

## Layer 2 — Brief

Create `qbrs/<slug>/brief.yml` (see `templates/brief.yml.example`).

Human-authored, optionally LLM-assisted. This is where editorial lives:
- Customer name, logo, tagline, mission source
- Onsite audience + date
- Featured calls (hand-picked from the harvested leads JSON)
- Team row for YS side
- YS momentum bullets
- 4 roadmap chapters: impact copy + example transcripts + nitty-gritty checklists
- Referral flywheel toggle + tab content (HSTA-specific for now)

## Layer 3 — Renderer

**Deferred until QBR #2 ships.** For now, adapt the Hair Shunnarah HTML in place:

1. Copy `qbrs/hair-shunnarah-2026-04/` to `qbrs/<new-slug>/`
2. Replace customer-specific strings + featured calls + team row + roadmap
3. Swap asset files (logo, headshots, audio)
4. Commit + push — same flow as always

After customer #2, extract the delta into `templates/qbr.html.j2` + `scripts/qbr_render.py`.

## Why not build Layer 3 now?

Every additional customer reveals what's actually reusable. HSTA has a rich chapter-4 referral flywheel (property / ASTA / TCPA tabs) that most customers won't need. Premature templating bakes in HSTA's quirks as the default.

Run the manual flow for #2, then codify.

## Editorial rules encoded in the `customer-presentation` skill

(see `~/.claude/skills/customer-presentation/SKILL.md`)

- "Urgent = good" — substantive call, not an interruption
- Bias slightly optimistic over slightly conservative
- No techno-jargon in customer-facing copy (no Gemini / LLM / classifier / scan)
- Hero slide: customer firm takes center stage, YS footer-sized
- Per-call $ estimates must survive a spot-check against the fact pattern
