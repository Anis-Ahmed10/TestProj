SELECT
    tc.status AS status,
    COUNT(*) AS status_count
FROM test_cases tc
JOIN user_stories us ON us.story_key = tc.user_story_id
JOIN epics e ON e.epic_key = us.epic_id
WHERE e.project_id = :project_id
GROUP BY tc.status
