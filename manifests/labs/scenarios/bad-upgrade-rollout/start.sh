#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NS="agent-lab-bad-upgrade"
DEPLOYMENT="upgrade-app"
CONTAINER="upgrade-app"
BAD_IMAGE="does-not-exist.local/not-a-real-image:latest"

echo "Applying base scenario with a healthy image..."
kubectl apply -f "$DIR/scenario.yaml"

echo "Waiting for initial rollout to become healthy..."
kubectl -n "$NS" rollout status deployment/"$DEPLOYMENT" --timeout=120s

echo "Introducing a bad upgrade image to break the rollout..."
kubectl -n "$NS" set image deployment/"$DEPLOYMENT" "$CONTAINER"="$BAD_IMAGE"

echo "Waiting for rollout to show image pull failure..."
for _ in {1..30}; do
	if kubectl -n "$NS" get pods -l app="$DEPLOYMENT" -o jsonpath='{range .items[*]}{.status.containerStatuses[*].state.waiting.reason}{"\n"}{end}' 2>/dev/null | grep -Eq 'ErrImagePull|ImagePullBackOff'; then
		break
	fi
	sleep 2
done

echo "Scenario started: bad-upgrade-rollout"
echo "Deployment upgraded to invalid image: $BAD_IMAGE"
kubectl get pods -n "$NS"
