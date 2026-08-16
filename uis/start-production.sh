#!/bin/sh
set -eu

cleanup() {
  trap - EXIT INT TERM
  kill "${website_pid:-}" "${backoffice_pid:-}" 2>/dev/null || true
  wait "${website_pid:-}" "${backoffice_pid:-}" 2>/dev/null || true
}

trap cleanup EXIT INT TERM
workspace_root="${WORKSPACE_ROOT:-/workspace}"

cd "$workspace_root/uis/website"
npm run start -- --hostname 0.0.0.0 --port 3000 &
website_pid=$!

cd "$workspace_root/uis/backoffice"
npm run start -- --hostname 0.0.0.0 --port 3001 &
backoffice_pid=$!

while kill -0 "$website_pid" 2>/dev/null && kill -0 "$backoffice_pid" 2>/dev/null; do
  sleep 1
done

status=0
if ! kill -0 "$website_pid" 2>/dev/null; then
  wait "$website_pid" || status=$?
else
  wait "$backoffice_pid" || status=$?
fi
exit "$status"
