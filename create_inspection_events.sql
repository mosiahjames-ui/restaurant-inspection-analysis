-- Create inspection_events table with the proper grain: one row = unique camis + inspection_date + inspection_type
-- This script will:
-- 1. Group by camis, inspection_date, inspection_type
-- 2. Retain required fields
-- 3. Calculate violation counts
-- 4. Preserve NULL/missing values
-- 5. Not average score or use MIN(grade)
-- 6. Not combine different inspection types

-- First, let's check if inspection_events table already exists
-- If it does, we'll drop it to recreate it fresh
DROP TABLE IF EXISTS inspection_events;

-- Create the inspection_events table with the proper grain
CREATE TABLE inspection_events AS
SELECT 
    o.camis,
    o.dba,
    o.inspection_date,
    o.inspection_type,
    o.grade,
    o.score,
    o.grade_date,
    o.boro,
    o.cuisine_description,
    -- Count total violations (rows in observations for this specific combination)
    COUNT(*) as num_violations,
    -- Count critical violations
    SUM(CASE WHEN o.critical_flag = 'Critical' THEN 1 ELSE 0 END) as num_critical_violations,
    -- Count non-critical violations
    SUM(CASE WHEN o.critical_flag = 'Not Critical' THEN 1 ELSE 0 END) as num_non_critical_violations
FROM observations o
GROUP BY 
    o.camis,
    o.inspection_date,
    o.inspection_type;

-- Print summary statistics as requested
-- Number of rows in inspection_events
SELECT COUNT(*) as total_rows FROM inspection_events;

-- Number of distinct camis in inspection_events
SELECT COUNT(DISTINCT camis) as distinct_camis FROM inspection_events;

-- Number of rows with each inspection_type
SELECT inspection_type, COUNT(*) as row_count 
FROM inspection_events 
GROUP BY inspection_type 
ORDER BY row_count DESC;

-- Number of rows with each grade, including NULL
SELECT grade, COUNT(*) as row_count 
FROM inspection_events 
GROUP BY grade 
ORDER BY grade;