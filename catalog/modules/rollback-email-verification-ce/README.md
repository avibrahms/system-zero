# rollback-email-verification-ce

Removes generic email verification artifacts from shared System Zero storage.

## Behavior

- delete verification outcome files created by draft checks
- remove matching verifier entries from external output logs
- remove matching intercepted email signal records idempotently

On every tick this module emits `ce.email.verification.rollback.snapshot` with module-specific outcome fields and records the same outcome in the `ce.reconstruction` memory stream.

## Source discipline

The source candidate was reconstructed into protocol-native behavior. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install rollback-email-verification-ce
sz doctor rollback-email-verification-ce
sz tick --reason rollback-email-verification-ce-smoke
```
