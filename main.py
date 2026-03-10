import csv
import time
import rb_solver
import sys

# --- Parsing Tools ---
def parse_location_id(loc_id):
    if not loc_id or len(loc_id) < 10: return -1, -1, -1
    # Chars 0-4: Row, 5-7: Bay, 8-9: Level
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
    max_id = 0
    
    config = {
        'max_row': 6, 
        'max_bay': 11, 
        'max_level': 8,
        'total_boxes': max_id + 1000,
        'agv_count': 5, 
        'port_count': 3, 
        'workstation_count': 3,
        't_travel': 5.0, 
        't_handle': 30.0, 
        't_process': 10.0, 
        't_pick': 2.0,
        'sim_start_epoch': 1705363200, 
        'w_penalty_lookahead': 500.0,
    } 
    # 1. Get scenario and sequence
    try:
        with open('DB/cur_cmd_master.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['selection_run_id'] == run_id:
                    inv_scenario = row['inv_scenario']
                    p_id = parse_carrier_id(row['parent_carrier_id'])
                    if p_id == 0: continue
                    ws_num = int(row['dest_position'])
                    dest_bay = -(ws_num + 1)
                    cmd_to_parent[row['cmd_id']] = p_id
                    job_sequence.append(p_id)
                    if p_id not in target_dest_map: target_dest_map[p_id] = []
                    target_dest_map[p_id].append(dest_bay)
    except FileNotFoundError:
        print("Warning: cur_cmd_master.csv not found.")

    # 2. Map carrier_id to parent_carrier_id
    carrier_to_parent = {}
    try:
        with open('DB/cur_carrier.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                c_id = row['carrier_id']
                p_id = parse_carrier_id(row['parent_carrier_id'])
                carrier_to_parent[c_id] = p_id
                if p_id > max_id: max_id = p_id
    except FileNotFoundError:
        print("Warning: cur_carrier.csv not found.")

    # 3. Initialize yard boxes based on cur_inventory
    boxes = []
    seen_parents = set()
    used_locations = set()
    try:
        with open('DB/cur_inventory.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['scenario'] == inv_scenario:
                    c_id = row['carrier_id']
                    p_id = carrier_to_parent.get(c_id)
                    loc_id = row['location_id']
                    
                    if p_id and p_id not in seen_parents and loc_id not in used_locations:
                        r, b, l = parse_location_id(loc_id)
                        if 0 <= r < 6 and 0 <= b < 11 and 0 <= l < 8:
                            boxes.append({'id': p_id, 'row': r, 'bay': b, 'level': l})
                            seen_parents.add(p_id)
                            used_locations.add(loc_id)
                            if p_id > max_id: max_id = p_id
    except FileNotFoundError:
        print("Warning: cur_inventory.csv not found.")

    # 4. Filter job sequence to ensure targets exist in current yard
    valid_job_sequence = [t for t in job_sequence if t in seen_parents]
    
    sku_map = {}
    try:
        with open('DB/cur_cmd_detail.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                p_id = cmd_to_parent.get(row['cmd_id'])
                if p_id: 
                    sku_map[p_id] = sku_map.get(p_id, 0) + int(row['quantity'])
    except FileNotFoundError:
        print("Warning: cur_cmd_detail.csv not found.")


    
    print(f"Final Count: {len(boxes)} boxes. Max ID: {max_id}. Jobs: {len(valid_job_sequence)}")
    return config, boxes, valid_job_sequence, sku_map, target_dest_map

def main():
    try:
        with open('DB/cur_cmd_master.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            test_run_id = row['selection_run_id']
    except Exception as e:
        print(f"Error reading initial run_id: {e}")
        return

    config, boxes, job_sequence, sku_map, target_dest_map = load_data_v4(test_run_id)
    logs = rb_solver.run_rb_solver(config, boxes, job_sequence, sku_map, target_dest_map)
    
    output_file = 'output_missions_python.csv'
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "mission_no", "agv_id", "mission_type", "container_id", "related_target_id", 
            "src_pos", "dst_pos", "start_time", "end_time", "start_s", "end_s", 
            "makespan", "sku_qty", "picking_duration(s)"
        ])
        
        epoch = config['sim_start_epoch']
        t_pick = config['t_pick']
        t_proc = config['t_process']
        
        for log in logs:
            s_pos = f"work station {abs(log.src[1])} (Port {log.src[2]})" if log.src[0] == -1 else f"({log.src[0]};{log.src[1]};{log.src[2]})"
            d_pos = f"work station {abs(log.dst[1])} (Port {log.dst[2]})" if log.dst[0] == -1 else f"({log.dst[0]};{log.dst[1]};{log.dst[2]})"
            current_sku = sku_map.get(log.related_target_id, 0)
            pick_dur_str = f"{t_proc} + {current_sku * t_pick} + {t_proc}" if log.mission_type == "target" and log.dst[0] == -1 else "0.0"

            writer.writerow([
                log.mission_no, log.agv_id, log.mission_type, log.container_id - 1, log.related_target_id - 1,
                s_pos, d_pos, log.start_time, log.end_time, log.start_time - epoch, log.end_time - epoch,
                log.makespan, current_sku, pick_dur_str
            ])
    print(f"Done. Makespan: {logs[-1].makespan if logs else 0:.2f}")

if __name__ == "__main__":
    main()
