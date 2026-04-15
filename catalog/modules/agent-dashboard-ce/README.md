# agent-dashboard-ce

Builds a dashboard health snapshot from generic session, action-card, and module state files.

## Behavior

- read shared dashboard/session JSON if present
- summarize active tasks, sessions, and installed module health
- write a module-private dashboard summary for UI adapters

On every tick this module emits `ce.agent.dashboard.snapshot` with module-specific outcome fields and records the same outcome in the `ce.reconstruction` memory stream.

## Source discipline

The source candidate was reconstructed into protocol-native behavior. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install agent-dashboard-ce
sz doctor agent-dashboard-ce
sz tick --reason agent-dashboard-ce-smoke
```
