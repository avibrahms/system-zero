# start-preamble-ce

Generates a compact start-preamble from current session and reference-stack state.

## Behavior

- read repo profile goals and registry state
- combine module health, dirty-file count, and recent events
- write a concise preamble payload for the next operator session

On every tick this module emits `ce.start.preamble.snapshot` with module-specific outcome fields and records the same outcome in the `ce.reconstruction` memory stream.

## Source discipline

The source candidate was reconstructed into protocol-native behavior. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install start-preamble-ce
sz doctor start-preamble-ce
sz tick --reason start-preamble-ce-smoke
```
