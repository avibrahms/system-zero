# chronicle-ce

Records recent bus events into a hashed daily chronicle stream.

## Behavior

- read recent System Zero bus events
- append normalized events to a daily module-private JSONL chronicle
- maintain a deterministic hash-chain head for tamper evidence

On every tick this module emits `ce.chronicle.snapshot` with module-specific outcome fields and records the same outcome in the `ce.reconstruction` memory stream.

## Source discipline

The source candidate was reconstructed into protocol-native behavior. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install chronicle-ce
sz doctor chronicle-ce
sz tick --reason chronicle-ce-smoke
```
