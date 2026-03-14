import os
import time
import argparse
import sys

from main import YardSimulationController
from data_generator import BatchDataManager

def run_batch_experiments():
    parser = argparse.ArgumentParser(description="High-Speed Batch Simulation Engine (No-Reset Mode)")
    parser.add_argument("--start_id", type=str, help="Start from this selection_run_id")
    parser.add_argument("--limit", type=int, help="Limit the number of runs to execute")
    args = parser.parse_known_args()[0]

    # 1. Initialize Controller and High-Speed Loader
    controller = YardSimulationController()
    batch_loader = BatchDataManager()
    
    # 2. Pre-load all DB data into memory (Fast subsequent access)
    batch_loader.load_all_to_ram()

    # 3. Collect and sort unique IDs from memory cache
    print("\n[Engine] Scanning memory for available selection_run_ids...")
    run_ids = set()
    for row in batch_loader.cached_master:
        rid = str(row.get('selection_run_id', '')).strip()
        if rid and rid != 'N/A':
            run_ids.add(rid)
    
    sorted_run_ids = sorted(list(run_ids))
    
    # 4. Filter by starting point
    if args.start_id:
        if args.start_id in sorted_run_ids:
            start_idx = sorted_run_ids.index(args.start_id)
            sorted_run_ids = sorted_run_ids[start_idx:]
            print(f"[Engine] Starting from ID: {args.start_id} (Index: {start_idx})")
        else:
            print(f"[Engine] Warning: {args.start_id} not found. Running all available IDs.")

    # 5. Apply execution limit
    if args.limit:
        sorted_run_ids = sorted_run_ids[:args.limit]
        print(f"[Engine] Limit set to {args.limit} runs.")

    total_count = len(sorted_run_ids)
    print(f"[Engine] Ready to execute {total_count} simulations at high speed.")
    print("-" * 50)

    # 6. High-Speed In-Process Execution Loop
    success_count = 0
    fail_count = 0
    fail_ids = []
    start_time = time.time()

    # Unified log directory for the entire session
    session_log_dir = controller.log_dir 

    for idx, rid in enumerate(sorted_run_ids, 1):
        print(f"[{idx}/{total_count}] Processing: {rid}")
        
        try:
            # Fetch pre-parsed data from RAM
            res = batch_loader.get_data_for_run(rid, controller.config)
            if not res:
                print(f"  !! Error: Data filtering failed for {rid}")
                fail_count += 1; fail_ids.append(rid); continue
                
            yard_cfg, boxes, job_seq, sku_map, dest_map, meta = res
            
            if not boxes or not job_seq:
                print(f"  !! Skip: Empty inventory or mission sequence for {rid}")
                fail_count += 1; fail_ids.append(rid); continue

            # Update controller state for this specific run
            controller.active_run_id = rid
            controller.log_dir = session_log_dir
            
            # Execute Simulation (No Python restart, No disk I/O)
            logs = controller.run_with_data(yard_cfg, boxes, job_seq, sku_map, dest_map)
            
            # Save independent output for each run_id
            controller.export_results(logs)
            success_count += 1
            
        except Exception as e:
            print(f"  !! Unexpected Crash for {rid}: {e}")
            fail_count += 1
            fail_ids.append(rid)

        print(f"--- Completed: {rid} ---\n")

    # Final Statistics
    total_duration = time.time() - start_time
    print("=" * 50)
    print(" HIGH-SPEED BATCH EXPERIMENTS COMPLETED")
    print(f" Total Duration : {total_duration:.2f} seconds")
    print(f" Success Count  : {success_count}")
    print(f" Failed Count   : {fail_count}")
    if fail_ids: print(f" Failed IDs     : {fail_ids}")
    print("=" * 50)

if __name__ == "__main__":
    run_batch_experiments()
