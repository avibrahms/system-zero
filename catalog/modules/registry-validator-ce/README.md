# registry-validator-ce

Validates the installed System Zero registry, manifests, capabilities, and config.

## Behavior

- parse .sz/registry.json and .sz.yaml
- verify every installed module has a manifest, entrypoint, and declared version
- report unsatisfied capabilities and missing configured modules

On every tick this module emits `ce.registry.validation.snapshot` with module-specific outcome fields and records the same outcome in the `ce.reconstruction` memory stream.

## Source discipline

The source candidate was reconstructed into protocol-native behavior. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install registry-validator-ce
sz doctor registry-validator-ce
sz tick --reason registry-validator-ce-smoke
```
