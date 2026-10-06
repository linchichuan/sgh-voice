#!/usr/bin/env bash
# CI entry point for the macOS offline (Japanese, medical) edition, called by
# .github/workflows/macos-medical.yml. Keeping the steps here lets the build
# evolve without editing the workflow (the automation cannot edit workflows).
set -euo pipefail
cd "$(dirname "$0")/.."
echo "::group::Runner"
sw_vers
uname -m
python3 --version
sysctl -n hw.memsize hw.ncpu
echo "::endgroup::"
mkdir -p dist/macos
if [[ -x macos/build-medical.sh ]]; then
  macos/build-medical.sh
else
  echo "macOS medical build not implemented yet; runner check only." | tee dist/macos/SHA256SUMS.txt
fi
