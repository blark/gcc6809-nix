# Agent task coordination

Use Beads against the shared homelab Dolt server. This repository's database
is `gcc6809`. All clones and worktrees must use that same database.

1. Set a distinct `BEADS_ACTOR` for this agent session.
2. Check `bd context` and `bd dolt test` before task writes.
3. Select work with `bd ready`; claim it with `bd update ID --claim`.
4. Do not override another agent's active claim. Close completed work with
   `bd close ID` and include the relevant verification results.

One localhost tunnel per machine connects clients to the cluster:

```sh
kubectl -n beads port-forward --address 127.0.0.1 svc/dolt 3307:3306
```

The shared password belongs in `~/.config/beads/credentials`, never in this
repository. See `.beads/README.md` for connection and configuration details.

If the server is unreachable, restore the tunnel; do not initialize a local
replacement database or run `bd dolt start/stop`. Routine Dolt push/pull is
unnecessary because agents share one database. Coordinate migrations, GC,
backup and other server maintenance through one maintainer.
