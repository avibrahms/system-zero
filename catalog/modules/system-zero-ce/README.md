# system-zero-ce

System Zero reconstructed as a protocol-native self-improvement organ.

## Behavior

On every tick this module reads its sanitized reconstruction contract, observes the current System Zero registry, emits `ce.system.zero.snapshot`, and appends a record to the `ce.reconstruction` memory stream.

## Source discipline

The original connection-engine source was reduced to anonymized behavior, metrics, and interface contracts. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install system-zero-ce
sz doctor system-zero-ce
sz tick --reason system-zero-ce-smoke
```
