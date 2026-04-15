# queue-gate-ce

Counts active ready-queue entries and opens or closes a content-production gate.

## Behavior

- parse markdown queue cards from shared content storage
- ignore posted and rejected entries
- compare active queue depth to the configured maximum

On every tick this module emits `ce.queue.gate.snapshot` with module-specific outcome fields and records the same outcome in the `ce.reconstruction` memory stream.

## Source discipline

The source candidate was reconstructed into protocol-native behavior. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install queue-gate-ce
sz doctor queue-gate-ce
sz tick --reason queue-gate-ce-smoke
```
