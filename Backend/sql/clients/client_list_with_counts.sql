WITH active_clients AS (
    SELECT c.id
    FROM clients AS c
    WHERE c.status != 'archived'
),

programme_counts AS (
    SELECT
        p.client_id,
        COUNT(*) AS programmes_count
    FROM programmes AS p
    INNER JOIN active_clients ac ON ac.id = p.client_id
    WHERE p.status != 'archived'
    GROUP BY p.client_id
),

project_counts AS (
    SELECT
        p.client_id,
        COUNT(*) AS projects_count
    FROM projects AS pr
    INNER JOIN programmes AS p ON p.id = pr.programme_id
    INNER JOIN active_clients ac ON ac.id = p.client_id
    WHERE pr.status != 'archived'
    GROUP BY p.client_id
),

member_counts AS (
    SELECT
        p.client_id,
        COUNT(DISTINCT pu.user_id) AS active_members_count
    FROM project_users AS pu
    INNER JOIN projects AS pr ON pr.id = pu.project_id
    INNER JOIN programmes AS p ON p.id = pr.programme_id
    INNER JOIN active_clients ac ON ac.id = p.client_id
    GROUP BY p.client_id
)

SELECT
    c.id,
    c.name,
    c.industry,
    c.location,
    c.contact,
    c.status,
    c.manager_id,
    u.name AS manager_name,
    c.created_at,
    c.last_modified,
    COALESCE(pc.programmes_count, 0) AS programmes_count,
    COALESCE(prc.projects_count, 0) AS projects_count,
    COALESCE(mc.active_members_count, 0) AS active_members_count
FROM clients c
INNER JOIN active_clients ac ON ac.id = c.id
LEFT JOIN programme_counts AS pc ON pc.client_id = c.id
LEFT JOIN project_counts AS prc ON prc.client_id = c.id
LEFT JOIN member_counts AS mc ON mc.client_id = c.id
LEFT JOIN users u ON u.id = c.manager_id
ORDER BY c.last_modified DESC, c.id DESC;
