#!/usr/bin/env bash
set -euo pipefail

# Deterministic local-only supply chain checks.

export SUPPLY_CHAIN_ENABLED=${SUPPLY_CHAIN_ENABLED:-1}
export PYTHON_VERSION_PIN=${PYTHON_VERSION_PIN:-3.12.5}

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "$SUPPLY_CHAIN_ENABLED" != "1" ]]; then
  echo "Supply chain checks disabled via SUPPLY_CHAIN_ENABLED=0" >&2
  exit 0
fi

PYTHON_BIN="python3"
if [[ -x ".venv/bin/python" ]]; then PYTHON_BIN=".venv/bin/python"; fi

function verify_base_images() {
  for df in "$REPO_ROOT/apps/orchestrator/Dockerfile" "$REPO_ROOT/apps/worker/Dockerfile"; do
    if [[ ! -f "$df" ]]; then continue; fi
    local from_line
    from_line=$(grep -E "^FROM\s+" "$df" | head -n1 || true)
    if [[ -z "$from_line" ]]; then echo "No FROM in $df" >&2; return 1; fi
    if echo "$from_line" | grep -q ":latest\b"; then
      echo "Refusing unpinned base image in $df: $from_line" >&2
      return 1
    fi
    if ! echo "$from_line" | grep -Eq "python:[0-9]+\.[0-9]+\.[0-9]+(-slim)?"; then
      echo "Base image must pin full semver tag in $df: $from_line" >&2
      return 1
    fi
    # Verify .python-version alignment (major.minor.patch exact match)
    local pinned_tag
    pinned_tag=$(echo "$from_line" | awk '{print $2}' | cut -d: -f2)
    if [[ "$pinned_tag" != "$PYTHON_VERSION_PIN"* ]]; then
      echo "Dockerfile $df python tag '$pinned_tag' does not match PYTHON_VERSION_PIN '$PYTHON_VERSION_PIN'" >&2
      return 1
    fi
  done
  return 0
}

function verify_python_version_file() {
  local ver_file="$REPO_ROOT/.python-version"
  if [[ ! -f "$ver_file" ]]; then
    echo ".python-version missing" >&2
    return 1
  fi
  local file_ver
  file_ver=$(cat "$ver_file" | tr -d '\n' | tr -d '\r' )
  if [[ "$file_ver" != "$PYTHON_VERSION_PIN" ]]; then
    echo ".python-version is '$file_ver' but expected '$PYTHON_VERSION_PIN'" >&2
    return 1
  fi
}

function gen_lockfiles() {
  "$PYTHON_BIN" "$REPO_ROOT/scripts/gen_lockfiles.py"
}

function gen_sbom() {
  "$PYTHON_BIN" "$REPO_ROOT/scripts/sbom_gen.py"
}

function check_licenses() {
  "$PYTHON_BIN" "$REPO_ROOT/scripts/license_check.py"
}

verify_base_images
verify_python_version_file
gen_lockfiles
gen_sbom
check_licenses

echo "Supply chain checks completed successfully."


