"""Unit tests for app/database/duplicate_checker_jira.py — 100% coverage."""

from __future__ import annotations

from app.database.duplicate_checker_jira import (
    DuplicateAction,
    DuplicateCheckResult,
    _content_hash,
    _normalise,
    check_story_duplicate,
)

# ──────────────────────────────────────────────────────────────────
# _normalise
# ──────────────────────────────────────────────────────────────────


class TestNormalise:
    def test_strips_and_lowercases(self):
        assert _normalise("  Hello World  ") == "hello world"

    def test_empty_string_returns_empty(self):
        assert _normalise("") == ""

    def test_none_returns_empty(self):
        assert _normalise(None) == ""

    def test_already_lowercase(self):
        assert _normalise("abc") == "abc"

    def test_mixed_case_with_whitespace(self):
        assert _normalise("  ABC  ") == "abc"


# ──────────────────────────────────────────────────────────────────
# _content_hash
# ──────────────────────────────────────────────────────────────────


class TestContentHash:
    def test_combines_description_and_ac(self):
        result = _content_hash("Desc", "AC")
        assert result == "desc||ac"

    def test_empty_inputs(self):
        assert _content_hash("", "") == "||"

    def test_whitespace_trimmed(self):
        assert _content_hash("  Desc  ", "  AC  ") == "desc||ac"

    def test_different_descriptions_produce_different_hashes(self):
        assert _content_hash("A", "AC") != _content_hash("B", "AC")

    def test_different_ac_produces_different_hashes(self):
        assert _content_hash("Desc", "A") != _content_hash("Desc", "B")

    def test_same_inputs_produce_same_hash(self):
        assert _content_hash("X", "Y") == _content_hash("X", "Y")


# ──────────────────────────────────────────────────────────────────
# DuplicateCheckResult dataclass
# ──────────────────────────────────────────────────────────────────


class TestDuplicateCheckResult:
    def test_defaults_are_none(self):
        result = DuplicateCheckResult(action=DuplicateAction.INSERT)
        assert result.rename_key is None
        assert result.rename_title is None
        assert result.existing_id is None

    def test_all_fields_set(self):
        result = DuplicateCheckResult(
            action=DuplicateAction.RENAME,
            rename_key="ST-1_1",
            rename_title="Story_1",
            existing_id="some-uuid",
        )
        assert result.action == DuplicateAction.RENAME
        assert result.rename_key == "ST-1_1"
        assert result.rename_title == "Story_1"
        assert result.existing_id == "some-uuid"


# ──────────────────────────────────────────────────────────────────
# DuplicateAction enum
# ──────────────────────────────────────────────────────────────────


class TestDuplicateAction:
    def test_values(self):
        assert DuplicateAction.INSERT == "insert"
        assert DuplicateAction.UPDATE == "update"
        assert DuplicateAction.SKIP == "skip"
        assert DuplicateAction.RENAME == "rename"

    def test_is_str(self):
        assert isinstance(DuplicateAction.INSERT, str)


# ──────────────────────────────────────────────────────────────────
# check_story_duplicate — helper builders
# ──────────────────────────────────────────────────────────────────


def _existing_by_key(story_key, title="Title", description="Desc", ac="AC", row_id="uuid-1"):
    return {
        story_key: {
            "id": row_id,
            "title": title,
            "description": description,
            "acceptance_criteria": ac,
        }
    }


def _existing_by_title(title):
    return {title.strip().lower(): [{"id": "uuid-1", "title": title}]}


# ──────────────────────────────────────────────────────────────────
# Case 1: SKIP — same key AND same content
# ──────────────────────────────────────────────────────────────────


class TestCheckStoryDuplicateSkip:
    def test_exact_duplicate_returns_skip(self):
        result = check_story_duplicate(
            story_key="ST-1",
            title="Title",
            description="Desc",
            acceptance_criteria="AC",
            existing_by_key=_existing_by_key("ST-1", description="Desc", ac="AC"),
            existing_by_title={},
        )
        assert result.action == DuplicateAction.SKIP
        assert result.existing_id == "uuid-1"

    def test_skip_with_whitespace_differences_normalised(self):
        """Content is normalised before comparison, so whitespace/case doesn't matter."""
        result = check_story_duplicate(
            story_key="ST-1",
            title="Title",
            description="  DESC  ",
            acceptance_criteria="  ac  ",
            existing_by_key=_existing_by_key("ST-1", description="desc", ac="ac"),
            existing_by_title={},
        )
        assert result.action == DuplicateAction.SKIP

    def test_skip_with_empty_description_and_ac(self):
        result = check_story_duplicate(
            story_key="ST-1",
            title="Title",
            description="",
            acceptance_criteria="",
            existing_by_key=_existing_by_key("ST-1", description="", ac=""),
            existing_by_title={},
        )
        assert result.action == DuplicateAction.SKIP

    def test_skip_existing_row_missing_description_treated_as_empty(self):
        existing = {"ST-1": {"id": "uuid-1", "title": "T"}}  # no description/ac keys
        result = check_story_duplicate(
            story_key="ST-1",
            title="T",
            description="",
            acceptance_criteria="",
            existing_by_key=existing,
            existing_by_title={},
        )
        assert result.action == DuplicateAction.SKIP


# ──────────────────────────────────────────────────────────────────
# Case 2: UPDATE — same key, different content
# ──────────────────────────────────────────────────────────────────


class TestCheckStoryDuplicateUpdate:
    def test_same_key_different_description_returns_update(self):
        result = check_story_duplicate(
            story_key="ST-1",
            title="Title",
            description="New Description",
            acceptance_criteria="AC",
            existing_by_key=_existing_by_key("ST-1", description="Old Description", ac="AC"),
            existing_by_title={},
        )
        assert result.action == DuplicateAction.UPDATE
        assert result.existing_id == "uuid-1"

    def test_same_key_different_ac_returns_update(self):
        result = check_story_duplicate(
            story_key="ST-1",
            title="Title",
            description="Desc",
            acceptance_criteria="New AC",
            existing_by_key=_existing_by_key("ST-1", description="Desc", ac="Old AC"),
            existing_by_title={},
        )
        assert result.action == DuplicateAction.UPDATE

    def test_same_key_both_fields_changed_returns_update(self):
        result = check_story_duplicate(
            story_key="ST-1",
            title="Title",
            description="New Desc",
            acceptance_criteria="New AC",
            existing_by_key=_existing_by_key("ST-1", description="Old Desc", ac="Old AC"),
            existing_by_title={},
        )
        assert result.action == DuplicateAction.UPDATE

    def test_same_key_title_only_changed_returns_update(self):
        """An inline edit that only changes the title (description/AC unchanged)
        must be detected as UPDATE, not silently SKIPped."""
        result = check_story_duplicate(
            story_key="ST-1",
            title="New Title",
            description="Desc",
            acceptance_criteria="AC",
            existing_by_key=_existing_by_key(
                "ST-1", title="Old Title", description="Desc", ac="AC"
            ),
            existing_by_title={},
        )
        assert result.action == DuplicateAction.UPDATE
        assert result.existing_id == "uuid-1"

    def test_same_key_title_case_and_whitespace_only_differ_returns_skip(self):
        """Title comparison is normalised the same way content is — pure
        whitespace/case differences must not trigger a false UPDATE."""
        result = check_story_duplicate(
            story_key="ST-1",
            title="  TITLE  ",
            description="Desc",
            acceptance_criteria="AC",
            existing_by_key=_existing_by_key("ST-1", title="title", description="Desc", ac="AC"),
            existing_by_title={},
        )
        assert result.action == DuplicateAction.SKIP

    def test_update_existing_id_is_returned(self):
        result = check_story_duplicate(
            story_key="ST-1",
            title="T",
            description="Changed",
            acceptance_criteria="",
            existing_by_key=_existing_by_key(
                "ST-1", description="Original", ac="", row_id="my-uuid"
            ),
            existing_by_title={},
        )
        assert result.existing_id == "my-uuid"


# ──────────────────────────────────────────────────────────────────
# Case 3: RENAME — same title, different key
# ──────────────────────────────────────────────────────────────────


class TestCheckStoryDuplicateRename:
    def test_same_title_different_key_returns_rename(self):
        result = check_story_duplicate(
            story_key="ST-NEW",
            title="Shared Title",
            description="Desc",
            acceptance_criteria="AC",
            existing_by_key={},
            existing_by_title=_existing_by_title("Shared Title"),
        )
        assert result.action == DuplicateAction.RENAME
        assert result.rename_key == "ST-NEW_1"
        assert result.rename_title == "Shared Title_1"

    def test_rename_suffix_increments_when_key_already_exists(self):
        """_1 is taken in existing_by_key → should return _2."""
        existing_by_key = {
            "ST-NEW_1": {"id": "x", "title": "T", "description": "", "acceptance_criteria": ""}
        }
        result = check_story_duplicate(
            story_key="ST-NEW",
            title="Shared Title",
            description="D",
            acceptance_criteria="A",
            existing_by_key=existing_by_key,
            existing_by_title=_existing_by_title("Shared Title"),
        )
        assert result.rename_key == "ST-NEW_2"
        assert result.rename_title == "Shared Title_2"

    def test_rename_suffix_increments_multiple_times(self):
        """_1 and _2 both taken → should return _3."""
        existing_by_key = {
            "ST-NEW_1": {"id": "a", "title": "T", "description": "", "acceptance_criteria": ""},
            "ST-NEW_2": {"id": "b", "title": "T", "description": "", "acceptance_criteria": ""},
        }
        result = check_story_duplicate(
            story_key="ST-NEW",
            title="Shared Title",
            description="D",
            acceptance_criteria="A",
            existing_by_key=existing_by_key,
            existing_by_title=_existing_by_title("Shared Title"),
        )
        assert result.rename_key == "ST-NEW_3"

    def test_rename_uses_normalised_title_for_lookup(self):
        """Title match is case/whitespace-insensitive."""
        result = check_story_duplicate(
            story_key="ST-NEW",
            title="  SHARED TITLE  ",
            description="D",
            acceptance_criteria="A",
            existing_by_key={},
            existing_by_title={"shared title": [{"id": "x"}]},
        )
        assert result.action == DuplicateAction.RENAME

    def test_rename_no_existing_id_set(self):
        result = check_story_duplicate(
            story_key="ST-NEW",
            title="Title",
            description="D",
            acceptance_criteria="A",
            existing_by_key={},
            existing_by_title=_existing_by_title("Title"),
        )
        assert result.existing_id is None


# ──────────────────────────────────────────────────────────────────
# Case 4: INSERT — brand new
# ──────────────────────────────────────────────────────────────────


class TestCheckStoryDuplicateInsert:
    def test_brand_new_story_returns_insert(self):
        result = check_story_duplicate(
            story_key="BRAND-NEW",
            title="Brand New Title",
            description="D",
            acceptance_criteria="A",
            existing_by_key={},
            existing_by_title={},
        )
        assert result.action == DuplicateAction.INSERT

    def test_insert_has_no_rename_info(self):
        result = check_story_duplicate(
            story_key="NEW-1",
            title="T",
            description="",
            acceptance_criteria="",
            existing_by_key={},
            existing_by_title={},
        )
        assert result.rename_key is None
        assert result.rename_title is None
        assert result.existing_id is None

    def test_empty_existing_dicts(self):
        result = check_story_duplicate(
            story_key="X",
            title="X",
            description="",
            acceptance_criteria="",
            existing_by_key={},
            existing_by_title={},
        )
        assert result.action == DuplicateAction.INSERT

    def test_title_collision_check_does_not_fire_when_title_empty(self):
        """Empty title normalises to '' — only triggers rename if
        '' is a key in existing_by_title."""
        result = check_story_duplicate(
            story_key="NEW",
            title="",
            description="",
            acceptance_criteria="",
            existing_by_key={},
            existing_by_title={},
        )
        assert result.action == DuplicateAction.INSERT
