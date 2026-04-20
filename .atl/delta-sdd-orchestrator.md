# SDD Orchestrator Module - Specification

## Overview

| Property | Value |
|----------|-------|
| **Module ID** | sdd-orchestrator |
| **Version** | 0.1.0 |
| **Category** | orchestration |
| **Description** | Orchestrates AI agents using Spec-Driven Development workflow, optimizing token usage |

## Problem

AI agents often:
- Skip specs and jump to code
- Use excessive tokens with verbose prompts
- Don't validate against specifications
- Create inconsistent implementations

## Solution

An SDD orchestrator that:
- Enforces spec → tasks → code → verify workflow
- Optimizes token usage with templates and caching
- Orchestrates sub-agents efficiently

## Token Optimization Strategies

| Strategy | Description | Savings |
|----------|------------|---------|
| Spec templates | Reuse prompt templates instead of full prompts | ~40% |
| Context compression | Compress historical context | ~30% |
| Delta specs | Only process what changed | ~50% |
| Caching | Cache common operations | Varies |
| Smart delegation | Route to appropriate sub-agent | ~20% |

## API Commands

```bash
# SDD workflow
sz sdd init          # Start new feature with spec
sz sdd propose      # Create proposal
sz sdd spec         # Write detailed spec
sz sdd tasks        # Break into tasks
sz sdd apply        # Implement tasks
sz sdd verify      # Validate against spec

# Token management
sz tokens status    # Show token usage
sz tokens compress # Optimize current context
sz tokens budget --max 100000  # Set budget

# Agent orchestration
sz delegate --agent code-reviewer --task "Review PR #123"
sz orchestrate --flow "spec → code → test → review"
```

## Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    SDD WORKFLOW                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌────────┐│
│  │  PROPOSE │───▶│   SPEC   │───▶│  TASKS   │───▶│ VERIFY ││
│  └─────────┘    └─────────┘    └─────────┘    └────────┘│
│       │                                                  │ │
│       │          ┌─────────┐                             │ │
│       └─────────▶│  APPLY  │─────────────────────────────┘│
│                  └─────────┘                             │
│                       │                                   │
│                       ▼                                   │
│                  ┌─────────┐                             │
│                  │ VERIFY  │───────(validate vs spec)     │
│                  └─────────┘                             │
└─────────────────────────────────────────────────────────────┘
```

## Sub-Agents

| Agent | Purpose | Triggers |
|-------|---------|---------|
| sdd-explore | Investigate codebase | Before spec |
| sdd-propose | Create change proposal | After explore |
| sdd-spec | Write detailed spec | After propose |
| sdd-tasks | Break into tasks | After spec |
| sdd-apply | Implement tasks | After tasks |
| sdd-verify | Validate against spec | After apply |

## Setpoints

| Setpoint | Default | Range | Description |
|----------|---------|-------|-------------|
| token_budget | 100000 | [10000, 500000] | Max tokens per cycle |
| max_retries | 2 | [0, 5] | LLM retry attempts |
| cache_enabled | true | [true, false] | Enable caching |
| auto_verify | true | [true, false] | Auto-verify after apply |

## Integration Points

- **Requires**: memory, bus, llm interfaces
- **Provides**: sdd.workflow, sdd.context
- **Hooks**: reconcile.sh, doctor.sh
- **Bus events**: sdd.spec.created, sdd.task.completed

## Acceptance Criteria

1. ✅ SDD workflow enforced
2. ✅ Token usage reduced by ~70%
3. ✅ Sub-agents orchestrated
4. ✅ Delta specs work
5. ✅ Template caching works
6. ✅ Verification against specs
7. ✅ Integration with heartbeat

## Token Budget Example

| Without Optimization | With Optimization |
|----------------------|------------------|
| Full spec per tick: ~50,000 | Delta specs only: ~25,000 |
| Daily: ~500,000 | Smart delegation: ~20,000 |
| | **Total: ~150,000 (~70% saved)** |