import json
import sqlite3
import os
from datetime import datetime

def setup_db(json_path, db_path):
    print(f"Converting {json_path} to SQLite database at {db_path}...")
    db_conn = sqlite3.connect(db_path)
    cursor = db_conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS observations")
    with open(json_path, 'r') as f:
        data = json.load(f)
    if not data:
        print("No data found in JSON.")
        return False
    all_keys = set()
    for item in data:
        all_keys.update(item.keys())
    columns = sorted(list(all_keys))
    cols_sql = ", ".join([f'"{col}" TEXT' for col in columns])
    cursor.execute(f"CREATE TABLE observations ({cols_sql})")
    placeholders = ", ".join(["?"] * len(columns))
    quoted_columns = ", ".join([f'"{c}"' for c in columns])
    insert_sql = f"INSERT INTO observations ({quoted_columns}) VALUES ({placeholders})"
    print(f"Inserting {len(data)} rows...")
    for item in data:
        row = []
        for col in columns:
            val = item.get(col)
            if isinstance(val, (dict, list)):
                val = json.dumps(val)
            row.append(val)
        cursor.execute(insert_sql, row)
    db_conn.commit()
    db_conn.close()
    print("Conversion complete.")
    return True

def run_full_analysis(db_path):
    print(f"\n--- Starting Full Exploratory Data Analysis ---")
    db_conn = sqlite3.connect(db_path)
    cursor = db_conn.cursor()

    # --- STEP 1: Inspect ---
    print("\n[STEP 1: INSPECTION]")
    cursor.execute("SELECT COUNT(*) FROM observations")
    total_rows = cursor.fetchone()[0]
    print(f"Total rows: {total_rows}")
    
    cursor.execute("PRAGMA table_info(observations)")
    cols = [c[1] for c in cursor.fetchall()]
    print(f"Columns: {', '.join(cols)}")

    # --- STEP 2: Grain ---
    print("\n[STEP 2: DATA GRAIN]")
    cursor.execute("""
        SELECT camis, inspection_date, COUNT(*) 
        FROM observations 
        GROUP BY camis, inspection_date 
        HAVING COUNT(*) > 1 
        LIMIT 1
    """)
    dup = cursor.fetchone()
    if dup:
        print("Grain: One row per violation (multiple rows per inspection/camis combo).")
    else:
        print("Grain: One row per inspection.")

    # --- STEP 3: Important Fields ---
    print("\n[STEP 3: IMPORTANT FIELDS]")
    important_fields = {
        "camis": "Unique identifier for the restaurant",
        "dba": "Doing Business As (Restaurant Name)",
        "inspection_date": "Date of the inspection",
        "grade": "Current health grade (A, B, C, etc.)",
        "score": "Numerical score from inspection",
        "violation_code": "Code for the specific violation",
        "violation_description": "Description of the violation",
        "critical_flag": "Indicates if the violation is critical",
        "cuisine_description": "Type of cuisine",
        "boro": "Borough where the restaurant is located"
    }
    for field, desc in important_fields.items():
        if field in cols:
            print(f"- {field}: {desc}")

    # --- STEP 4: Time Dimension ---
    print("\n[STEP 4: TIME DIMENSION]")
    cursor.execute("SELECT MIN(inspection_date), MAX(inspection_date) FROM observations")
    min_d, max_d = cursor.fetchone()
    print(f"Earliest inspection: {min_d}")
    print(f"Latest inspection: {max_d}")
    
    # --- STEP 5: Grades and Scores ---
    print("\n[STEP 5: GRADES AND SCORES]")
    cursor.execute("SELECT grade, COUNT(*) FROM observations WHERE grade IS NOT NULL GROUP BY grade")
    grades = cursor.fetchall()
    print("Grade distribution:")
    for g, count in grades:
        print(f"  {g}: {count}")

    cursor.execute("SELECT AVG(CAST(score AS FLOAT)) FROM observations WHERE score IS NOT NULL")
    avg_score = cursor.fetchone()[0]
    print(f"Average score: {avg_score:.2f}")

    # --- STEP 6: Violations ---
    print("\n[STEP 6: VIOLATIONS]")
    cursor.execute("""
        SELECT violation_description, COUNT(*) 
        FROM observations 
        GROUP BY violation_description 
        ORDER BY COUNT(*) DESC 
        LIMIT 5
    """)
    top_violations = cursor.fetchall()
    print("Top 5 violations:")
    for v, count in top_violations:
        print(f"  {count}x: {v}")

    cursor.execute("""
        SELECT COUNT(*) FROM observations WHERE critical_flag = 'Critical'
    """)
    crit_count = cursor.fetchone()[0]
    print(f"Total critical violations: {crit_count}")

    # --- STEP 7: Inspection Trajectories ---
    print("\n[STEP 7: INSPECTION TRAJECTORIES]")
    # Find restaurants with at least 2 inspections
    cursor.execute("""
        SELECT camis, COUNT(DISTINCT inspection_date) as inspection_count
        FROM observations
        GROUP BY camis
        HAVING inspection_count > 1
        ORDER BY inspection_count DESC
        LIMIT 5
    """)
    trajectories = cursor.fetchall()
    print(f"Found {len(trajectories)} restaurants with multiple inspections (sample shown).")
    
    # Sample trajectory for one restaurant
    if trajectories:
        sample_camis = trajectories[0][0]
        cursor.execute("""
            SELECT inspection_date, grade, score
            FROM observations
            WHERE camis =?
            ORDER BY inspection_date ASC
        """, (sample_camis,))
        history = cursor.fetchall()
        print(f"Trajectory for sample restaurant ({sample_camis}):")
        for h in history:
            print(f"  Date: {h[0]}, Grade: {h[1]}, Score: {h[2]}")

    # --- STEP 8: Surprising Patterns ---
    print("\n[STEP 8: SURPRISING PATTERNS]")
    # Example: Restaurants with same grade but different scores (if possible)
    cursor.execute("""
        SELECT grade, MIN(CAST(score AS FLOAT)), MAX(CAST(score AS FLOAT))
        FROM observations
        WHERE grade IS NOT NULL AND score IS NOT NULL
        GROUP BY grade
        HAVING MIN(CAST(score AS FLOAT))!= MAX(CAST(score AS FLOAT))
        LIMIT 3
    """)
    score_variance = cursor.fetchall()
    if score_variance:
        print("Found grades with varying scores (e.g., same grade, different scores):")
        for g, min_s, max_s in score_variance:
            print(f"  Grade {g}: Score range [{min_s}, {max_s}]")

    # --- STEP 9: Data Quality ---
    print("\n[STEP 9: DATA QUALITY]")
    print("Missing values summary:")
    for col in ['grade', 'violation_code', 'cuisine_description', 'boro', 'dba']:
        cursor.execute(f'SELECT COUNT(*) FROM observations WHERE "{col}" IS NULL OR "{col}" = ""')
        count = cursor.fetchone()[0]
        print(f"  {col}: {count} missing")

    db_conn.close()

if __name__ == "__main__":
    JSON_FILE = "data/raw_dataset.json"
    DB_FILE = "data/restaurant_data.db"
    
    if os.path.exists(JSON_FILE):
        if setup_db(JSON_FILE, DB_FILE):
            run_full_analysis(DB_FILE)
    else:
        print(f"Error: {JSON_FILE} not found.")