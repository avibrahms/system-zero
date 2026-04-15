# eidetic-ce

Indexes evidence-like repository documents into a compact memory map.

## Behavior

- scan public markdown and document filenames for evidence concepts
- group evidence surfaces by purpose and file type
- write a searchable memory index without copying private document text

On every tick this module emits `ce.eidetic.index.snapshot` with module-specific outcome fields and records the same outcome in the `ce.reconstruction` memory stream.

## Source discipline

The source candidate was reconstructed into protocol-native behavior. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install eidetic-ce
sz doctor eidetic-ce
sz tick --reason eidetic-ce-smoke
```
