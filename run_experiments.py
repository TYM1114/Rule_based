import csv
import os
import time
import argparse
import sys

from main import YardSimulationController
from data_generator import BatchDataManager

def run_batch_experiments():
    parser = argparse.ArgumentParser(description="High-Speed Batch Simulation Experiments")
    parser.add_argument("--start_id", type=str, help="Start from this selection_run_id")
    parser.add_argument("--limit", type=int, help="Limit the number of runs to execute")
    args = parser.parse_known_args()[0]

    master_file = 'DB/cur_cmd_master.csv'
    if not os.path.exists(master_file):
        print(f"Error: Master file {master_file} not found.")
        return

    # 1. Initialize Controller and Batch Loader
    controller = YardSimulationController()
    batch_loader = BatchDataManager()
    
    # 2. Pre-load everything to RAM (Once)
    batch_loader.load_all_to_ram()

    # 3. Collect and sort unique IDs from cached master
    print("\nScanning cached data for unique selection_run_ids...")
    run_ids = set()
    for row in batch_loader.cached_master:
        rid = str(row.get('selection_run_id', '')).strip()
        if rid and rid != 'N/A':
            run_ids.add(rid)
    
    sorted_run_ids = sorted(list(run_ids))
    
    # 4. Filter by start_id
    if args.start_id:
        if args.start_id in sorted_run_ids:
            start_idx = sorted_run_ids.index(args.start_id)
            sorted_run_ids = sorted_run_ids[start_idx:]
            print(f"Starting from {args.start_id} (index {start_idx})")
        else:
            print(f"Warning: Start ID {args.start_id} not found in cache. Running all.")

    # 5. Apply limit
    if args.limit:
        sorted_run_ids = sorted_run_ids[:args.limit]
        print(f"Limited to {args.limit} runs.")

    total_count = len(sorted_run_ids)
    print(f"Ready to execute {total_count} experiments in high-speed mode.")
    print("--------------------------------------------------")

    # 6. Optimized Simulation Loop (In-Process)
    success_count = 0
    fail_count = 0
    fail_ids = []
    start_time = time.time()

    # Create a unified batch log directory
    batch_log_dir = controller.log_dir 

    for idx, rid in enumerate(sorted_run_ids, 1):
        print(f"[{idx}/{total_count}] Processing ID: {rid}")
        
        try:
            # 1. Get data from RAM (Fast!)
            res = batch_loader.get_data_for_run(rid, controller.config)
            if not res:
                print(f"Skip ID {rid}: Data filtering failed.")
                fail_count += 1; fail_ids.append(rid); continue
                
            yard_cfg, boxes, job_seq, sku_map, dest_map, meta = res
            
            if not boxes or not job_seq:
                print(f"Skip ID {rid}: No valid boxes or jobs.")
                fail_count += 1; fail_ids.append(rid); continue

            # 2. Configure Controller for this sub-run
            controller.active_run_id = rid
            controller.log_dir = batch_log_dir # Reuse the same directory
            
            # 3. Run Simulation directly in current process
            logs = controller.run_with_data(yard_cfg, boxes, job_seq, sku_map, dest_map)
            
            # 4. Export results
            controller.export_results(logs)
            success_count += 1
            
        except Exception as e:
            print(f"Unexpected error for ID {rid}: {e}")
            fail_count += 1
            fail_ids.append(rid)

        print(f"--- Completed ID: {rid} ---\n")

    total_duration = time.time() - start_time
    print("==================================================")
    print(" HIGH-SPEED BATCH EXPERIMENTS COMPLETED")
    print(f" Total Time : {total_duration:.2f} seconds")
    print(f" Success    : {success_count}")
    print(f" Failed     : {fail_count}")
    if fail_ids: print(f" Failed IDs : {fail_ids}")
    print("==================================================")

if __name__ == "__main__":
    run_batch_experiments()
