SELECT
    id,
    name,
    industry,
    location,
    contact,
    status,
    manager_id,
    created_at,
    last_modified
FROM clients
WHERE LOWER(name) = LOWER(:client_name)
AND status != 'archived'
LIMIT 1;
