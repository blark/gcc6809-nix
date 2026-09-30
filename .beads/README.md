# Shared Beads task database

This repository uses the homelab's Kubernetes-hosted Dolt server:

- Database: `gcc6809`
- SQL user: `beads`
- Client endpoint: `127.0.0.1:3307` through Kubernetes port-forward
- Password: machine-local `~/.config/beads/credentials`, never committed

Run one tunnel per machine and keep it running:

```sh
kubectl -n beads port-forward --address 127.0.0.1 svc/dolt 3307:3306
```

Authorized machines use this credentials file (mode 0600, parent 0700):

```ini
[127.0.0.1:3307]
password = <shared-password>
```

Then verify from this repository:

```sh
bd context
bd dolt test
bd ready
```

The context must show database `gcc6809`, server mode, and port `3307`.
Tracked metadata/config points clones at the same database. Do not bootstrap
an independent local database from Git or force reinitialization. If the
connection fails, restore the tunnel first. It must be restarted after its
pod is replaced or the connection drops.

Use a distinct `BEADS_ACTOR` per agent and `bd update ID --claim` to coordinate
work. Agents share one authoritative database, so normal work does not need
Dolt push/pull. The auto-configured Git remote is not evidence that backups
exist: off-cluster backups are not yet configured.

The server is managed through Flux in `homelab-k8s/apps/beads`. Do not run
`bd dolt start/stop` or change schemas concurrently with other agents.

For a genuinely new project, the deployment repository provides
`apps/beads/init-project.py`. It handles Beads 1.3's init-only environment
password requirement and persists shared-server port 3307. This project is
already initialized; use the connection checks above instead.
