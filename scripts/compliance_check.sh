#!/usr/bin/env bash
set -euo pipefail

# Env toggles
COMPLIANCE_ENABLED=${COMPLIANCE_ENABLED:-1}
REDACTION_MODE=${REDACTION_MODE:-strict}
ALLOW_WARN=${COMPLIANCE_ALLOW_WARN_OVERRIDE:-0}

if [[ "$COMPLIANCE_ENABLED" == "0" || "$COMPLIANCE_ENABLED" == "false" ]]; then
  echo "Compliance disabled (COMPLIANCE_ENABLED=0)"
  exit 0
fi

ROOT_DIR="${1:-.}"
RULES="${RULES_PATH:-compliance/regexes.json}"

exit_code=0

# 1) Secrets scan
python3 scripts/secrets_scan.py --root "$ROOT_DIR" --rules "$RULES" --allow-warn-override || exit_code=$?

# 2) Redaction test vectors
python3 scripts/redaction_test_vectors.py || exit_code=$?

# 3) Audit verify
python3 scripts/audit_verify.py || exit_code=$?

exit $exit_code


