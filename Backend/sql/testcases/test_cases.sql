INSERT INTO test_cases (
    id,
    user_story_id,
    title,
    priority,
    test_case_type,
    tags,
    jira_key,
    test_data,
    created_by
)
VALUES (
    :id,
    :user_story_id,
    :title,
    :priority,
    :test_case_type,
    :tags,
    :jira_key,
    CAST(:test_data AS jsonb),
    :created_by
);
