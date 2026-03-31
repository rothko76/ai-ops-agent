#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

kubectl apply -f "$DIR/scenario.yaml"
echo "Scenario started: missing-secret"
kubectl get pods -n agent-lab-missing-secret
