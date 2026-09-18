UPDATE test_cases
            SET jira_key = :jira_key
            WHERE user_story_id = :user_story_id
            AND title = :tc_title
