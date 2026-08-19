DROP TABLE IF EXISTS inspection_events;

CREATE TABLE inspection_events AS
SELECT 
    o.camis,
    o.dba,
    o.inspection_date,
    o.inspection_type,
    MAX(o.grade) AS grade,
    MAX(o.score) AS score,
    MAX(o.grade_date) AS grade_date,
    o.boro,
    o.cuisine_description,
    COUNT(*) AS num_violations,
    SUM(CASE WHEN o.critical_flag = 'Critical' THEN 1 ELSE 0 END) AS num_critical_violations,
    SUM(CASE WHEN o.critical_flag = 'Not Critical' THEN 1 ELSE 0 END) AS num_non_critical_violations
FROM observations o
GROUP BY 
    o.camis,
    o.dba,
    o.inspection_date,
    o.inspection_type,
    o.boro,
    o.cuisine_description;

SELECT COUNT(*) AS total_rows FROM inspection_events;
SELECT COUNT(DISTINCT camis) AS distinct_camis FROM inspection_events;