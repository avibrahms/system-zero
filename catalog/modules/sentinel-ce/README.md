# sentinel-ce

Scans repository files for common secret, config, and safety findings.

## Behavior

- scan text files with bounded traversal
- detect secret-shaped tokens without storing the token values
- emit severity-tagged security and configuration findings

On every tick this module emits `ce.sentinel.scan.snapshot` with module-specific outcome fields and records the same outcome in the `ce.reconstruction` memory stream.

## Source discipline

The source candidate was reconstructed into protocol-native behavior. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install sentinel-ce
sz doctor sentinel-ce
sz tick --reason sentinel-ce-smoke
```
