INSERT INTO projects (
    programme_id,
    name,
    description,
    status,
    lead_id,
    start_date
)
VALUES (
    :programme_id,
    :name,
    :description,
    :status,
    :lead_id,
    :start_date
)
RETURNING
    id,
    programme_id,
    name,
    description,
    status,
    lead_id,
    start_date,
    created_at,
    last_modified;
