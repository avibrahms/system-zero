<!-- project-meta
id: solo-venture
todoist_project: "Solo Venture Engine"
context: business
zone: module
health_override: active
keywords: solo founder, product, MVP, ship, launch, revenue, MRR, stripe, vibe coding, micro-SaaS, build in public, kill, scale, monetize
products: [ship-or-skip, fleetai, system0, sample-product]
-->

# Solo Venture Engine

**Health:** `active` [SHIPPING FREEZE — RED count = 2]. Read `METRICS.md` first. Freeze lifts when RED <2.
**Currently RED:** Revenue ($0 MRR) + Content loop (underdistributed). Fix distribution + kill discipline before new builds.

## Idea Generation (PERMANENT)

90% target: developers, AI engineers, indie hackers. 10% max: compliance/regulation/governance. Every product must solve a business problem worth $99+/mo.

## Complexity Floor (PERMANENT)

Minimum sample-product-level: multiple endpoints/workflows, auth, billing, API docs. No 1-2 hour tools. Min build: 3-7 days.

## Session Protocol

1. `python3 core/system/scripts/solo-venture-sync.py --quiet` (syncs sample-products ↔ registry ↔ PORTFOLIO.md)
2. `python3 modules/solo-venture/engine/generate-ideas.py --bridge --quiet` (idempotent, auto-creates Todoist ≥25/30)
3. Check dashboard at `localhost:8686`
4. After deploy: `python3 core/system/scripts/solo-venture-shipping-check.py --slug <slug> --mode registry`. NOT complete until registry check passes.

## Architecture (Two Repos)

| Repo | Contains |
|------|----------|
| `connection-engine/modules/solo-venture/` | Strategy, protocols, ideas, registry, metrics |
| `sample-products/` | Next.js monorepo, app code, deploy scripts |

`solo-venture-sync.py` bridges them. Deploy via `scripts/deploy-product.sh`. Ship via `scripts/ship.sh`.

## Infrastructure

Cloudflare Pages (static) or Fly.io (server). `example.com` subdomains (Hostinger). Stripe Checkout. Dashboard on port 8686.

## Principles (Levels Pattern)

1. Scratch own itch. 2. 14-30 days idea to live. 3. Charge from day one. 4. Kill at 60 days if $0. 5. Every product event = LinkedIn content. 6. Zero employees. 7. Lean stack. 8. 5% hit rate is fine — ship 6-8/year.
