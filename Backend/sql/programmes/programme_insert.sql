INSERT INTO programmes (
    client_id,
    name,
    description,
    status
)
VALUES (
    :client_id,
    :name,
    :description,
    :status
)
RETURNING
    id,
    client_id,
    name,
    description,
    status,
    created_at,
    last_modified;
