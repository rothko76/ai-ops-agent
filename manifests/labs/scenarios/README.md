# Incident Lab Scenarios

Each scenario has:
- `scenario.yaml`
- `start.sh`
- `cleanup.sh`

## Available Scenarios

- `missing-secret`: Pod references a non-existent secret (`CreateContainerConfigError`).
- `crashloop`: Container exits immediately (`CrashLoopBackOff`).
- `image-pull-backoff`: Invalid image path (`ImagePullBackOff` or `ErrImagePull`).
- `bad-upgrade-rollout`: Deployment starts healthy, then a bad image upgrade breaks rollout (`ImagePullBackOff`), ideal for rollback demos.
- `bad-config-rollout`: Deployment starts healthy, then a bad env config rollout causes app exit and `CrashLoopBackOff`.
- `unschedulable`: Impossible node selector (`Pending` with scheduling failures).

## Usage

Run directly:

```bash
bash manifests/labs/scenarios/missing-secret/start.sh
bash manifests/labs/scenarios/missing-secret/cleanup.sh
```

Or use the scenario runner:

```bash
bash manifests/labs/scenarios/run.sh start missing-secret
bash manifests/labs/scenarios/run.sh cleanup missing-secret
```
