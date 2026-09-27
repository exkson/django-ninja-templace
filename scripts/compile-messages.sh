#!/bin/bash
# Refresh the French catalogue from source strings, then compile it.
# Requires GNU gettext (msgfmt / xgettext) on PATH.

set -e
cd "$(dirname "$0")/../core"
uv run python ../manage.py makemessages -l fr -e py,html,txt,email
uv run python ../manage.py compilemessages -l fr
