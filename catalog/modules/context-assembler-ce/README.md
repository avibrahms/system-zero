# context-assembler-ce

Selects the highest-signal repository files for a task or focus query.

## Behavior

- derive a context query from setpoints, environment, or recent tick reasons
- score repository files by keyword relevance and freshness
- emit a token-bounded file list for downstream agents

On every tick this module emits `ce.context.assembler.snapshot` with module-specific outcome fields and records the same outcome in the `ce.reconstruction` memory stream.

## Source discipline

The source candidate was reconstructed into protocol-native behavior. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install context-assembler-ce
sz doctor context-assembler-ce
sz tick --reason context-assembler-ce-smoke
```
