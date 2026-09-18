SELECT EXISTS (
    SELECT 1
    FROM clients
    WHERE LOWER(name) = LOWER(:name)
      AND (:exclude_name IS NULL OR name != :exclude_name)
      AND status != 'archived'
) AS client_exists;
