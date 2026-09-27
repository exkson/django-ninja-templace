#!/usr/bin/env bash
# Point this clone's git hooks at the tracked .githooks/ directory.
set -euo pipefail

cd "$(dirname "$0")/.."
git config core.hooksPath .githooks
echo "core.hooksPath -> .githooks"
