#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

kubectl delete -f "$DIR/scenario.yaml" --ignore-not-found=true
echo "Scenario cleaned: image-pull-backoff"
