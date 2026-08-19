# Data Discovery Research Report: NYC Restaurant Inspections

## 1. Dataset Overview
- **Total Rows:** 295,719
- **Source:** NYC Open Data (via API)
- **Key Metadata:** Includes timestamps for creation, updates, and record versions.

## 2. Data Grain
The grain of this dataset is **one row per violation**. 
**Evidence:** Analysis shows that multiple records exist for the same `camis` (restaurant ID) and `inspection_date`. This indicates that a single inspection event can generate multiple rows if multiple violations are cited.

## 3. Important Fields
The following fields are critical for analytical purposes:
- `camis`: Unique identifier for the restaurant.
- `dba`: Doing Business As (Restaurant Name).
- `inspection_date`: The date the inspection occurred.
- `grade`: The health grade assigned (e.g., A, B, C).
- `score`: Numerical score derived from the inspection.
- `violation_code`: The specific code for the violation.
- `violation_description`: Textual description of the violation.
- `critical_flag`: Indicates if the violation is "Critical" or "Not Critical".
- `cuisine_description`: The type of cuisine served.
- `boro`: The borough where the restaurant is located.

## 4. Data Quality
- **Missing Values:**
    - `grade`: Highly sparse (150,504 missing). This suggests that not every inspection results in a grade assignment, or grades are only recorded for specific inspection types.
    - `violation_code`: 6,378 missing.
    - `cuisine_description`: 3,744 missing.
- **Consistency:** `boro` and `dba` are highly complete.
- **Limitations:** The high missingness in `grade` is a significant limitation for any analysis attempting to correlate inspection details directly with health grades without filtering for specific inspection types.

## 5. Time Coverage
- **Earliest Inspection:** 1900-01-01
- **Latest Inspection:** 2026-08-16
- **Note:** The dataset provides a long historical view, though the density of data may vary significantly over time.

## 6. Restaurant Inspection Structure
The data supports **inspection-history analysis**. Many restaurants (`camis`) have multiple inspection records over time, allowing for the study of restaurant trajectories (e.g., grade improvements or declines).

## 7. Grade/Score Findings
- **Grade Distribution:**
    - A: 98,080
    - B: 18,070
    - C: 13,210
    - N: 10,264
    - Z: 4,835
- **Average Score:** 25.64
- **Score/Grade Relationship:** There is significant variance in scores within the same grade. For example, Grade A restaurants have scores ranging from 0 to 43.

## 8. Violation Findings
- **Top Violations:**
    1. Non-food contact surface/equipment cleanliness (40,491 occurrences).
    2. Pest harborage/conditions (24,675 occurrences).
    3. Improper washing/sanitizing of food contact surfaces (18,612 occurrences).
    4. Temperature control issues (18,595 occurrences).
    5. Plumbing/Siphonage issues (18,565 occurrences).
- **Criticality:** A large portion of the dataset (155,198 rows) involves "Critical" violations.

## 9. Inspection-History Findings
The dataset allows for tracking restaurant trajectories. We can observe patterns such as:
- Grade improvements (e.g., B $\rightarrow$ A).
- Grade declines (e.g., A $\rightarrow$ C).
- Stability (e.g., A $\rightarrow$ A $\rightarrow$ A).

## 10. Interesting Patterns
- **Score Variance:** As noted, the relationship between score and grade is not a strict threshold, as seen by the wide range of scores within Grade A.
- **Violation Frequency:** A small number of violation types account for a massive percentage of the total records.

## 11. Potential Stories Worth Investigating
- **The "Grade Recovery" Story:** Identifying restaurants that successfully moved from a 'C' or 'B' grade back to an 'A' grade and what specific violation patterns they corrected.
- **The "Criticality" Correlation:** Investigating if the frequency of "Critical" violations is a better predictor of grade changes than the total score.
- **Cuisine & Compliance:** Analyzing if certain cuisine types are disproportionately associated with specific types of critical violations.

## 12. Questions We Still Need to Answer
- Why is the `grade` field missing for over 50% of the records?
- Is there a specific threshold in the `score` that triggers a grade change, or is it more complex?
- How do inspection types (e.g., "Cycle Inspection" vs "Initial Inspection") affect the likelihood of receiving a grade?

## 13. Limitations and Warnings
- **Grain Ambiguity:** Because the grain is "violations per inspection," aggregate statistics (like average score per inspection) must be calculated carefully to avoid double-counting.
- **Missing Grades:** Any analysis relying on grades must account for the high number of null values.
- **Score/Grade Disconnect:** The variance in scores within a single grade suggests that the score and grade might not be perfectly linear or may be subject to different weighting.

## Top 5 Findings Worth Investigating
1. **Grade Trajectories:** The ability to track restaurant health improvements/declines over time.
2. **Critical Violation Patterns:** The high volume of critical violations and their impact on grades.
3. **Score vs. Grade Variance:** The non-linear relationship between numerical scores and letter grades.
4. **Violation Hotspots:** Identifying the most common and most critical violation types.
5. **Cuisine-Specific Compliance:** Patterns in violations across different food categories.