#!/bin/bash
# Run the test suite. Pass extra args through:
#   scripts/test.sh                                # all tests
#   scripts/test.sh core.tests.services.test_auth  # one module
#   scripts/test.sh -v 2                           # verbose
#
# Tests run under config.settings_test, which pins every I/O-bound backend
# (WhatsApp, email, geo) to in-process fakes. Override DJANGO_SETTINGS_MODULE
# if you need to.

set -e
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings_test}"
if [ $# -eq 0 ]; then
    exec uv run python manage.py test core.tests web.tests
fi
exec uv run python manage.py test "$@"
