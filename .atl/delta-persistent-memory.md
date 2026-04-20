# Persistent Memory Module - Specification

## Overview

| Property | Value |
|----------|-------|
| **Module ID** | persistent-memory |
| **Version** | 0.1.0 |
| **Category** | memory |
| **Description** | Persistent memory layer that survives repository restarts, server reboots, and team transitions. Transforms System Zero from stateless to stateful. |

## Problem

Currently, every time System Zero restarts:
- All context is lost
- AI has no memory of past decisions
- Each session starts from zero
- Team members joining mid-project are blind to past context

## Solution

A persistent memory layer using SQLite for MVP that:
- Auto-captures key decisions and learnings
- Survives restarts and reboots
- Provides search and context recovery
- Works with existing modules

## Data Schema

```sql
-- Core observation table
CREATE TABLE observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    type TEXT CHECK (type IN (
        'decision', 'architecture', 'bugfix', 
        'pattern', 'config', 'preference', 'discovery'
    )) NOT NULL,
    content TEXT NOT NULL,
    project TEXT,
    scope TEXT DEFAULT 'project',
    topic_key TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT,
    updated_at TIMESTAMP
);

-- Full-text search index
CREATE INDEX obs_search ON observations (title, content);

-- Topic upsert support
CREATE UNIQUE INDEX obs_topic ON observations (project, topic_key) WHERE topic_key IS NOT NULL;
```

## Storage Location

- SQLite database: `.sz/persistent-memory/memory.db`
- Entry point: `modules/persistent-memory/entry.py`

## API Commands

```bash
# Save observation (automatic or manual)
sz mem save --type bugfix --title "Fixed N+1 in UserList" \
  --content "Found missing .include(), added eager loading"

# Search memory
sz mem search "N+1"

# Get context for new session
sz mem context --project mi-proyecto --limit 20

# Topic updates (upsert)
sz mem update --topic architecture/auth-model \
  --content "Switched to JWT from sessions"
```

## Auto-Capture Triggers

The module automatically captures:

1. **Architecture Decisions**
   - Tool selection (DB, framework, etc.)
   - Pattern choices
   - Tradeoff decisions

2. **Bug Fixes**
   - Root cause analysis
   - Solution approach
   - Files affected

3. **Conventions**
   - Naming patterns
   - Structure decisions
   - Code organization

4. **User Preferences**
   - Style preferences
   - Testing approach
   - Documentation standards

5. **Discovered Context**
   - Codebase learnings
   - API patterns
   - Integration details

## Features

### 1. Automatic Capture
- Proactive save after key events
- Context-aware triggers
- No manual annotation required

### 2. Search
- Full-text search across all memories
- Filter by type, project, date
- Relevance ranking

### 3. Context Recovery
- Session summary on startup
- Recent context retrieval
- Topic-based loading

### 4. Integration
- Works with existing modules
- Compatible with heartbeat, bus, LLM
- No breaking changes

## Token Savings

With persistent context:
- Don't repeat questions → ~30% tokens saved
- Reuse shared understanding → ~20% tokens saved
- Smart context loading → ~40% tokens saved
- **Total: ~50-70% token reduction**

## Setpoints

| Setpoint | Default | Range | Description |
|----------|---------|-------|-------------|
| auto_capture | true | [true, false] | Auto-save important events |
| retention_days | 90 | [30, 365] | Days to keep observations |
| max_results | 20 | [5, 100] | Max search results |
| fts_enabled | true | [true, false] | Enable full-text search |

## Integration Points

- **Requires**: memory interface (S0 built-in)
- **Provides**: memory.persistent observation store
- **Hooks**: reconcile.sh, doctor.sh
- **Bus events**: observation.saved, observation.searched

## Acceptance Criteria

1. ✅ Survives repository restarts
2. ✅ Survives server reboots  
3. ✅ Auto-captures decisions and bugs
4. ✅ Full-text search works
5. ✅ Context recovery for new sessions
6. ✅ Topic upserts work correctly
7. ✅ Token usage reduced by ~50%
8. ✅ No breaking changes to existing modules

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| SQLite concurrency | Use WAL mode |
| Memory bloat | TTL cleanup (retention_days) |
| Search performance | FTS5 index |
| Data corruption | Backup on write |