# action-card-cleanup-ce

Archives completed action-card items from shared storage and removes them from the active card.

## Behavior

- read shared action-card, completion-state, and archive JSON files
- append completed active items to the permanent archive idempotently
- remove archived items from the active card and clear completion state

On every tick this module emits `ce.action.card.cleanup.snapshot` with module-specific outcome fields and records the same outcome in the `ce.reconstruction` memory stream.

## Source discipline

The source candidate was reconstructed into protocol-native behavior. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install action-card-cleanup-ce
sz doctor action-card-cleanup-ce
sz tick --reason action-card-cleanup-ce-smoke
```
