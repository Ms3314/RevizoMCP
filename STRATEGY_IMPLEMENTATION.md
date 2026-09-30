# Strategy Feature Implementation

## Overview
Implemented a session strategy feature that allows users to set preferences for how many revision problems (SRS-based) and backlog problems (weak/unsolved topics) they want to solve per session. The MCP server uses these preferences when suggesting problems.

## What Was Built

### 1. Database Model (`app/models.py`)
- Added `Strategy` table with:
  - `user_id` (primary key)
  - `revisions_per_session` (default: 1)
  - `backlog_per_session` (default: 2)

### 2. Service Layer (`app/service.py`)
Added three new functions:

- **`get_strategy(session, user_id)`**: Retrieves user's strategy, creating defaults if not set
- **`update_strategy(session, user_id, revisions_per_session, backlog_per_session)`**: Updates strategy preferences
- **`get_suggested_problems(session, user_id, today)`**: Fetches curated problem list based on strategy:
  - Revisions: due problems from SRS ladder (spaced repetition)
  - Backlog: unsolved problems prioritized by weak topics (repeated mistakes)
- **`_get_weak_topics(session, user_id, threshold)`**: Identifies topics with repeated mistake patterns

### 3. MCP Tools (`app/mcp_server.py`)
Added two new tools:

- **`get_suggested_problems()`**: Returns curated list based on user's strategy
  - Reads strategy from DB
  - Fetches N due problems (revisions)
  - Identifies weak topics from mistake tags
  - Fetches M backlog problems (prioritizing weak topics)
  - Returns: strategy settings, revision list, backlog list, weak topics

- **`update_strategy(revisions_per_session, backlog_per_session)`**: Updates user's session preferences
  - Validates inputs (clamps negatives to 0)
  - Persists to database
  - Returns updated strategy

### 4. Coach Playbook (`app/prompts/playbook.py`)
Added scenario 14: "Strategy-based session planning"
- Teaches the coach when to use `get_suggested_problems`
- Explains how to present the curated plan
- Shows how to update strategy when user requests changes

### 5. Tests (`tests/test_strategy.py`)
Added 9 comprehensive tests:
- Default strategy creation
- Strategy retrieval and updates
- Negative value clamping
- Partial updates
- Weak topic identification
- Threshold respect
- Empty suggestions handling
- Strategy limit respect

## How It Works

### User Flow
1. User asks: "What should I solve today?"
2. Coach calls `get_suggested_problems()`
3. System reads user's strategy (default: 1 revision + 2 backlog)
4. Fetches due problems from SRS ladder
5. Identifies weak topics (topics with ≥2 mistake occurrences)
6. Fetches backlog problems, prioritizing weak topics
7. Returns curated list with context

### Example Response
```json
{
  "strategy": {
    "revisions_per_session": 2,
    "backlog_per_session": 3
  },
  "revisions": [
    {
      "problem_id": "Two Sum",
      "difficulty": "easy",
      "watch_out": "Watch out - you last failed with edge_cases"
    }
  ],
  "backlog": [
    {
      "problem_id": "Coin Change",
      "topics": ["dp"],
      "reason": "weak topic"
    }
  ],
  "weak_topics": ["dp", "arrays"]
}
```

### Strategy Updates
User: "I want 2 revisions and 3 new problems per session"
Coach: calls `update_strategy(revisions_per_session=2, backlog_per_session=3)`

## Key Design Decisions

1. **No Web UI**: Strategy is managed via MCP tools only (set once, rarely changed)
2. **Weak Topic Detection**: Topics with ≥2 mistake occurrences are flagged as weak
3. **Backlog Prioritization**: Problems from weak topics are suggested first
4. **Default Values**: 1 revision + 2 backlog (conservative starting point)
5. **No Foreign Key**: Strategy table doesn't enforce user existence (created on-demand)

## Testing
All 61 tests pass:
- 52 existing tests (web, CSV import, etc.)
- 9 new strategy tests

## Files Modified
- `app/models.py`: Added Strategy model
- `app/service.py`: Added strategy functions
- `app/mcp_server.py`: Added MCP tools
- `app/prompts/playbook.py`: Added scenario 14
- `tests/test_strategy.py`: New test file (9 tests)

## Usage Examples

### Setting Strategy
```
User: "I want to solve 2 revisions and 3 new problems each session"
Coach: calls update_strategy(revisions_per_session=2, backlog_per_session=3)
```

### Getting Suggestions
```
User: "What should I solve today?"
Coach: calls get_suggested_problems()
Coach: "Your strategy: 2 revisions + 3 from backlog. Today: [revision 1] (due, watch out for edge_cases), [revision 2] (due). Then: [backlog 1] (weak topic: dp), [backlog 2] (weak topic: arrays), [backlog 3] (never attempted)."
```

## Future Enhancements (Not Implemented)
- Dashboard widget showing current strategy
- Topic-specific strategies (e.g., "focus on DP this week")
- Difficulty-based filtering
- Time-based strategies (e.g., "30-minute session")
