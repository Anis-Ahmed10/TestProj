SELECT
    id,
    client_id,
    name,
    description,
    status,
    created_at,
    last_modified
FROM programmes
WHERE id = :programme_id
  AND status != 'archived'
LIMIT 1;
