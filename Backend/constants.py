"""Constants used by automation selector services."""

# Priority field name variations used in AI-generated test case responses
# to normalize priority assignment behavior
PRIORITY_FIELD_VARIATIONS = (
    "priority",
    "Priority",
    "priorityAssignment",
    "priority_assignment",
    "priorityLevel",
    "priority_level",
)

automation_selector_manual_keywords = {
    "captcha",
    "exploratory",
    "visual",
    "usability",
    "subjective",
    "one-time",
    "ad hoc",
    "hardware",
    "biometric",
}

automation_selector_automate_keywords = {
    "regression",
    "login",
    "api",
    "repeat",
    "stable",
    "smoke",
    "data-driven",
    "critical",
    "workflow",
}

# Constants for test case generation
PRIORITY_LABELS = {
    "auto_risk": "Auto-assign by risk",
    "all_high": "All High",
    "manual": "Manual",
}

FORMAT_LABELS = {
    "standard": "Structured (ID, Steps, Expected)",
    "bdd": "BDD (Given/When/Then)",
}

COVERAGE_LABELS = {
    "smoke": "Smoke (Happy path only)",
    "standard": "Standard (Happy + Negative)",
    "comprehensive": "Comprehensive (All paths)",
}


MAX_RESULTS = 100
DEFAULT_TIMEOUT = 30

ACTION_SKIP = "SKIP"
ACTION_NEW = "NEW"

STATUS_SUCCESS = "SUCCESS"
APPROVED_STATUS = "approved"
FORMAT_STANDARD = "standard"
FORMAT_BDD = "bdd"
FORMAT_EXPLORATORY = "exploratory"
