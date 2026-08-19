import sqlite3
import collections
import csv
import json
import os

def initialize_database(db_path):
    """Check if database and inspection_events table exist and are populated.
    If not, initialize them from raw data."""
    
    # Check if database file exists
    if not os.path.exists(db_path):
        print("Database not found. Initializing from raw data...")
        # Import and run setup from scripts/analyze_dataset.py
        import sys
        sys.path.insert(0, 'scripts')
        from analyze_dataset import setup_db
        json_path = 'data/raw_dataset.json'
        if os.path.exists(json_path):
            setup_db(json_path, db_path)
        else:
            raise FileNotFoundError(f"Raw data file not found: {json_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if inspection_events table exists and is populated
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inspection_events'")
    table_exists = cursor.fetchone() is not None
    
    if not table_exists:
        print("inspection_events table not found. Creating it...")
        cursor.execute("DROP TABLE IF EXISTS inspection_events")
        cursor.execute("""
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
                o.cuisine_description
        """)
        conn.commit()
        print("inspection_events table created successfully.")
    else:
        # Check if table is populated
        cursor.execute("SELECT COUNT(*) FROM inspection_events")
        count = cursor.fetchone()[0]
        if count == 0:
            print("inspection_events table is empty. Populating it...")
            cursor.execute("DROP TABLE IF EXISTS inspection_events")
            cursor.execute("""
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
                    o.cuisine_description
            """)
            conn.commit()
            print("inspection_events table populated successfully.")
    
    return conn, cursor

def run_analysis():
    db_path = 'data/restaurant_data.db'
    
    # Initialize database and inspection_events table if needed
    conn, cursor = initialize_database(db_path)

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
    graded_inspection_dates = []

    for row in cursor.fetchall():
        camis, dba, date, grade, score, ins_type, boro, cuisine, n_viol, n_crit, n_non_crit = row
        if date:
            graded_inspection_dates.append(date)
        
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
                'core': h['core'],
                'num_violations': h['num_violations'],
                'num_critical_violations': h['num_critical_violations'],
                'num_non_critical_violations': h['num_non_critical_violations']
            })

    print("Step 3: Quantifying Trajectories...")

    results = {
        'trajectories': {},
        'current_grade_distribution': {},
        'violation_averages': {},
        'representative_examples': [],
        'grade_timeframe': {
            'start': min(graded_inspection_dates) if graded_inspection_dates else None,
            'end': max(graded_inspection_dates) if graded_inspection_dates else None,
            'inspection_count': len(graded_inspection_dates)
        }
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
                    'restaurant_name': restaurant_metadata[camis]['dba'],
                    'borough': restaurant_metadata[camis]['boro'],
                    'cuisine': restaurant_metadata[camis]['cuisine'],
                    'history': []
                }
                for h in history:
                    example['history'].append({
                        'date': h['date'],
                        'grade': h['grade'],
                        'core': h['core'],
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

    dashboard_data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dashboard_data.csv')
    cursor.execute("""
        SELECT
            COALESCE(boro, 'Unknown') AS boro,
            COALESCE(cuisine_description, 'Unknown') AS cuisine_description,
            grade,
            COUNT(*) AS inspection_count,
            MIN(inspection_date) AS first_inspection,
            MAX(inspection_date) AS last_inspection
        FROM aggregated_inspections
        WHERE grade IN ('A', 'B', 'C')
        GROUP BY COALESCE(boro, 'Unknown'), COALESCE(cuisine_description, 'Unknown'), grade
    """)
    dashboard_rows = cursor.fetchall()
    with open(dashboard_data_path, 'w', newline='') as dashboard_file:
        writer = csv.writer(dashboard_file)
        writer.writerow([
            'boro', 'cuisine_description', 'grade', 'inspection_count',
            'first_inspection', 'last_inspection'
        ])
        writer.writerows(dashboard_rows)

    print("Analysis completed successfully. Results saved to analysis/results.json")
    
    print("\n--- Summary ---")
    for grade, stats in results['current_grade_distribution'].items():
        if grade == 'total_count': continue
        print(f"Current Grade {grade}:")
        for traj, perc in stats.items():
            if isinstance(perc, float):
                print(f"  {traj}: {perc:.2f}%")

    conn.close()


def load_dashboard_data(db_path):
    """Load one row per inspection for the interactive Streamlit dashboard."""
    dashboard_data_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(db_path))),
        'analysis',
        'dashboard_data.csv'
    )
    import pandas as pd

    if os.path.exists(dashboard_data_path):
        data = pd.read_csv(dashboard_data_path)
        data['first_inspection'] = pd.to_datetime(data['first_inspection'], errors='coerce')
        data['last_inspection'] = pd.to_datetime(data['last_inspection'], errors='coerce')
        data['boro'] = data['boro'].fillna('Unknown').replace('', 'Unknown')
        data['cuisine_description'] = data['cuisine_description'].fillna('Unknown').replace('', 'Unknown')
        return data

    conn, cursor = initialize_database(db_path)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='aggregated_inspections'")
    table_exists = cursor.fetchone() is not None

    if not table_exists:
        cursor.execute("""
            CREATE TABLE aggregated_inspections AS
            SELECT
                camis,
                dba,
                inspection_date,
                MIN(grade) AS grade,
                AVG(CAST(score AS REAL)) AS score,
                inspection_type,
                boro,
                cuisine_description,
                COUNT(*) AS num_violations,
                SUM(CASE WHEN critical_flag = 'Critical' THEN 1 ELSE 0 END) AS num_critical_violations,
                SUM(CASE WHEN critical_flag = 'Not Critical' THEN 1 ELSE 0 END) AS num_non_critical_violations
            FROM observations
            GROUP BY camis, inspection_date
        """)
        conn.commit()

    data = pd.read_sql_query("""
         SELECT COALESCE(boro, 'Unknown') AS boro,
             COALESCE(cuisine_description, 'Unknown') AS cuisine_description,
             grade,
             COUNT(*) AS inspection_count,
             MIN(inspection_date) AS first_inspection,
             MAX(inspection_date) AS last_inspection
        FROM aggregated_inspections
        WHERE grade IN ('A', 'B', 'C')
         GROUP BY COALESCE(boro, 'Unknown'), COALESCE(cuisine_description, 'Unknown'), grade
    """, conn)
    conn.close()

    data['first_inspection'] = pd.to_datetime(data['first_inspection'], errors='coerce')
    data['last_inspection'] = pd.to_datetime(data['last_inspection'], errors='coerce')
    data['boro'] = data['boro'].fillna('Unknown').replace('', 'Unknown')
    data['cuisine_description'] = data['cuisine_description'].fillna('Unknown').replace('', 'Unknown')
    return data


def streamlit_dashboard():
    """Render the interactive inspection dashboard with Streamlit and Plotly."""
    import plotly.express as px
    import streamlit as st

    st.set_page_config(page_title='NYC Restaurant Inspections', page_icon='🍽️', layout='wide')
    st.title('NYC Restaurant Inspections')
    st.caption('Interactive grade and inspection-history analysis from NYC Open Data')

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, 'data', 'restaurant_data.db')

    try:
        data = load_dashboard_data(db_path)
    except Exception as error:
        st.error(f'Could not load the inspection data: {error}')
        st.stop()

    palette = {'A': '#1e6b50', 'B': '#d5962d', 'C': '#bf5a45'}
    boroughs = sorted(data['boro'].dropna().unique())
    cuisines = sorted(data['cuisine_description'].dropna().unique())

    st.sidebar.header('Filter dashboard')
    selected_borough = st.sidebar.selectbox('Borough', ['All boroughs'] + boroughs)
    selected_cuisines = st.sidebar.multiselect(
        'Cuisine',
        cuisines,
        help='Leave empty to include every cuisine.'
    )

    filtered = data.copy()
    if selected_borough != 'All boroughs':
        filtered = filtered[filtered['boro'] == selected_borough]
    if selected_cuisines:
        filtered = filtered[filtered['cuisine_description'].isin(selected_cuisines)]

    with st.expander('How to read these grades'):
        start_date = data['first_inspection'].min()
        end_date = data['last_inspection'].max()
        st.write(
            f"The graded inspection records cover {start_date:%B %-d, %Y} "
            f"through {end_date:%B %-d, %Y}."
        )
        st.write(
            'The source data is recorded at the violation level. Multiple violation rows '
            'from one inspection are grouped together before calculating grade histories.'
        )
        st.markdown(
            '**Stable A:** every available graded inspection for a restaurant was A, '
            'with at least two graded inspections.\n\n'
            '**Stable B:** every available graded inspection was B, with at least two '
            'graded inspections.\n\n'
            '**Stable C:** every available graded inspection was C, with at least two '
            'graded inspections.'
        )
        st.caption(
            'Stable describes consistency in the available records. It does not mean '
            'the restaurant was inspected continuously outside this dataset.'
        )

    grade_counts = filtered.groupby('grade')['inspection_count'].sum().reindex(['A', 'B', 'C'], fill_value=0)
    metric_columns = st.columns(3)
    for column, grade in zip(metric_columns, ['A', 'B', 'C']):
        column.metric(f'Grade {grade} inspections', f'{grade_counts[grade]:,}')

    donut_data = grade_counts.rename_axis('grade').reset_index(name='count')
    donut = px.pie(
        donut_data,
        names='grade',
        values='count',
        hole=0.62,
        title='Grade breakdown',
        color='grade',
        color_discrete_map=palette
    )
    donut.update_traces(textinfo='percent+label', hovertemplate='Grade %{label}: %{value:,} (%{percent})<extra></extra>')
    donut.update_layout(template='simple_white', margin=dict(t=60, b=10, l=10, r=10), showlegend=False)
    st.plotly_chart(donut, use_container_width=True)

    borough_grade_counts = (
        filtered.groupby(['boro', 'grade'], as_index=False)['inspection_count']
        .sum()
        .rename(columns={'inspection_count': 'count'})
    )
    borough_chart = px.bar(
        borough_grade_counts,
        x='boro',
        y='count',
        color='grade',
        barmode='group',
        title='Grade Distribution by Borough',
        labels={'boro': 'Borough', 'count': 'Inspection count', 'grade': 'Grade'},
        color_discrete_map=palette,
        category_orders={'grade': ['A', 'B', 'C']}
    )
    borough_chart.update_layout(template='simple_white', margin=dict(t=60, b=10, l=10, r=10), legend_title_text='')
    st.plotly_chart(borough_chart, use_container_width=True)


if __name__ == "__main__":
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        running_in_streamlit = get_script_run_ctx() is not None
    except ImportError:
        running_in_streamlit = False

    if running_in_streamlit:
        streamlit_dashboard()
    else:
        run_analysis()