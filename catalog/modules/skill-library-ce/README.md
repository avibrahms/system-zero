# skill-library-ce

Sanitized recursive-question skill library reconstructed as a protocol module.

## Behavior

On every tick this module reads its sanitized reconstruction contract, observes the current System Zero registry, emits `ce.skill.library.snapshot`, and appends a record to the `ce.reconstruction` memory stream.

## Source discipline

The original connection-engine source was reduced to anonymized behavior, metrics, and interface contracts. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install skill-library-ce
sz doctor skill-library-ce
sz tick --reason skill-library-ce-smoke
```
