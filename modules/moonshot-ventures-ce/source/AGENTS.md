<!-- project-meta
id: moonshot-ventures
todoist_project: "Moonshot Ventures"
context: business
zone: module
health_override: paused — 2026-03-27: no active execution owner; reactivate when one venture is assigned or a System Zero instance is scheduled
keywords: moonshot, ventures, frontier, impossible, biotech, longevity, space, energy, nuclear, fusion, robotics, neural, quantum, synthetic biology, climate, asteroid mining, cap table, fundraising, exit, portfolio, venture engine
products: []
-->

# Moonshot Ventures

AI-accelerated frontier companies targeting problems impossible today but solvable in 5-10 years. Each venture = real company with cap table, fundraising plan, financials, presentation website. Target: $400M+ cumulative exit value.

## Pause Gate

When `health_override` is paused: reference-only. No venture creation, no deploys. Before reactivation: regenerate `intelligence/feed-config.yaml` from `core/system/data/moonshot-domain-spec.json`.

## Qualification (ALL must pass)

1. **Impossible today** — requires AI breakthroughs in 5-10 years. Buildable today → Solo Venture.
2. **Civilization-scale** — millions of lives affected. Step-function change.
3. **Frontier domain** — biotech, space, energy, nuclear, robotics, neural, quantum, synthetic biology, climate.
4. **Company-grade** — cap table, fundraising plan, distribution, financials.
5. **MVP shipped** — real working product on example.com (research tool, API, platform). The "impossible" part is the vision; the MVP is buildable and MUST ship.
6. **Fundraising endgame** — zero capital start → prove via MVP → pre-seed $500K-$2M → seed → Series A.

## Rejection (ANY triggers)

Full vision buildable today → Solo Venture. Traditional SaaS → reject. No investor thesis → reject. <1M lives impact → reject. No deployable MVP possible → reject.

## Session Protocol (after reactivation only)

1. Always Opus subagent. Unlimited research budget.
2. Read `venture-engine.md` before starting.
3. Use `core/system/scripts/moonshot-scorecard.py` for validation.
4. Check `portfolio-tracker.md` to avoid duplicates.
5. After deploy: verify `modules/solo-venture/engine/product-registry.json` has complete entry (name, tagline, category:"Moonshot", status, launchDate, customDomain, url). Incomplete = `partial`.

## Cross-Module

Solo Venture: shared deployment infra. LinkedIn Pipeline: venture research → content. Identity: frontier thought leadership.
