INSERT INTO clients (
    name,
    industry,
    location,
    contact,
    status,
    manager_id

)
VALUES (
    :name,
    :industry,
    :location,
    :contact,
    :status,
    :manager_id
)
RETURNING
    id,
    name,
    industry,
    location,
    contact,
    status,
    manager_id,
    created_at,
    last_modified;
