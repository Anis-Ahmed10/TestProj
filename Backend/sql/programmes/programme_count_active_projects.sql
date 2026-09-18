SELECT COUNT(*) AS active_projects_count
FROM projects
WHERE programme_id = :programme_id
  AND LOWER(status) = 'active';
