#!/usr/bin/env bash
# Layer 1 — QBR data harvester.
# Deterministic pull of everything a QBR needs that doesn't require editorial judgment.
#
# Usage:
#   bash scripts/qbr_harvest.sh <customer-slug> <receiver_id> <window_start_YYYY-MM-DD> [tz]
# Example:
#   bash scripts/qbr_harvest.sh hair-shunnarah-2026-04 iqb2OrGSVLN1itClADzATN9BUYR2 2025-06-16 America/Chicago
#
# What it writes (under qbrs/<slug>/):
#   data/stats.json                — monthly volume, 24h dist, off-hours split, totals
#   assets/leads-backing.json      — classified leads (from sales_leads table) with anonymized topics
#
# What it does NOT do (Layer 2 — human + LLM-assisted):
#   - Hero tagline · partnership narrative · featured-call selection
#   - Roadmap copy · nitty-gritty steps · contract-routing table
#   - Referral flywheel tabs (property/ASTA/TCPA) — HSTA-specific for now
#
# Requires:
#   - cloud-sql-proxy running on :5432 (script will try to start one)
#   - gcloud auth configured for ad@strange-attractor.com IAM
#   - uv (for psycopg2-binary on the fly)

set -euo pipefail

SLUG="${1:?Usage: qbr_harvest.sh <slug> <receiver_id> <window_start> [tz]}"
RECEIVER="${2:?Receiver ID required (e.g. iqb2OrGSVLN1itClADzATN9BUYR2)}"
WINDOW="${3:?Window start required (YYYY-MM-DD)}"
TZ_NAME="${4:-America/Chicago}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/qbrs/${SLUG}"
mkdir -p "${OUT}/data" "${OUT}/assets"
echo "Writing to ${OUT}/"

if ! lsof -iTCP:5432 -sTCP:LISTEN -n -P >/dev/null 2>&1; then
  echo "cloud-sql-proxy not running on :5432 — starting..."
  cloud-sql-proxy yousquared-prod:us-central1:yousquared-prod-postgres-a6be8a9b \
    --auto-iam-authn --port 5432 >/tmp/csp.log 2>&1 &
  sleep 3
fi

PY=$(mktemp /tmp/qbr_harvest.XXXXXX.py)
trap 'rm -f "$PY"' EXIT
cat > "$PY" <<'PYEOF'
import json, os, re, sys
from datetime import datetime
from collections import Counter
import psycopg2
from psycopg2.extras import RealDictCursor

SLUG     = os.environ["QBR_SLUG"]
RECEIVER = os.environ["QBR_RECEIVER"]
WINDOW   = os.environ["QBR_WINDOW"]
TZ       = os.environ["QBR_TZ"]
OUT      = os.environ["QBR_OUT"]

CONN = "host=127.0.0.1 port=5432 sslmode=disable dbname=yousquared user=ad@strange-attractor.com"
conn = psycopg2.connect(CONN); conn.autocommit = True
cur = conn.cursor(cursor_factory=RealDictCursor)

def q(sql, **params):
    cur.execute(sql, params)
    return cur.fetchall()

# ── Monthly volume, classification split ──────────────────────────────────
monthly = q(f"""
  SET statement_timeout='20s';
  SELECT to_char(date_trunc('month', started_at AT TIME ZONE %(tz)s), 'Mon YY') AS month,
         to_char(date_trunc('month', started_at AT TIME ZONE %(tz)s), 'YYYY-MM') AS month_iso,
         COUNT(*) AS total,
         COUNT(*) FILTER (WHERE is_urgent) AS urgent,
         COUNT(*) FILTER (WHERE NOT is_urgent AND NOT is_empty AND NOT is_spam) AS non_urgent,
         COUNT(*) FILTER (WHERE is_empty) AS empty,
         COUNT(*) FILTER (WHERE is_spam)  AS spam
  FROM conversations
  WHERE receiver_id = %(r)s AND started_at >= %(w)s
  GROUP BY 1,2 ORDER BY 2;
""", r=RECEIVER, w=WINDOW, tz=TZ)

# ── 24-hour distribution ──────────────────────────────────────────────────
hourly = q("""
  SET timezone=%(tz)s;
  SELECT EXTRACT(HOUR FROM (started_at AT TIME ZONE %(tz)s))::int AS hr,
         COUNT(*) AS n
  FROM conversations
  WHERE receiver_id = %(r)s AND started_at >= %(w)s
  GROUP BY 1 ORDER BY 1;
""", r=RECEIVER, w=WINDOW, tz=TZ)
hourly_arr = [0]*24
for row in hourly: hourly_arr[row["hr"]] = row["n"]

# ── Off-hours split (weekday 8-16 CT = in-hours) ──────────────────────────
splits = q("""
  WITH c AS (
    SELECT started_at AT TIME ZONE %(tz)s AS ts
    FROM conversations
    WHERE receiver_id = %(r)s AND started_at >= %(w)s
  )
  SELECT COUNT(*) AS total,
    COUNT(*) FILTER (WHERE EXTRACT(DOW FROM ts) BETWEEN 1 AND 5 AND EXTRACT(HOUR FROM ts) BETWEEN 8 AND 16) AS in_hours,
    COUNT(*) FILTER (WHERE NOT (EXTRACT(DOW FROM ts) BETWEEN 1 AND 5 AND EXTRACT(HOUR FROM ts) BETWEEN 8 AND 16)) AS off_hours
  FROM c;
""", r=RECEIVER, w=WINDOW, tz=TZ)[0]

stats = {
    "customer_slug": SLUG,
    "receiver_id": RECEIVER,
    "window_start": WINDOW,
    "timezone": TZ,
    "generated_at": datetime.utcnow().isoformat() + "Z",
    "totals": dict(splits),
    "off_hours_pct": round(100 * splits["off_hours"] / splits["total"]) if splits["total"] else 0,
    "monthly": [dict(m) for m in monthly],
    "hourly_24h": hourly_arr,
}

# ── Classified leads (from sales_leads table) ─────────────────────────────
leads = q("""
  SELECT sl.conversation_id AS id,
         to_char(c.started_at AT TIME ZONE %(tz)s, 'YYYY-MM-DD') AS date,
         to_char(c.started_at AT TIME ZONE %(tz)s, 'HH12:MI AM') AS time,
         to_char(c.started_at AT TIME ZONE %(tz)s, 'Dy') AS dow,
         GREATEST(1, ROUND(EXTRACT(EPOCH FROM (c.ended_at - c.started_at))/60.0))::int AS dur_min,
         COALESCE(c.is_urgent, false) AS urgent,
         COALESCE(c.short_report, '') AS topic,
         sl.category, sl.lead_type, sl.value_bucket, sl.estimated_value AS fee
  FROM sales_leads sl
  JOIN conversations c ON c.conversation_id = sl.conversation_id
  WHERE sl.user_id = %(r)s AND c.started_at >= %(w)s
  ORDER BY sl.estimated_value DESC NULLS LAST;
""", r=RECEIVER, w=WINDOW, tz=TZ)

# Quick anonymization (conservative — names → initials, PII strings redacted)
NAME_RE  = re.compile(r'\b([A-Z][a-z]{1,20})(?:\s+([A-Z][a-z]{1,20})){1,3}\b')
PHONE_RE = re.compile(r'\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
EMAIL_RE = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
ADDR_RE  = re.compile(r'\b\d{1,5}\s+[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*){0,3}\s+(?:St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Blvd|Boulevard|Way|Ct|Court|Pl|Place|Cir|Circle|Hwy|Highway|Pkwy|Parkway)\b')

def scrub(s):
    if not s: return ""
    s = EMAIL_RE.sub("[email]", s)
    s = PHONE_RE.sub("[phone]", s)
    s = ADDR_RE.sub("[address]", s)
    def _ini(m):
        first = m.group(1)[0]; rest = [g for g in m.groups()[1:] if g]
        last = rest[-1][0] if rest else ""
        return f"{first}{'.'+last+'.' if last else '.'}"
    return NAME_RE.sub(_ini, s)

clean = [{**dict(r), "topic": scrub(r["topic"])[:300]} for r in leads]

# ── Write outputs ─────────────────────────────────────────────────────────
with open(f"{OUT}/data/stats.json", "w") as f:
    json.dump(stats, f, indent=2, default=str)
with open(f"{OUT}/assets/leads-backing.json", "w") as f:
    json.dump(clean, f, default=str)

print(f"stats: {stats['totals']['total']} calls · {stats['off_hours_pct']}% off-hours · {len(monthly)} months")
print(f"leads: {len(clean)} qualified · total fee ${sum((r['fee'] or 0) for r in clean):,}")
print(f"→ {OUT}/data/stats.json")
print(f"→ {OUT}/assets/leads-backing.json")
cur.close(); conn.close()
PYEOF

QBR_SLUG="$SLUG" QBR_RECEIVER="$RECEIVER" QBR_WINDOW="$WINDOW" QBR_TZ="$TZ_NAME" QBR_OUT="$OUT" \
  uv run --with psycopg2-binary python "$PY"
