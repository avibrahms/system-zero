# mcp-server-launcher-ce

Discovers MCP server definitions and produces a launch readiness plan.

## Behavior

- find MCP config files and server scripts in the repository
- classify servers as launchable, missing command, or config-only
- emit a deterministic launch plan instead of starting long-running processes

On every tick this module emits `ce.mcp.launch.plan.snapshot` with module-specific outcome fields and records the same outcome in the `ce.reconstruction` memory stream.

## Source discipline

The source candidate was reconstructed into protocol-native behavior. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install mcp-server-launcher-ce
sz doctor mcp-server-launcher-ce
sz tick --reason mcp-server-launcher-ce-smoke
```
