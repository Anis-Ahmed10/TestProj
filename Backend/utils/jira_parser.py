from typing import Any, Optional, Union


def _collect_texts(node: Any, texts: list[str]) -> None:
    if isinstance(node, dict):
        text = node.get("text")
        if text and isinstance(text, str):
            texts.append(text)
        content = node.get("content")
        if isinstance(content, list):
            for child in content:
                _collect_texts(child, texts)
    elif isinstance(node, list):
        for item in node:
            _collect_texts(item, texts)


def extract_description(field: Optional[Union[dict, list, str]]) -> str:
    if not field:
        return "No Description"

    if isinstance(field, str):
        cleaned = field.strip()
        return cleaned if cleaned else "No Description"

    try:
        texts: list[str] = []
        _collect_texts(field, texts)

        if not texts:
            return "No Description"

        return " ".join(texts)

    except Exception:
        return "No Description"


def extract_acceptanceCriteria(fields: Optional[dict]) -> str:
    """
    Dynamically find acceptance criteria fields from Jira payload.
    """
    if not fields or not isinstance(fields, dict):
        return "No Acceptance Criteria"

    for field_name, value in fields.items():
        if "acceptance" in field_name.lower():
            if value:
                if isinstance(value, (dict, list)):
                    return extract_description(value)

                return str(value)

    return "No Acceptance Criteria"
