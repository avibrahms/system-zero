# spec-lint-ce

Lints System Zero plan and protocol specs for required sections and stale placeholders.

## Behavior

- read phase plans, protocol docs, and shared spec fixtures
- check required headings, acceptance criteria, and unresolved placeholders
- emit lint errors and warnings with file-level counts

On every tick this module emits `ce.spec.lint.snapshot` with module-specific outcome fields and records the same outcome in the `ce.reconstruction` memory stream.

## Source discipline

The source candidate was reconstructed into protocol-native behavior. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install spec-lint-ce
sz doctor spec-lint-ce
sz tick --reason spec-lint-ce-smoke
```
