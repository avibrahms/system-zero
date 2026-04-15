# registry-validator-ce

Registry Validator reconstructed as a protocol-native self-improvement organ.

## Behavior

On every tick this module reads its sanitized reconstruction contract, observes the current System Zero registry, emits `ce.registry.validator.snapshot`, and appends a record to the `ce.reconstruction` memory stream.

## Source discipline

The original connection-engine source was reduced to anonymized behavior, metrics, and interface contracts. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install registry-validator-ce
sz doctor registry-validator-ce
sz tick --reason registry-validator-ce-smoke
```
