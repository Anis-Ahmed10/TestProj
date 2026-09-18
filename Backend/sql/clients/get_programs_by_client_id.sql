SELECT
    id,
    name,
    description
FROM programmes
WHERE client_id = :client_id
AND status != 'archived'
ORDER BY created_at DESC, name ASC;
