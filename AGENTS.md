# Agent task coordination

Use Beads for task tracking when it is configured in your workspace.
Connection settings and credentials are machine-local and must not be committed.

1. Set a distinct `BEADS_ACTOR` for this agent session.
2. Check `bd context` and `bd dolt test` before task writes.
3. Select work with `bd ready`; claim it with `bd update ID --claim`.
4. Do not override another agent's active claim. Close completed work with
   `bd close ID` and include the relevant verification results.

If Beads is not configured or its connection fails, obtain the local setup
instructions from the maintainer. Do not initialize a replacement database,
change the backend, or publish connection details as a workaround.
