"""Guard tests for the MCP prompt sources in app/prompts."""

from app.prompts import INSTRUCTIONS, SCENARIO_PLAYBOOK


def test_playbook_is_assembled_into_instructions():
    assert "SCENARIO PLAYBOOK" in INSTRUCTIONS
    assert "add_problem" in SCENARIO_PLAYBOOK
    assert "record_attempt" in SCENARIO_PLAYBOOK


def test_playbook_covers_both_calls_for_a_new_solved_problem():
    # the key scenario: new problem + user already solved it -> BOTH tools, add first
    idx_add = SCENARIO_PLAYBOOK.find("add_problem")
    idx_record = SCENARIO_PLAYBOOK.find("record_attempt")
    assert -1 not in (idx_add, idx_record)
    assert idx_add < idx_record


def test_leetcode_cookie_is_never_requested_in_chat():
    # credentials are entered once in the signed-in dashboard, never passed in prompt/tool args
    assert "get_leetcode_submissions" not in INSTRUCTIONS
    assert "NEVER ask them to paste their LEETCODE_SESSION cookie into chat" in INSTRUCTIONS
    assert "/app/leetcode" in SCENARIO_PLAYBOOK
    assert "import_all_leetcode" in SCENARIO_PLAYBOOK


def test_playbook_handles_missing_problem_link():
    # no link given -> derive from the lc-<slug> id; never fabricate URLs
    assert "DERIVE" in SCENARIO_PLAYBOOK
    assert "https://leetcode.com/problems/coin-change/" in SCENARIO_PLAYBOOK
    assert "Never fabricate a URL" in SCENARIO_PLAYBOOK


def test_scope_rule_governs_greetings():
    # coach stays quiet on unrelated chat; ritual starts on revision intent
    assert "SCOPE:" in INSTRUCTIONS
    assert "NOT on bare greetings" in INSTRUCTIONS


def test_scenario_1_is_the_revision_ritual():
    # greeting offer path + full ritual with same-turn recording
    assert "Session openings" in SCENARIO_PLAYBOOK
    assert "revision_stats + get_due_problems" in SCENARIO_PLAYBOOK
    assert "IN THIS TURN" in SCENARIO_PLAYBOOK
    assert "never batch" in SCENARIO_PLAYBOOK


def test_duplicate_problem_gets_graceful_redirect():
    # problem already tracked + user starts it -> reframe, never raw error
    assert "IF get_problem SHOWS IT EXISTS" in SCENARIO_PLAYBOOK
    assert "never surface the raw error" in SCENARIO_PLAYBOOK


def test_backdated_scenario_annotates_real_date():
    # Option A: record today, note the real date in mistakes - no date param
    assert "recording today" in SCENARIO_PLAYBOOK
    assert "never invent a date the user didn't give" in SCENARIO_PLAYBOOK
    assert "oldest first" in SCENARIO_PLAYBOOK


def test_vague_failure_scenario_maps_tags_and_asks_once():
    # multi-tag mapping + verbatim quoting + ask-once-on-empty rule
    assert "VERBATIM" in SCENARIO_PLAYBOOK
    assert 'mistake_tags=["complexity_tle", "edge_cases"]' in SCENARIO_PLAYBOOK
    assert "always ask once" in SCENARIO_PLAYBOOK
    assert "never invent a tag" in SCENARIO_PLAYBOOK


def test_sync_scenario_never_guesses_username():
    # first sync: ask for the handle with where-to-find-it, never infer it;
    # a wrong handle imports a stranger's history and there is no delete tool
    assert "NEVER guess it from their email" in SCENARIO_PLAYBOOK
    assert "leetcode.com/u/<handle>" in SCENARIO_PLAYBOOK
    assert "no delete tool" in SCENARIO_PLAYBOOK
    assert "if that's not you, say so" in SCENARIO_PLAYBOOK


def test_help_discipline_scenario():
    # never hand the answer; hint ladder; help logging; external = not a solve
    assert "NEVER write the solution" in SCENARIO_PLAYBOOK
    assert "the SMALLEST next step" in SCENARIO_PLAYBOOK
    assert "LOG EVERY HELP, BOTH SOURCES" in SCENARIO_PLAYBOOK
    assert "EXTERNAL SOLUTIONS ARE NOT SOLVES" in SCENARIO_PLAYBOOK
    assert "independence score" in SCENARIO_PLAYBOOK


def test_no_delete_tool_caveat():
    # deletion is unsupported - say so plainly, never fake it with other tools
    assert "NOT SUPPORTED: there is no delete/reset tool" in SCENARIO_PLAYBOOK


def test_starting_out_onboarding_scenario():
    # empty tracker -> onboarding: suggest sync (scenario 10) or first add,
    # then pivot into the ritual - never a dead end
    assert "Starting out - the tracker is EMPTY" in SCENARIO_PLAYBOOK
    assert "Most people start with the sync" in SCENARIO_PLAYBOOK
    assert "scenario 13" in SCENARIO_PLAYBOOK  # scenario 1 cross-reference
