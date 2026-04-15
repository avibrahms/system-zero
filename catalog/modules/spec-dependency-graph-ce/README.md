# spec-dependency-graph-ce

Builds a dependency graph from phase and workflow specification documents.

## Behavior

- discover phase plan and workflow specification files
- extract references between phases, specs, and protocol documents
- detect broken references and cycles in the extracted graph

On every tick this module emits `ce.spec.dependency.graph.snapshot` with module-specific outcome fields and records the same outcome in the `ce.reconstruction` memory stream.

## Source discipline

The source candidate was reconstructed into protocol-native behavior. No private paths, operator identity, account data, product registry, or personal workflow content is shipped.

## Install

```bash
sz install spec-dependency-graph-ce
sz doctor spec-dependency-graph-ce
sz tick --reason spec-dependency-graph-ce-smoke
```
