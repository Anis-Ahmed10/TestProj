SELECT
  p.id,
  p.programme_id,
  p.name,
  p.description,
  p.status,
  p.lead_id,
  p.start_date,
  p.created_at,
  p.last_modified,
  u.name AS lead_name
FROM projects p
LEFT JOIN users u ON u.id = p.lead_id
WHERE p.programme_id = :programme_id
  AND p.status != 'archived'
ORDER BY p.created_at DESC, p.name ASC;
