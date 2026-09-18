"""Unit tests for app/utils/jira_parser.py — 100% coverage."""

from app.utils.jira_parser import (
    _collect_texts,
    extract_acceptanceCriteria,
    extract_description,
)

# ──────────────────────────────────────────────────────────────────
# extract_description
# ──────────────────────────────────────────────────────────────────


class TestExtractDescription:
    def test_none_returns_no_description(self):
        assert extract_description(None) == "No Description"

    def test_empty_dict_returns_no_description(self):
        assert extract_description({}) == "No Description"

    def test_empty_content_list_returns_no_description(self):
        assert extract_description({"content": []}) == "No Description"

    def test_string_input_valid(self):
        assert extract_description("  Plain text description  ") == "Plain text description"

    def test_string_input_blank(self):
        assert extract_description("   ") == "No Description"

    def test_content_with_no_text_nodes_returns_no_description(self):
        field = {
            "content": [
                {"content": [{"type": "hardBreak"}]},
            ]
        }
        assert extract_description(field) == "No Description"

    def test_single_paragraph_single_text(self):
        field = {"content": [{"content": [{"type": "text", "text": "Hello world"}]}]}
        assert extract_description(field) == "Hello world"

    def test_multiple_paragraphs_joined_with_space(self):
        field = {
            "content": [
                {"content": [{"type": "text", "text": "First"}]},
                {"content": [{"type": "text", "text": "Second"}]},
            ]
        }
        assert extract_description(field) == "First Second"

    def test_nested_bullet_list_adf(self):
        field = {
            "type": "doc",
            "content": [
                {
                    "type": "bulletList",
                    "content": [
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": "Item 1"}],
                                }
                            ],
                        },
                        {
                            "type": "listItem",
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": "Item 2"}],
                                }
                            ],
                        },
                    ],
                }
            ],
        }
        assert extract_description(field) == "Item 1 Item 2"

    def test_list_input_direct(self):
        field = [
            {"type": "text", "text": "Direct"},
            {"type": "text", "text": "List"},
        ]
        assert extract_description(field) == "Direct List"

    def test_multiple_text_nodes_in_one_paragraph(self):
        field = {
            "content": [
                {
                    "content": [
                        {"type": "text", "text": "A"},
                        {"type": "text", "text": "B"},
                    ]
                }
            ]
        }
        assert extract_description(field) == "A B"

    def test_inner_content_missing_text_key_is_skipped(self):
        field = {
            "content": [
                {
                    "content": [
                        {"type": "hardBreak"},  # no "text" key
                        {"type": "text", "text": "OK"},
                    ]
                }
            ]
        }
        assert extract_description(field) == "OK"

    def test_exception_during_parsing_returns_no_description(self):
        class BadDict(dict):
            def get(self, *args, **kwargs):
                raise RuntimeError("crash")

        assert extract_description(BadDict({"key": "val"})) == "No Description"

    def test_outer_item_missing_content_key(self):
        field = {"content": [{"type": "paragraph"}]}
        assert extract_description(field) == "No Description"

    def test_collect_texts_non_dict_non_list(self):
        texts = []
        _collect_texts(12345, texts)
        assert texts == []


# ──────────────────────────────────────────────────────────────────
# extract_acceptanceCriteria
# ──────────────────────────────────────────────────────────────────


class TestExtractAcceptanceCriteria:
    def test_non_dict_fields_returns_default(self):
        assert extract_acceptanceCriteria(None) == "No Acceptance Criteria"
        assert extract_acceptanceCriteria([]) == "No Acceptance Criteria"

    def test_no_acceptance_field_returns_default(self):
        assert extract_acceptanceCriteria({"summary": "foo"}) == "No Acceptance Criteria"

    def test_acceptance_field_none_value_returns_default(self):
        assert extract_acceptanceCriteria({"acceptanceCriteria": None}) == "No Acceptance Criteria"

    def test_acceptance_field_empty_string_returns_default(self):
        assert extract_acceptanceCriteria({"acceptanceCriteria": ""}) == "No Acceptance Criteria"

    def test_acceptance_field_string_value(self):
        assert extract_acceptanceCriteria({"acceptanceCriteria": "Must work"}) == "Must work"

    def test_acceptance_field_dict_value_calls_extract_description(self):
        field = {
            "acceptanceCriteria": {
                "content": [{"content": [{"type": "text", "text": "Parsed AC"}]}]
            }
        }
        assert extract_acceptanceCriteria(field) == "Parsed AC"

    def test_acceptance_field_list_value_calls_extract_description(self):
        field = {"acceptanceCriteria": [{"type": "text", "text": "AC from list"}]}
        assert extract_acceptanceCriteria(field) == "AC from list"

    def test_field_name_case_insensitive_match(self):
        assert (
            extract_acceptanceCriteria({"customfield_acceptance_criteria": "AC text"}) == "AC text"
        )

    def test_multiple_fields_first_acceptance_wins(self):
        fields = {
            "summary": "ignore",
            "acceptance_notes": "First AC",
            "acceptance_criteria": "Second AC",
        }
        result = extract_acceptanceCriteria(fields)
        assert result == "First AC"

    def test_acceptance_field_integer_value_converted_to_str(self):
        assert extract_acceptanceCriteria({"acceptance_score": 42}) == "42"
