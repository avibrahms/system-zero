# Approval Gate Module - Specification

## Overview

| Property | Value |
|----------|-------|
| **Module ID** | approval-gate |
| **Version** | 0.1.0 |
| **category** | security |
| **Description** | Requires human approval before executing changes in the repository |

## Problem

Currently:
- AI agents can make autonomous changes without user confirmation
- No safety net for production systems
- Learning environments need oversight
- Safety-critical code requires human review

## Solution

An approval gate that:
- Intercepts proposed changes
- Shows proposal details
- Waits for user decision
- Logs all decisions

## API Commands

```bash
# Approval workflow
sz approval list          # List pending proposals
sz approval approve 1   # Approve proposal #1
sz approval reject 2      # Reject proposal #2
sz approval request 3    # Request more info

# Configuration
sz config set approval.mode approve
```

## Configuration Modes

| Mode | Behavior |
|------|----------|
| manual | No automatic execution |
| approve | Propose and wait for approval |
| auto-low | Auto-apply low-risk changes |
| auto-all | All automatic (dangerous) |

## Proposal Format

```markdown
# Proposal #N

## What
[Description of changes]

## Why
[Reason for changes]

## Files Affected
- src/app.ts
- src/utils.ts

## Risk Level
- LOW / MEDIUM / HIGH

## Diff Summary
+10 lines -5 lines
```

## Module Structure

```
modules/approval-gate/
├── module.yaml
├── entry.py               # Main approval logic
├── approve.sh
├── templates/
│   └── proposal.md
├── reconcile.sh
└── doctor.sh
```

## Features

1. **Change Interception**
   - Before any modification
   - Present proposal to user
   - Show what, why, files, risk

2. **Decision Tracking**
   - Approve / Reject / Request Info
   - Log all decisions
   - History maintained

3. **Risk Assessment**
   - LOW: Documentation, tests
   - MEDIUM: Refactoring, small fixes
   - HIGH: Production changes, migrations

4. **Notification**
   - Before changes applied
   - Configurable channels
   - Integration with bus

## Setpoints

| Setpoint | Default | Range | Description |
|----------|---------|-------|-------------|
| mode | approve | [manual, approve, auto-low, auto-all] | Approval mode |
| notify_before | true | [true, false] | Notify before changes |
| auto_low_threshold | low | [low, medium] | Auto-apply threshold |
| max_pending | 10 | [1, 50] | Max pending proposals |

## Integration Points

- **Requires**: bus interface
- **Provides**: approval.required, approval.decision
- **Hooks**: reconcile.sh, doctor.sh
- **Bus events**: approval.requested, approval.decided

## Decision Log

```json
{
  "id": 1,
  "proposal": {...},
  "decision": "approved",
  "decided_by": "user@example.com",
  "decided_at": "2026-04-17T10:30:00Z",
  "comment": "LGTM!"
}
```

## Acceptance Criteria

1. ✅ Intercepts proposed changes
2. ✅ Shows proposal details
3. ✅ Approve/Reject/Request Info works
4. ✅ Decision history maintained
5. ✅ Risk assessment works
6. ✅ Integration with bus
7. ✅ Mode configuration works

## Use Cases

| Use Case | Mode |
|---------|------|
| Production e-commerce | approve |
| Learning/experimentation | auto-low |
| Safety-critical systems | manual |
| Development | auto-all |