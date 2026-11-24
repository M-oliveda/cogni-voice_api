#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
#
# Fill `$NAME` placeholders in the Kong declarative config from the environment,
# then start Kong. Adapted from Supabase's docker/volumes/api/kong-entrypoint.sh.
# awk is used instead of eval so YAML quoting survives, and placeholders whose
# variable is not set are left as they are.
set -eu

awk '{
  result = ""
  rest = $0
  while (match(rest, /\$[A-Za-z_][A-Za-z_0-9]*/)) {
    name = substr(rest, RSTART + 1, RLENGTH - 1)
    if (name in ENVIRON) {
      result = result substr(rest, 1, RSTART - 1) ENVIRON[name]
    } else {
      result = result substr(rest, 1, RSTART + RLENGTH - 1)
    }
    rest = substr(rest, RSTART + RLENGTH)
  }
  print result rest
}' /home/kong/temp.yml > "$KONG_DECLARATIVE_CONFIG"

exec /entrypoint.sh kong docker-start
