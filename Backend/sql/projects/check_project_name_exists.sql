SELECT EXISTS (
    SELECT 1
    FROM projects
    WHERE programme_id = :programme_id
      AND LOWER(name) = LOWER(:name)
    AND status != 'archived'
) AS project_exists;
