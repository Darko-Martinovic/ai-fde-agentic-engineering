from backend import diffs

TEXT = "\n".join(f"Line {n}." for n in range(1, 21))


def lines(hunk):
    return [(line.kind, line.text) for line in hunk.lines]


def test_one_line_changed_is_one_removed_and_one_added_with_two_around_it():
    [hunk] = diffs.changes(TEXT, TEXT.replace("Line 10.", "Line ten."))
    assert lines(hunk) == [
        ("context", "Line 8."),
        ("context", "Line 9."),
        ("removed", "Line 10."),
        ("added", "Line ten."),
        ("context", "Line 11."),
        ("context", "Line 12."),
    ]
    assert hunk.heading.startswith("@@")


def test_two_changes_far_apart_are_two_stretches():
    changed = TEXT.replace("Line 2.", "Line two.").replace("Line 18.", "Line 18!")
    first, second = diffs.changes(TEXT, changed)
    assert ("added", "Line two.") in lines(first)
    assert ("added", "Line 18!") in lines(second)
    assert diffs.counted([first, second], "added") == 2
    assert diffs.counted([first, second], "removed") == 2


def test_the_same_text_has_no_changes():
    assert diffs.changes(TEXT, TEXT) == []
