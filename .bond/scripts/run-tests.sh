#!/bin/sh
# Run the bond test suite with the project venv (extra args go to pytest, e.g. run-tests.sh test/bond/test_local.py -v)
exec .venv/bin/python -m pytest "$@"
