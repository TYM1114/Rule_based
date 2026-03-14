import csv
import os
import subprocess
import time
import argparse

def run_batch_experiments():
    parser = argparse.ArgumentParser(description="Batch Run Simulation Experiments")
    parser.add_argument("--start_id", type=str, help="Start from this selection_run_id")
    parser.add_argument("--limit", type=int, help="Limit the number of runs to execute")
    args = parser.parse_known_args()[0]

    master_file = 'DB/cur_cmd_master.csv'
    main_script = 'main.py'
    
    if not os.path.exists(master_file):
        print(f"Error: Master file {master_file} not found.")
        return
    if not os.path.exists(main_script):
        print(f"Error: Main script {main_script} not found.")
        return

    # 1. Collect and sort unique IDs
    print(f"Scanning {master_file} for unique IDs...")
    run_ids = set()
    try:
        with open(master_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rid = str(row.get('selection_run_id', '')).strip()
                if rid and rid != 'N/A':
                    run_ids.add(rid)
    except Exception as e:
        print(f"Failed to read CSV: {e}")
        return
    
    sorted_run_ids = sorted(list(run_ids))
    
    # 2. Filter by start_id
    if args.start_id:
        if args.start_id in sorted_run_ids:
            start_idx = sorted_run_ids.index(args.start_id)
            sorted_run_ids = sorted_run_ids[start_idx:]
            print(f"Starting from {args.start_id} (index {start_idx})")
        else:
            print(f"Warning: Start ID {args.start_id} not found. Running all IDs.")

    # 3. Apply limit
    if args.limit:
        sorted_run_ids = sorted_run_ids[:args.limit]
        print(f"Limited to {args.limit} runs.")

    total_count = len(sorted_run_ids)
    print(f"Ready to run {total_count} experiments.")
    print("--------------------------------------------------")

    # 4. Main Loop
    success_count = 0
    fail_count = 0
    fail_ids = []
    start_time = time.time()

    for idx, rid in enumerate(sorted_run_ids, 1):
        print(f"[{idx}/{total_count}] Executing ID: {rid}")
        
        # Call main.py with --mode db and --run_id
        command = ["python", main_script, "--mode", "db", "--run_id", rid]
        
        try:
            # We use subprocess.run and let it print directly to stdout
            result = subprocess.run(command)
            
            if result.returncode == 0:
                success_count += 1
            else:
                fail_count += 1
                fail_ids.append(rid)
                
        except Exception as e:
            print(f"Execution error for ID {rid}: {e}")
            fail_count += 1
            fail_ids.append(rid)

        print(f"--- Finished ID: {rid} ---\n")

    total_duration = time.time() - start_time
    print("==================================================")
    print(" BATCH EXPERIMENTS COMPLETED")
    print(f" Total Time : {total_duration:.2f} seconds")
    print(f" Success    : {success_count}")
    print(f" Failed     : {fail_count}")
    if fail_ids: print(f" Failed IDs : {fail_ids}")
    print("==================================================")

if __name__ == "__main__":
    run_batch_experiments()
