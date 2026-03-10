import csv
import time
import rb_solver
import sys
import os
import gen_sequence

# --- Parsing Tools ---
def parse_location_id(loc_id):
    if not loc_id or len(loc_id) < 10: return -1, -1, -1
    return int(loc_id[0:5]), int(loc_id[5:8]), int(loc_id[8:10])

def parse_carrier_id(car_id):
    if not car_id: return 0
    clean_id = ''.join(filter(str.isdigit, car_id))
    return int(clean_id) + 1 if clean_id else 0

def load_data_v4(run_id):
    print(f"Selection run id: {run_id}")
    inv_scenario = ""
    job_sequence = []
    target_dest_map = {}
    cmd_to_parent = {}
    
    csv_source = 'DB/cur_cmd_master.csv'
    if os.path.exists('resequence.csv'):
        with open('resequence.csv', 'r', encoding='utf-8-sig') as f:
            if run_id in f.read():
                csv_source = 'resequence.csv'
                print(f"Using optimized resequence source: {csv_source}")

    try:
        with open(csv_source, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['selection_run_id'] == run_id:
                    inv_scenario = row['inv_scenario']
                    p_id = parse_carrier_id(row['parent_carrier_id'])
                    if p_id == 0: continue
                    dest_bay = -(int(row['dest_position']) + 1)
                    cmd_to_parent[row['cmd_id']] = p_id
                    job_sequence.append(p_id)
                    if p_id not in target_dest_map: target_dest_map[p_id] = []
                    target_dest_map[p_id].append(dest_bay)
    except FileNotFoundError:
        print(f"Error: {csv_source} not found.")

    carrier_to_parent = {}
    max_id = 0
    try:
        with open('DB/cur_carrier.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                c_id, p_id = row['carrier_id'], parse_carrier_id(row['parent_carrier_id'])
                carrier_to_parent[c_id] = p_id
                if p_id > max_id: max_id = p_id
    except: pass

    boxes, seen_parents, used_locations = [], set(), set()
    try:
        with open('DB/cur_inventory.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['scenario'] == inv_scenario:
                    p_id = carrier_to_parent.get(row['carrier_id'])
                    r, b, l = parse_location_id(row['location_id'])
                    if p_id and p_id not in seen_parents and (r,b,l) not in used_locations:
                        boxes.append({'id': p_id, 'row': r, 'bay': b, 'level': l})
                        seen_parents.add(p_id); used_locations.add((r,b,l))
                        if p_id > max_id: max_id = p_id
    except: pass

    valid_job_sequence = [t for t in job_sequence if t in seen_parents]
    sku_map = {}
    try:
        with open('DB/cur_cmd_detail.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                p_id = cmd_to_parent.get(row['cmd_id'])
                if p_id: sku_map[p_id] = sku_map.get(p_id, 0) + int(row['quantity'])
    except: pass

    config = {
        'max_row': 6, 'max_bay': 11, 'max_level': 8, 'total_boxes': max_id + 1000,
        'agv_count': 5, 'port_count': 3, 'workstation_count': 3,
        't_travel': 5.0, 't_handle': 30.0, 't_process': 10.0, 't_pick': 2.0,
        'sim_start_epoch': 1705363200, 'w_penalty_lookahead': 500.0,
    }
    print(f"Final Count: {len(boxes)} boxes. Jobs: {len(valid_job_sequence)}")
    return config, boxes, valid_job_sequence, sku_map, target_dest_map

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

    print(f"--- Starting Simulation for ID: {test_run_id} ---")
    config, boxes, job_sequence, sku_map, target_dest_map = load_data_v4(test_run_id)
    logs = rb_solver.run_rb_solver(config, boxes, job_sequence, sku_map, target_dest_map)
    
    # 建立標記映射 (僅供 Output 追蹤用)
    tag_map = {}
    search_file = 'resequence.csv' if "RESEQ" in test_run_id else 'DB/cur_cmd_master.csv'
    try:
        with open(search_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['selection_run_id'] == test_run_id:
                    p_id = parse_carrier_id(row['parent_carrier_id'])
                    tag_map.setdefault(p_id, []).append({'run': row.get('original_run_id', row['selection_run_id']), 'cmd': row['cmd_id']})
        
        if "RESEQ" in test_run_id:
            master_data = {}
            with open('DB/cur_cmd_master.csv', 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    p_id = parse_carrier_id(row['parent_carrier_id'])
                    master_data.setdefault(p_id, []).append({'run': row['selection_run_id'], 'cmd': row['cmd_id']})
            for p_id in tag_map:
                if p_id in master_data: tag_map[p_id] = master_data[p_id]
    except: pass

    output_file = 'output_missions_python.csv'
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "mission_no", "agv_id", "mission_type", "original_run_id", "cmd_id", "container_id", "related_target_id", 
            "src_pos", "dst_pos", "start_time", "end_time", "start_s", "end_s", 
            "makespan", "sku_qty", "duration_breakdown"
        ])
        
        epoch = config['sim_start_epoch']
        counts, usage_idx = {"target": 0, "reshuffle": 0, "return": 0, "transfer": 0}, {}
        
        for log in logs:
            tid = log.related_target_id
            info_list = tag_map.get(tid, [{'run': "N/A", 'cmd': "N/A"}])
            idx = usage_idx.get(tid, 0)
            info = info_list[min(idx, len(info_list)-1)]
            if log.mission_type in ["target", "transfer"]: usage_idx[tid] = idx + 1
            
            s_pos = f"work station {abs(log.src[1])} (Port {log.src[2]})" if log.src[0] == -1 else f"({log.src[0]};{log.src[1]};{log.src[2]})"
            d_pos = f"work station {abs(log.dst[1])} (Port {log.dst[2]})" if log.dst[0] == -1 else f"({log.dst[0]};{log.dst[1]};{log.dst[2]})"
            if log.mission_type in counts: counts[log.mission_type] += 1

            writer.writerow([
                log.mission_no, log.agv_id, log.mission_type, info['run'], info['cmd'], 
                log.container_id-1, tid-1, s_pos, d_pos, log.start_time, log.end_time, 
                log.start_time-epoch, log.end_time-epoch, log.makespan, sku_map.get(tid, 0), log.duration_detail
            ])

    print(f"\n--- Simulation Summary ---")
    print(f"Total Missions: {len(logs)}")
    print(f"Target: {counts['target']} | Reshuffle: {counts['reshuffle']} | Return: {counts['return']} | Transfer: {counts['transfer']}")
    print(f"Final Makespan: {logs[-1].makespan if logs else 0:.2f}\n")

if __name__ == "__main__":
    main()
