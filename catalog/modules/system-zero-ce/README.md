# system-zero-ce

Audits the local System Zero installation and reconstructed stack readiness.

## Behavior

- check .sz.yaml, .sz/registry.json, bus, memory, and installed modules
- summarize protocol readiness without calling external services
- emit concrete remediation hints for missing runtime pieces

On every tick this module emits `ce.system.zero.audit.snapshot` with module-specific outcome fields and records the same outcome in the `ce.reconstruction` memory stream.

## Source discipline

The source candidate was reconstructed into protocol-native behavior. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install system-zero-ce
sz doctor system-zero-ce
sz tick --reason system-zero-ce-smoke
```
