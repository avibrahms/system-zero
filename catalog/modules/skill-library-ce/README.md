# skill-library-ce

Exposes the sanitized recursive-question skill catalog as a queryable module.

## Behavior

- load sanitized skill contracts from source/skills.json
- count skills and match them against the current query
- publish a digest so downstream modules can detect library changes

On every tick this module emits `ce.skill.library.snapshot` with module-specific outcome fields and records the same outcome in the `ce.reconstruction` memory stream.

## Source discipline

The source candidate was reconstructed into protocol-native behavior. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install skill-library-ce
sz doctor skill-library-ce
sz tick --reason skill-library-ce-smoke
```
