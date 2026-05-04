#!/usr/bin/env bash
# Shared helpers for Cloudflare Access management scripts.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE not found. Copy scripts/.env.example to scripts/.env and fill in." >&2
  exit 1
fi
# shellcheck disable=SC1090
. "$ENV_FILE"

: "${CF_ACCOUNT_ID:?CF_ACCOUNT_ID missing in scripts/.env}"
: "${CF_ACCESS_APP_ID:?CF_ACCESS_APP_ID missing in scripts/.env}"
: "${CF_ACCESS_POLICY_ID:?CF_ACCESS_POLICY_ID missing in scripts/.env}"
: "${CF_API_TOKEN:?CF_API_TOKEN missing in scripts/.env}"

CF_API="https://api.cloudflare.com/client/v4"
POLICY_URL="$CF_API/accounts/$CF_ACCOUNT_ID/access/apps/$CF_ACCESS_APP_ID/policies/$CF_ACCESS_POLICY_ID"

cf_get_policy() {
  curl -fsS -H "Authorization: Bearer $CF_API_TOKEN" "$POLICY_URL"
}

# Update the policy's `include` array. Pass new include JSON on stdin.
cf_put_policy_include() {
  local current new_include
  current=$(cf_get_policy)
  new_include=$(cat)
  jq --argjson inc "$new_include" '
    .result | { name, decision, include: $inc, exclude: (.exclude // []), require: (.require // []), session_duration }
  ' <<<"$current" \
    | curl -fsS -X PUT -H "Authorization: Bearer $CF_API_TOKEN" -H "Content-Type: application/json" \
        --data @- "$POLICY_URL" >/dev/null
}
