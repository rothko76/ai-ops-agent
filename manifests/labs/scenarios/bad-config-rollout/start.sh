#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NS="agent-lab-bad-config"
DEPLOYMENT="config-app"
BROKEN_VALUE="broken"

echo "Applying base scenario with valid config (APP_MODE=prod)..."
kubectl apply -f "$DIR/scenario.yaml"

echo "Waiting for initial rollout to become healthy..."
kubectl -n "$NS" rollout status deployment/"$DEPLOYMENT" --timeout=120s

echo "Introducing bad config rollout (APP_MODE=$BROKEN_VALUE)..."
kubectl -n "$NS" set env deployment/"$DEPLOYMENT" APP_MODE="$BROKEN_VALUE"

echo "Waiting for CrashLoopBackOff signal..."
for _ in {1..30}; do
  if kubectl -n "$NS" get pods -l app="$DEPLOYMENT" -o jsonpath='{range .items[*]}{.status.containerStatuses[*].state.waiting.reason}{"\n"}{end}' 2>/dev/null | grep -Eq 'CrashLoopBackOff'; then
    break
  fi
  sleep 2
done

echo "Scenario started: bad-config-rollout"
echo "Deployment config changed to APP_MODE=$BROKEN_VALUE"
kubectl get pods -n "$NS"
