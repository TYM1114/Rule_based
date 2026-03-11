import csv
import os

def parse_location_id(loc_id):
    """解析 10 位數座標 ID 為 (Row, Bay, Level)"""
    if not loc_id or len(loc_id) < 10: return -1, -1, -1
    return int(loc_id[0:5]), int(loc_id[5:8]), int(loc_id[8:10])

def parse_carrier_id(car_id):
    """解析 Carrier ID (確保 ID > 0)"""
    if not car_id: return 0
    clean_id = ''.join(filter(str.isdigit, car_id))
    return int(clean_id) + 1 if clean_id else 0

def load_simulation_data(run_id):
    """從 CSV 載入模擬所需的所有資料。"""
    print(f"Reseq_id: {run_id}")
    inv_scenario = ""
    job_sequence = []
    target_dest_map = {}
    cmd_to_parent = {}
    
    csv_source = 'DB/cur_cmd_master.csv'
    if os.path.exists('resequence.csv'):
        with open('resequence.csv', 'r', encoding='utf-8-sig') as f:
            if run_id in f.read():
                csv_source = 'resequence.csv'

    try:
        with open(csv_source, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            filter_col = 'reseq_id' if 'resequence.csv' in csv_source else 'selection_run_id'
            for row in reader:
                if row[filter_col] == run_id:
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
    return config, boxes, valid_job_sequence, sku_map, target_dest_map

def get_tag_map(test_run_id):
    """建立標記映射，僅從當前選定的任務清單抓取 ID。"""
    tag_map = {}
    search_file = 'resequence.csv' if "RESEQ" in test_run_id else 'DB/cur_cmd_master.csv'
    try:
        with open(search_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            filter_col = 'reseq_id' if 'resequence.csv' in search_file else 'selection_run_id'
            for row in reader:
                if row[filter_col] == test_run_id:
                    p_id = parse_carrier_id(row['parent_carrier_id'])
                    orig_run = row['selection_run_id']
                    tag_map.setdefault(p_id, []).append({
                        'run': orig_run, 
                        'cmd': row['cmd_id']
                    })
    except Exception as e:
        print(f"Warning in get_tag_map: {e}")
    return tag_map
