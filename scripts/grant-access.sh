#!/usr/bin/env bash
# Add an email to the YouSquared Presentations Access policy.
# Usage: scripts/grant-access.sh <email>
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_cf-common.sh"

email="${1:?Usage: $0 <email>}"
case "$email" in
  *@*.*) ;;
  *) echo "Error: '$email' doesn't look like an email" >&2; exit 1 ;;
esac

current_include=$(cf_get_policy | jq '.result.include')

# Skip if already present (specific-email rule)
if jq -e --arg e "$email" 'any(.email.email == $e)' <<<"$current_include" >/dev/null; then
  echo "Already allowed: $email"
  exit 0
fi

jq --arg e "$email" '. + [{"email": {"email": $e}}]' <<<"$current_include" | cf_put_policy_include
echo "Granted: $email"
