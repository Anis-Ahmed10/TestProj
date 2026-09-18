UPDATE programmes
SET status = 'archived',
    last_modified = NOW()
WHERE id = :programme_id
  AND status != 'archived'
RETURNING
    id,
    client_id,
    name,
    description,
    status,
    created_at,
    last_modified;
