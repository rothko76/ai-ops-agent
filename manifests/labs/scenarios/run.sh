#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <start|cleanup> <scenario>"
  echo "Scenarios: missing-secret crashloop image-pull-backoff bad-upgrade-rollout bad-config-rollout unschedulable"
  exit 1
fi

ACTION="$1"
SCENARIO="$2"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$BASE_DIR/$SCENARIO/${ACTION}.sh"

if [[ ! -f "$SCRIPT" ]]; then
  echo "Invalid action or scenario: $ACTION $SCENARIO"
  exit 1
fi

bash "$SCRIPT"
