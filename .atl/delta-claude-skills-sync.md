# Claude Skills Sync Module - Specification

## Overview

| Property | Value |
|----------|-------|
| **Module ID** | claude-skills-sync |
| **Version** | 0.1.0 |
| **Category** | skills |
| **Description** | Installs and manages AI agent skills in repository, bringing modern development patterns |

## Problem

Currently:
- Skills live in AI agent config, not in repository
- Each developer/AI learns framework quirks separately
- No shared conventions across team
- Inconsistent code patterns

## Solution

A skills sync module that:
- Installs skill patterns into `docs/skills/`
- Updates on schedule
- Integrates with existing conventions
- Documents what's installed

## Skills Installed

| Skill | Description | Value |
|-------|-------------|-------|
| react-19 | React 19 with compiler | No more useMemo/useCallback |
| nextjs-15 | Next.js 15 App Router | Server Actions, partial prerendering |
| prisma | Type-safe ORM | Full TypeScript integration |
| playwright | E2E testing | Page Objects, selectors |
| tailwind-4 | Modern CSS | cn(), no var() in className |
| zustand-5 | State management | New simplified API |
| supabase | Firebase alternative | BaaS with PostgreSQL |
| sdd | Spec-Driven Development | opspec workflow |
| engram | Persistent memory | Cross-session context |
| +30 more | Various frameworks | Full stack coverage |

## API Commands

```bash
# Install skills
sz skills install --recommend     # Install recommended for repo type
sz skills install react-19 nextjs-15 tailwind-4

# List and manage
sz skills list                # List installed skills
sz skills update            # Check for updates

# Configuration
sz config set skills.auto_update weekly
```

## Module Structure

```
modules/claude-skills-sync/
├── module.yaml
├── entry.sh                  # Main sync logic
├── skills.yaml              # List of skills to sync
├── reconcile.sh
├── doctor.sh
└── templates/
    gitignore patterns
    README.md
```

## Features

1. **Selective install** - Install only needed skills
2. **Version pinning** - Lock to specific skill versions
3. **Custom skills** - Allow custom skill directories
4. **Auto-update** - Configurable update schedule
5. **Documentation** - Generate docs/skills/README.md

## Documentation Sync

Beyond skills, this module can also sync project documentation:

| Document | Description |
|----------|-------------|
| DESIGN.md | Complete design system (colors, typography, components) |
| docs/API.md | API conventions |
| docs/CONTRIBUTING.md | Contribution guidelines |
| docs/ARCHITECTURE.md | Architecture decisions |

Example DESIGN.md includes:
- Color palette (primary, neutral, semantic)
- Typography scale
- Component patterns
- Spacing system

## Setpoints

| Setpoint | Default | Range | Description |
|----------|---------|-------|-------------|
| skills_dir | docs/skills | - | Directory for skills |
| auto_update | false | [true, false] | Auto-update on schedule |
| update_schedule | weekly | [daily, weekly, monthly] | Update frequency |
| pin_versions | true | [true, false] | Lock versions |

## Integration Points

- **Requires**: storage, bus interfaces
- **Provides**: skills.installed, skills.registry
- **Hooks**: reconcile.sh, doctor.sh
- **Bus events**: skills.installed, skills.updated

## Target Directory Structure

```
repo/
├── docs/
│   └── skills/
│       ├── react-19.md
│       ├── nextjs-15.md
│       ├── prisma.md
│       ├── tailwind-4.md
│       └── README.md          # Index of all skills
├── .gitignore
└── DESIGN.md              # If installed
```

## Acceptance Criteria

1. ✅ Installs skills to docs/skills/
2. ✅ Version pinning works
3. ✅ Auto-update on schedule
4. ✅ README.md index generated
5. ✅ Conflicts resolved
6. ✅ Integration with heartbeat

## Why This Matters

Instead of each developer/AI learning framework quirks separately, the repository itself contains the conventions. Any AI agent (Claude, OpenCode, Cursor, etc.) can read `docs/skills/` and follow the same patterns.