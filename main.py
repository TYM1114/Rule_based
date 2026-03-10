import csv
import time
import rb_solver
import sys
import os
import gen_sequence
import data_loader

def main():
    test_run_id = ""
    if len(sys.argv) > 1:
        if sys.argv[1] == "multi":
            count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            start_id = sys.argv[3] if len(sys.argv) > 3 else None
            _, test_run_id = gen_sequence.generate_optimized_sequence(count, start_id)
        else: test_run_id = sys.argv[1]
    
    if not test_run_id:
        user_input = input("Enter selection_run_id (or type 'multi'): ").strip()
        if user_input == "multi": _, test_run_id = gen_sequence.generate_optimized_sequence(10)
        elif user_input: test_run_id = user_input
    
    if not test_run_id: return

    
    # use data_loader to load all necessary data for the simulation
    config, boxes, job_sequence, sku_map, target_dest_map = data_loader.load_simulation_data(test_run_id)
    
    logs = rb_solver.run_rb_solver(config, boxes, job_sequence, sku_map, target_dest_map)
    
    # get tag map for better output readability
    tag_map = data_loader.get_tag_map(test_run_id)

    output_file = 'output_missions_python.csv'
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "mission_no", "agv_id", "mission_type", "selection_run_id", "cmd_id", "container_id", "related_target_id", 
            "src_pos", "dst_pos", "start_s", "end_s", "makespan", "sku_qty", "duration_breakdown"
        ])
        
        epoch = config['sim_start_epoch']
        counts, usage_idx = {"target": 0, "reshuffle": 0, "return": 0, "transfer": 0}, {}
        
        for log in logs:
            tid = log.related_target_id
            info_list = tag_map.get(tid, [{'run': "N/A", 'cmd': "N/A"}])
            idx = usage_idx.get(tid, 0)
            info = info_list[min(idx, len(info_list)-1)]
            if log.mission_type in ["target", "transfer"]: usage_idx[tid] = idx + 1
            
            s_pos = f"WS {abs(log.src[1])} (Port {log.src[2]})" if log.src[0] == -1 else f"({log.src[0]};{log.src[1]};{log.src[2]})"
            d_pos = f"WS {abs(log.dst[1])} (Port {log.dst[2]})" if log.dst[0] == -1 else f"({log.dst[0]};{log.dst[1]};{log.dst[2]})"
            if log.mission_type in counts: counts[log.mission_type] += 1

            writer.writerow([
                log.mission_no, log.agv_id, log.mission_type, info['run'], info['cmd'], 
                log.container_id-1, tid-1, s_pos, d_pos, log.start_time-epoch, log.end_time-epoch, log.makespan,
                sku_map.get(tid, 0), log.duration_detail
            ])

    print(f"Total Missions: {len(logs)}")
    print(f"Target: {counts['target']} | Reshuffle: {counts['reshuffle']} | Return: {counts['return']} | Transfer: {counts['transfer']}")
    print(f"Final Makespan: {logs[-1].makespan if logs else 0:.2f}\n")

if __name__ == "__main__":
    main()

