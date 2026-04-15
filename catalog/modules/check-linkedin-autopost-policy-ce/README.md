# check-linkedin-autopost-policy-ce

Checks generic content auto-post policy files for stale eligibility and cadence language.

## Behavior

- read shared content policy and posting markdown files
- verify only approved content is eligible for automated posting
- emit precise policy drift findings without touching account data

On every tick this module emits `ce.content.autopost.policy.snapshot` with module-specific outcome fields and records the same outcome in the `ce.reconstruction` memory stream.

## Source discipline

The source candidate was reconstructed into protocol-native behavior. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install check-linkedin-autopost-policy-ce
sz doctor check-linkedin-autopost-policy-ce
sz tick --reason check-linkedin-autopost-policy-ce-smoke
```
