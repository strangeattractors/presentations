#!/usr/bin/env bash
# Remove an email from the Access policy. Domain rules are NOT touched.
# Usage: scripts/revoke-access.sh <email>
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_cf-common.sh"

email="${1:?Usage: $0 <email>}"

current_include=$(cf_get_policy | jq '.result.include')

if ! jq -e --arg e "$email" 'any(.email.email == $e)' <<<"$current_include" >/dev/null; then
  echo "Not in specific-email list: $email"
  if jq -e --arg e "$email" '
    any(.email_domain.domain as $d | ($e | endswith("@" + $d)))
  ' <<<"$current_include" >/dev/null; then
    echo "Note: $email matches a domain rule. Add a Block policy above Allow to exclude this user."
  fi
  exit 0
fi

jq --arg e "$email" 'map(select(.email.email != $e))' <<<"$current_include" | cf_put_policy_include
echo "Revoked: $email"
