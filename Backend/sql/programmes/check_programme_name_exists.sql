SELECT EXISTS (
    SELECT 1
    FROM programmes
    WHERE client_id = :client_id
      AND LOWER(name) = LOWER(:name)
  AND status != 'archived'
) AS programme_exists;
