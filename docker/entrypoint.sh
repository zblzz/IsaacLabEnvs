#!/bin/bash
set -euo pipefail
module_root="$1"
shift
/isaac-sim/python.sh -m pip install --no-index --disable-pip-version-check --user --no-deps --no-build-isolation -e "$module_root" > /tmp/scene-install.log 2>&1 || { cat /tmp/scene-install.log; exit 1; }
while [[ "${1:-}" == "--install" ]]; do
    /isaac-sim/python.sh -m pip install --no-index --disable-pip-version-check --user --no-deps --no-build-isolation -e "$2" >> /tmp/scene-install.log 2>&1 || { cat /tmp/scene-install.log; exit 1; }
    shift 2
done
exec /isaac-sim/python.sh -u "$@"
