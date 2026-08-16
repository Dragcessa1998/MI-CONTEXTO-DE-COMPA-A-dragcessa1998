#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/../.." && pwd)

for project in \
  "$repo_root/uis/backoffice" \
  "$repo_root/uis/website" \
  "$repo_root/uis/talent-pipeline-tracker" \
  "$repo_root/services/talent-api"
do
  (cd "$project" && npm audit --package-lock-only --audit-level=low)
done

uvx pip-audit --path "$repo_root/services/api/.venv/lib/python3.13/site-packages" --progress-spinner off
