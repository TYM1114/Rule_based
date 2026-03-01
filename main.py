import csv
import time
import rb_solver # Rule_based
import gen_yard
import gen_sequence


# parameter

GLOBAL_CONFIG = {
    'max_row': 2,           #6
    'max_bay': 2,          #11
    'max_level': 2,         #8
    'total_boxes': 7,
    'mission_count': 8,   
    'agv_count': 5,        #5
    'beam_width': 200,
    't_travel': 5.0,
    't_handle': 30.0,
    't_process': 10.0,
    't_pick': 2.0,
    'sim_start_epoch': 1705363200,
    'w_penalty_blocking': 2000.0,  
    'w_penalty_lookahead': 500.0,
    'workstation_count': 3,
    'port_count': 2
}

def load_csv_data():
    # 1. Load Config
    # config = {}
    # with open('yard_config.csv', 'r') as f:
    #     reader = csv.DictReader(f)
    #     row = next(reader)
    #     config['max_row'] = int(row['max_row'])
    #     config['max_bay'] = int(row['max_bay'])
    #     config['max_level'] = int(row['max_level'])
    #     config['total_boxes'] = int(row['total_boxes'])
    #     config['t_travel'] = float(row.get('time_travel_unit', 5.0))
    #     config['t_handle'] = float(row.get('time_handle', 30.0))
    #     config['t_process'] = float(row.get('time_process', 10.0))

    # 2. Load Yard
    boxes = []
    with open('mock_yard.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            boxes.append({
                'id': int(row['container_id']),
                'row': int(row['row']),
                'bay': int(row['bay']),
                'level': int(row['level'])
            })

    # 3. Load Commands
    commands = []
    sku_map = {} 
    with open('mock_commands.csv', 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                dr, db, dl = int(row['dest_row']), int(row['dest_bay']), int(row['dest_level'])
            except:
                dr, db, dl = -1, -1, 1

            cid = int(row['parent_carrier_id'])
            qty = int(row.get('sku_qty', 1))
            sku_map[cid] = qty

            commands.append({
                'id': cid,
                'type': row['cmd_type'],
                'dest': {'row': dr, 'bay': db, 'level': dl},
                'sku_qty': qty
            })
            
    return boxes, commands, sku_map

def main():

    gen_yard.generate_yard_with_config(GLOBAL_CONFIG)
    job_sequence = gen_sequence.generate_sequence_with_config(GLOBAL_CONFIG)

    start_t = time.perf_counter()
    
    boxes, commands, sku_map = load_csv_data()
    
    # job_sequence = [cmd['id'] for cmd in commands if cmd['type'] == 'target']
    
    target_dest_map = {}
    for cmd in commands:
        if cmd['type'] == 'target':
            tid = cmd['id']
            dest_bay = cmd['dest']['bay']
            if tid not in target_dest_map:
                target_dest_map[tid] = []
            target_dest_map[tid].append(dest_bay)
    
    # The job_sequence is now the unique list of containers to process
    job_sequence = list(target_dest_map.keys())

    logs = rb_solver.run_rb_solver(GLOBAL_CONFIG, boxes, job_sequence, sku_map, target_dest_map)
    
    # 5. 輸出任務日誌 (含相對秒數與 SKU 詳情)
    with open('output_missions_python.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "mission_no", "agv_id", "mission_type", "container_id", 
            "related_target_id", "src_pos", "dst_pos", "start_time", 
            "end_time", "start_s", "end_s", "makespan", "sku_qty", "picking_duration(s)"
        ])
        
        SIM_START_EPOCH = GLOBAL_CONFIG['sim_start_epoch']
        t_pick_val = GLOBAL_CONFIG['t_pick']
        
        for log in logs:
            if log.src[0] == -1:
                s_str = f"work station {abs(log.src[1])} (Port {log.src[2]})"
            else:
                s_str = f"({log.src[0]};{log.src[1]};{log.src[2]})"
            
            if log.dst[0] == -1:
                d_str = f"work station {abs(log.dst[1])} (Port {log.dst[2]})"
            else:
                d_str = f"({log.dst[0]};{log.dst[1]};{log.dst[2]})"

            target_id = log.related_target_id
            current_sku = sku_map.get(target_id, 0)
            
            if log.mission_type == "target" and log.dst[0] == -1:
                duration = current_sku * t_pick_val
            else:
                duration = 0.0

            writer.writerow([
                log.mission_no, log.agv_id, log.mission_type, log.container_id,
                log.related_target_id, s_str, d_str, log.start_time, log.end_time,
                log.start_time - SIM_START_EPOCH, log.end_time - SIM_START_EPOCH,
                log.makespan, current_sku, duration
            ])

    end_t = time.perf_counter()
    print(f"Total Time: {end_t - start_t:.6f}s")
    if logs:
        print(f"Final Makespan: {logs[-1].makespan:.2f}s")

if __name__ == "__main__":
    main()