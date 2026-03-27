import os
import time
import argparse
import sys
import csv
from datetime import datetime
from main import YardSimulationController
from data_generator import BatchDataManager

def run_exp():

    ORDER_SCENARIO = "large_uni"
    INV_SCENARIOS = [
        "2x2_slot_random_place_random",
        "2x2_slot_inorder_place_inorder",
        "2x2_slot_inorder_place_cluster",
        "2x2_slot_inorder_place_random"
    ]
    BATCH_WINDOWS = ["1", "5", "10", "15"]
    BATCH_ALGOS = ["grasp_ver3", "greedy_ver3"]
    SELECT_ALGOS = ["grasp_ver3", "greedy_ver3"]



    controller = YardSimulationController()
    batch_loader = BatchDataManager()
    batch_loader.load_all_to_ram()

    session_start_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_log_dir = controller.log_dir 
    
    combo_report_path = os.path.join(base_log_dir, "combo_summary.csv")
    with open(combo_report_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "Order Scenario", "Inv Scenario", "Batch Time Window", 
            "Batch Algo Ver", "Selection Algo Ver", 
            "Number of Tasks", "Makespan", "CPU time"
        ])

    summary_data = []

    for inv in INV_SCENARIOS:
        for win in BATCH_WINDOWS:
            for b_algo in BATCH_ALGOS:
                for s_algo in SELECT_ALGOS:
                    

                    combo_name = f"{inv}_{win}_{b_algo}_{s_algo}"
                    combo_dir = os.path.join(base_log_dir, combo_name)
                    
                    target_run_ids = []
                    for row in batch_loader.cached_master:
                        if (row.get('order_scenario') == ORDER_SCENARIO and
                            row.get('inv_scenario') == inv and
                            row.get('batch_time_window') == win and
                            row.get('batch_algo_ver') == b_algo and
                            row.get('selection_algo_ver') == s_algo):
                            
                            rid = str(row.get('selection_run_id', '')).strip()
                            if rid and rid not in target_run_ids:
                                target_run_ids.append(rid)
                    
                    if not target_run_ids:
                        continue 

                    os.makedirs(combo_dir, exist_ok=True)
                    print(f"\n[Combo] Starting: {combo_name}")
                    print(f"       Found {len(target_run_ids)} cases to simulate.")
                    
                    combo_total_tasks = 0
                    combo_total_makespan = 0.0
                    combo_total_cpu_time = 0.0

                    for rid in target_run_ids:
                        try:
                            res = batch_loader.get_data_for_run(rid, controller.config)
                            if not res: continue
                            yard_cfg, boxes, job_seq, sku_map, dest_map, meta = res

                            controller.active_run_id = rid
                            controller.log_dir = combo_dir
                            
                            start_cpu = time.process_time()
                            logs = controller.run_with_data(yard_cfg, boxes, job_seq, sku_map, dest_map)
                            cpu_duration = time.process_time() - start_cpu
                            
                            num_tasks = len(logs)
                            final_makespan = logs[-1].makespan if logs else 0
                            
                            print(f"  > ID: {rid} | Tasks: {num_tasks} | Makespan: {final_makespan:.2f} | CPU: {cpu_duration:.4f}s")
                            
                            controller.export_results(logs)
                            
                            combo_total_tasks += num_tasks
                            combo_total_makespan += final_makespan
                            combo_total_cpu_time += cpu_duration
                            
                            summary_data.append([combo_name, rid, num_tasks, final_makespan, cpu_duration])
                            
                        except Exception as e:
                            print(f"  !! Error processing {rid}: {e}")

                    # 輸出組合彙總結果到 Terminal
                    print("-" * 50)
                    print(f"[Combo Summary] {combo_name}")
                    print(f"  Total Tasks    : {combo_total_tasks}")
                    print(f"  Total Makespan : {combo_total_makespan:.2f}")
                    print(f"  Total CPU Time : {combo_total_cpu_time:.4f}s")
                    print("-" * 50)

                    combo_row = [
                        ORDER_SCENARIO, inv, win, b_algo, s_algo,
                        combo_total_tasks, combo_total_makespan, combo_total_cpu_time
                    ]

                    with open(combo_report_path, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(combo_row)

    report_path = os.path.join(base_log_dir, "experiment_total_summary.csv")
    with open(report_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Combo_Name", "Selection_Run_ID", "Number_of_Tasks", "Makespan", "CPU_Time"])
        writer.writerows(summary_data)

    print(f"\n[All Completed] Global summary saved to: {report_path}")
    print(f"                Combo summary (image.png style) saved to: {combo_report_path}")

if __name__ == "__main__":
    run_exp()

if __name__ == "__main__":
    run_exp()
