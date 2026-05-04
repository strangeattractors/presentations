#!/usr/bin/env bash
# Print current Allow-policy rules: domain endings + specific emails.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_cf-common.sh"

cf_get_policy | jq -r '
  .result.include[] |
  if .email_domain.domain then "domain: \(.email_domain.domain)"
  elif .email.email     then "email:  \(.email.email)"
  else "other:  \(.)"
  end
'
