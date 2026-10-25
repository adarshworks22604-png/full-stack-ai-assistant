from app.services.bug_ids import extract_bug_ids

P = r"\bBUG-\d{1,8}\b"


def test_extracts_unique_ids_in_order():
    assert extract_bug_ids("BUG-2 then BUG-1 and BUG-2 again", P) == ["BUG-2", "BUG-1"]


def test_ignores_lookalikes():
    assert extract_bug_ids("XBUG-1 bug-2 BUG- BUG-abc BUG-123456789", P) == []


def test_caps_the_number_of_ids():
    assert extract_bug_ids(" ".join(f"BUG-{i}" for i in range(20)), P, max_ids=3) == ["BUG-0", "BUG-1", "BUG-2"]


def test_no_ids_and_empty_text():
    assert extract_bug_ids("", P) == [] and extract_bug_ids("nothing here", P) == []


def test_pattern_is_configurable():
    assert extract_bug_ids("see JIRA-77 and ABC-5", r"\b[A-Z]{4}-\d+\b") == ["JIRA-77"]
