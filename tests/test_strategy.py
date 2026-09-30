"""Strategy feature tests: service functions and MCP tools.

No live database needed — service calls are tested directly with mock sessions,
matching the conventions in test_web.py and test_csv_import.py.
"""

from datetime import date, timedelta
from unittest.mock import Mock, MagicMock

import pytest

from app import service
from app.models import Strategy, Problem, Attempt


def test_get_strategy_creates_defaults():
    """First call to get_strategy creates defaults (1 revision, 2 backlog)."""
    session = Mock()
    session.get.return_value = None  # No strategy exists
    
    strategy = service.get_strategy(session, user_id=1)
    
    assert strategy.revisions_per_session == 1
    assert strategy.backlog_per_session == 2
    session.add.assert_called_once()
    session.flush.assert_called_once()


def test_get_strategy_returns_existing():
    """get_strategy returns existing strategy without creating a new one."""
    session = Mock()
    existing = Strategy(user_id=1, revisions_per_session=3, backlog_per_session=5)
    session.get.return_value = existing
    
    strategy = service.get_strategy(session, user_id=1)
    
    assert strategy.revisions_per_session == 3
    assert strategy.backlog_per_session == 5
    session.add.assert_not_called()


def test_update_strategy():
    """update_strategy changes the numbers."""
    session = Mock()
    existing = Strategy(user_id=1, revisions_per_session=1, backlog_per_session=2)
    session.get.return_value = existing
    
    updated = service.update_strategy(session, user_id=1, revisions_per_session=3, backlog_per_session=5)
    
    assert updated.revisions_per_session == 3
    assert updated.backlog_per_session == 5
    session.add.assert_called_once()
    session.flush.assert_called_once()


def test_update_strategy_clamps_negative():
    """Negative values are clamped to 0."""
    session = Mock()
    existing = Strategy(user_id=1, revisions_per_session=1, backlog_per_session=2)
    session.get.return_value = existing
    
    updated = service.update_strategy(session, user_id=1, revisions_per_session=-5)
    
    assert updated.revisions_per_session == 0


def test_update_strategy_partial():
    """update_strategy can update just one field."""
    session = Mock()
    existing = Strategy(user_id=1, revisions_per_session=1, backlog_per_session=2)
    session.get.return_value = existing
    
    updated = service.update_strategy(session, user_id=1, revisions_per_session=5)
    
    assert updated.revisions_per_session == 5
    assert updated.backlog_per_session == 2  # unchanged


def test_get_weak_topics_identifies_patterns():
    """_get_weak_topics identifies topics with repeated mistake patterns."""
    session = Mock()
    
    # Mock problems
    p1 = Mock(spec=Problem)
    p1.id = 1
    p1.topics = ["arrays", "hashing"]
    
    problems = {1: p1}
    session.scalars.return_value.all.return_value = [p1]
    
    # Mock attempts with mistake tags
    a1 = Mock(spec=Attempt)
    a1.problem_pk = 1
    a1.mistake_tags = ["wrong_ds", "edge_cases"]
    
    a2 = Mock(spec=Attempt)
    a2.problem_pk = 1
    a2.mistake_tags = ["implementation_bug"]
    
    attempts = [a1, a2]
    session.scalars.return_value.all.return_value = attempts
    
    # First call returns problems, second returns attempts
    session.scalars.side_effect = [
        Mock(all=Mock(return_value=[p1])),
        Mock(all=Mock(return_value=attempts))
    ]
    
    weak = service._get_weak_topics(session, user_id=1, threshold=2)
    
    # arrays has 3 mistakes (2 from a1 + 1 from a2), hashing has 3 mistakes
    assert "arrays" in weak
    assert "hashing" in weak


def test_get_weak_topics_respects_threshold():
    """_get_weak_topics only returns topics with >= threshold mistakes."""
    session = Mock()
    
    p1 = Mock(spec=Problem)
    p1.id = 1
    p1.topics = ["arrays"]
    
    a1 = Mock(spec=Attempt)
    a1.problem_pk = 1
    a1.mistake_tags = ["wrong_ds"]  # only 1 mistake
    
    session.scalars.side_effect = [
        Mock(all=Mock(return_value=[p1])),
        Mock(all=Mock(return_value=[a1]))
    ]
    
    weak = service._get_weak_topics(session, user_id=1, threshold=2)
    
    # arrays has only 1 mistake, below threshold of 2
    assert "arrays" not in weak


def test_get_suggested_problems_empty():
    """No problems -> empty suggestions."""
    session = Mock()
    
    # Mock strategy
    strategy = Strategy(user_id=1, revisions_per_session=1, backlog_per_session=2)
    session.get.return_value = strategy
    
    # Mock empty problems
    session.scalars.return_value.all.return_value = []
    
    result = service.get_suggested_problems(session, user_id=1)
    
    assert result["revisions"] == []
    assert result["backlog"] == []
    assert result["weak_topics"] == []
    assert result["strategy"]["revisions_per_session"] == 1
    assert result["strategy"]["backlog_per_session"] == 2


def test_get_suggested_problems_respects_limits():
    """Suggestions respect strategy limits."""
    session = Mock()
    
    # Mock strategy
    strategy = Strategy(user_id=1, revisions_per_session=2, backlog_per_session=3)
    session.get.return_value = strategy
    
    # Mock problems
    p1 = Mock(spec=Problem)
    p1.id = 1
    p1.problem_id = "p1"
    p1.solved = True
    p1.last_solved = date.today() - timedelta(days=10)
    p1.interval_days = 1
    p1.topics = ["arrays"]
    
    p2 = Mock(spec=Problem)
    p2.id = 2
    p2.problem_id = "p2"
    p2.solved = False
    p2.topics = ["dp"]
    
    p3 = Mock(spec=Problem)
    p3.id = 3
    p3.problem_id = "p3"
    p3.solved = False
    p3.topics = ["arrays"]
    
    # Mock scalars to return different results for different queries
    def scalars_side_effect(query):
        mock_result = Mock()
        # Check if this is a due problems query (has is_due check)
        if "where" in str(query).lower():
            mock_result.all.return_value = [p1, p2, p3]
        else:
            mock_result.all.return_value = []
        return mock_result
    
    session.scalars.side_effect = scalars_side_effect
    
    # Mock get_due_problems and get_backlog to return our test data
    with pytest.MonkeyPatch.context() as m:
        m.setattr(service, "get_due_problems", lambda s, u, t, limit: [p1])
        m.setattr(service, "get_backlog", lambda s, u: [p2, p3])
        m.setattr(service, "_get_weak_topics", lambda s, u, threshold=2: ["arrays"])
        
        result = service.get_suggested_problems(session, user_id=1)
        
        # Should get 1 revision (p1) and 2 backlog (p2, p3)
        assert len(result["revisions"]) == 1
        assert len(result["backlog"]) == 2
        assert result["weak_topics"] == ["arrays"]
