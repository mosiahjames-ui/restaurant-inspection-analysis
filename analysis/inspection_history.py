import sqlite3
import collections
import json

def run_analysis():
    db_path = 'data/restaurant_data.db'
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Step 1: Aggregating violation-level data to inspection-level...")

    # Create a temporary table for aggregated inspections
    # We'll group by restaurant and inspection date. 
    # Since we found inconsistencies in score/grade for some inspections,
    # we will take the MIN grade and AVG score.
    
    cursor.execute("DROP TABLE IF EXISTS aggregated_inspections")
    cursor.execute("""
        CREATE TABLE aggregated_inspections AS
        SELECT 
            camis,
            dba,
            inspection_date,
            MIN(grade) as grade,
            AVG(CAST(score AS REAL)) as score,
            inspection_type,
            boro,
            cuisine_description,
            COUNT(*) as num_violations,
            SUM(CASE WHEN critical_flag = 'Critical' THEN 1 ELSE 0 END) as num_critical_violations,
            SUM(CASE WHEN critical_flag = 'Not Critical' THEN 1 ELSE 0 END) as num_non_critical_violations
        FROM observations
        GROUP BY camis, inspection_date
    """)

    print("Step 2: Analyzing graded inspections and trajectories...")
    
    # Fetch the aggregated data
    cursor.execute("""
        SELECT 
            camis, 
            dba,
            inspection_date, 
            grade, 
            score, 
            inspection_type, 
            boro, 
            cuisine_description,
            num_violations,
            num_critical_violations,
            num_non_critical_violations
        FROM aggregated_inspections
        WHERE grade IS NOT NULL AND grade IN ('A', 'B', 'C')
        ORDER BY camis, inspection_date ASC
    """)
    
    restaurant_histories = collections.defaultdict(list)
    restaurant_metadata = {}

    for row in cursor.fetchall():
        camis, dba, date, grade, score, ins_type, boro, cuisine, n_viol, n_crit, n_non_crit = row
        
        restaurant_histories[camis].append({
            'date': date,
            'grade': grade,
            'core': score,
            'inspection_type': ins_type,
            'num_violations': n_viol,
            'num_critical_violations': n_crit,
            'num_non_critical_violations': n_non_crit
        })
        
        if camis not in restaurant_metadata:
            restaurant_metadata[camis] = {
                'dba': dba,
                'boro': boro,
                'cuisine': cuisine
            }

    print(f"Found {len(restaurant_histories)} restaurants with graded inspection histories.")

    # PART 3 & 4: Construct histories and classify trajectories
    trajectory_counts = collections.defaultdict(int)
    current_grade_stats = collections.defaultdict(lambda: collections.defaultdict(int))
    trajectory_data = collections.defaultdict(list)
    
    for camis, history in restaurant_histories.items():
        if len(history) < 2:
            continue
            
        grades = [h['grade'] for h in history]
        current_grade = grades[-1]
        
        # Classification Logic
        trajectory = "Other"
        if all(g == grades[0] for g in grades):
            trajectory = f"Stable {grades[0]}"
        elif grades[0] == current_grade and grades[-1] == current_grade and any(g!= current_grade for g in grades):
            trajectory = f"Recovered to {current_grade}"
        elif grades[0]!= current_grade and grades[-1] == current_grade:
            trajectory = f"Improved to {current_grade}"

        trajectory_counts[trajectory] += 1
        current_grade_stats[current_grade][trajectory] += 1
        
        # Collect inspection data for the trajectory
        for h in history:
            trajectory_data[trajectory].append({
                'camis': camis,
                'dba': restaurant_metadata[camis]['dba'],
                'boro': restaurant_metadata[camis]['boro'],
                'cuisine': restaurant_metadata[camis]['cuisine'],
                'date': h['date'],
                'grade': h['grade'],
                'core': h['score'],
                'num_violations': h['num_violations'],
                'num_critical_violations': h['num_critical_violations'],
                'num_non_critical_violations': h['num_non_critical_violations']
            })

    print("Step 3: Quantifying Trajectories...")

    results = {
        'trajectories': {},
        'current_grade_distribution': {},
        'violation_averages': {},
        'epresentative_examples': []
    }

    # Part 6: Violation Analysis
    for traj, data in trajectory_data.items():
        if not data: continue
        avg_viol = sum(d['num_violations'] for d in data) / len(data)
        avg_crit = sum(d['num_critical_violations'] for d in data) / len(data)
        avg_non_crit = sum(d['num_non_critical_violations'] for d in data) / len(data)
        results['violation_averages'][traj] = {
            'avg_viol': round(avg_viol, 2),
            'avg_crit': round(avg_crit, 2),
            'avg_non_crit': round(avg_non_crit, 2)
        }

    # Part 5: Quantify Percentages
    total_for_grade = collections.defaultdict(int)
    for camis, history in restaurant_histories.items():
        if len(history) < 2: continue
        total_for_grade[history[-1]['grade']] += 1

    for grade in ['A', 'B', 'C']:
        total = total_for_grade[grade]
        if total > 0:
            results['current_grade_distribution'][grade] = {}
            for traj, count in current_grade_stats[grade].items():
                results['current_grade_distribution'][grade][traj] = round((count / total) * 100, 2)
            results['current_grade_distribution'][grade]['total_count'] = total
        else:
            results['current_grade_distribution'][grade] = {'total_count': 0}

    # Part 7: Representative Examples
    target_trajectories = [
        "Stable A",
        "Improved to A",
        "Recovered to A",
        "Stable B",
        "Stable C"
    ]
    
    for target in target_trajectories:
        found = False
        for camis, history in restaurant_histories.items():
            if len(history) < 2: continue
            grades = [h['grade'] for h in history]
            current_grade = grades[-1]
            
            trajectory = "Other"
            if all(g == grades[0] for g in grades):
                trajectory = f"Stable {grades[0]}"
            elif grades[0] == current_grade and grades[-1] == current_grade and any(g!= current_grade for g in grades):
                trajectory = f"Recovered to {current_grade}"
            elif grades[0]!= current_grade and grades[-1] == current_grade:
                trajectory = f"Improved to {current_grade}"
                
            if trajectory == target:
                example = {
                    'estaurant_name': restaurant_metadata[camis]['dba'],
                    'borough': restaurant_metadata[camis]['boro'],
                    'cuisine': restaurant_metadata[camis]['cuisine'],
                    'history': []
                }
                for h in history:
                    example['history'].append({
                        'date': h['date'],
                        'grade': h['grade'],
                        'core': h['score'],
                        'violations': h['num_violations'],
                        'critical_violations': h['num_critical_violations']
                    })
                results['representative_examples'].append(example)
                found = True
                break
        if not found:
            results['representative_examples'].append(f"No example found for {target}")

    # Final output
    with open('analysis/results.json', 'w') as f:
        json.dump(results, f, indent=4)

    print("Analysis completed successfully. Results saved to analysis/results.json")
    
    print("\n--- Summary ---")
    for grade, stats in results['current_grade_distribution'].items():
        if grade == 'total_count': continue
        print(f"Current Grade {grade}:")
        for traj, perc in stats.items():
            if isinstance(perc, float):
                print(f"  {traj}: {perc:.2f}%")

    conn.close()

if __name__ == "__main__":
    run_analysis()