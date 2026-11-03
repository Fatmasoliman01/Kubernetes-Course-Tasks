# Task 1 – Multi-container Pods (Init Container & Sidecar)

## Overview

Run an nginx "hello" page on a 3-node minikube cluster.
The page shows the current time and refreshes every 5 seconds via a sidecar.
hello in MLOPS MENA COMMUNITY : 2026-11-03 12:08:14

---

## Pod Architecture

| Container | Type | Role |
|---|---|---|
| `init-done` | Init container | Prints `done` and exits. Blocks main containers if it fails. |
| `nginx` | Main container | Writes `index.html` with current time, serves on port 80. |
| `time-updater` | Sidecar | Rewrites `index.html` every 5 seconds via `/proc/<pid>/root`. |

**Key concepts used:**
- `shareProcessNamespace: true` — sidecar can see nginx's PID
- `/proc/<pid>/root` — sidecar writes into nginx's filesystem without a volume
- `SYS_PTRACE` capability — required to access another process's `/proc` path
- No volumes used — filesystem sharing through shared process namespace only

---

## Files

| File | Purpose |
|---|---|
| `namespace.yaml` | Creates the `webapp` namespace |
| `deployment.yaml` | Working 3-replica deployment |
| `deployment-fail-init.yaml` | Step 5 – init container that exits 1 |

---

## Steps & Results

### 1. Cluster – 3 nodes Ready

```bash
minikube start --nodes 3 --cni=calico --cpus 1 --memory 1200 --driver=docker --force
kubectl get nodes
```

![3 nodes ready](screenshots/01-nodes-ready.png)

---

### 2. Create Namespace & Deploy

```bash
kubectl apply -f namespace.yaml
kubectl apply -f deployment.yaml
kubectl get pods -n webapp -w
```

![pods running](screenshots/02-pods-running.png)

---

### 3. Page Serving – Time Updates Every 5 Seconds

```bash
kubectl port-forward -n webapp deploy/web-deployment 8080:80 --address=0.0.0.0
curl http://localhost:8080
sleep 6 && curl http://localhost:8080
```

![curl output time 1](screenshots/03-curl-first.png)
![curl output time 2](screenshots/04-curl-second.png)

---

### 4. Verification Checks

```bash
# Deployment ready
kubectl get deploy web-deployment -n webapp

# Container names
kubectl get pods -n webapp -l app=web \
  -o jsonpath='{.items[0].spec.initContainers[*].name} {.items[0].spec.containers[*].name}'

# Init log
kubectl logs deploy/web-deployment -n webapp -c init-done

# Sidecar sees nginx
kubectl exec deploy/web-deployment -n webapp -c time-updater -- ps

# No volumes
kubectl get deploy web-deployment -n webapp \
  -o jsonpath='{.spec.template.spec.volumes}'
```

![verification output](screenshots/05-verification.png)

---

### 5. Breaking the Init Container

Changed init container command to `exit 1`:

```bash
kubectl apply -f deployment-fail-init.yaml
kubectl get pods -n webapp -w
```

**Result:**
- New pod → `Init:Error` → `Init:CrashLoopBackOff`
- `nginx` and `time-updater` never started on the new pod
- 3 old pods stayed `2/2 Running` — page remained reachable

![init crashloopbackoff](screenshots/06-init-fail.png)

```bash
kubectl logs <new-pod> -n webapp -c init-done
```

![init failed log](screenshots/07-init-log.png)

---

### 6. Fix – Back to 3/3

```bash
kubectl apply -f deployment.yaml
kubectl get pods -n webapp -w
kubectl get deploy web-deployment -n webapp
```

![fixed](screenshots/08-fixed.png)

---

## Key Learnings

- Init containers are **gates** — main containers never start if the init fails
- `shareProcessNamespace` lets containers share PIDs inside the same Pod
- `/proc/<pid>/root` lets a sidecar write into another container's filesystem with no volume
- Kubernetes `RollingUpdate` protects users — old pods keep running while new ones are failing
