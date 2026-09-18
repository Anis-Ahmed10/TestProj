SELECT
                title,
                test_data
            FROM test_cases
            WHERE user_story_id = :usid
