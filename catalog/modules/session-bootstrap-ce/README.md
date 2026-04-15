# session-bootstrap-ce

Builds a deterministic session-start payload from repo profile, git state, and module health.

## Behavior

- read repo profile and installed module registry
- capture current branch and dirty-file counts when git is available
- write a module-private session bootstrap payload

On every tick this module emits `ce.session.bootstrap.snapshot` with module-specific outcome fields and records the same outcome in the `ce.reconstruction` memory stream.

## Source discipline

The source candidate was reconstructed into protocol-native behavior. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install session-bootstrap-ce
sz doctor session-bootstrap-ce
sz tick --reason session-bootstrap-ce-smoke
```
