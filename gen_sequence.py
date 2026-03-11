import csv
import sys
import os
from datetime import datetime, timedelta

# --- Parsing Tools ---
def parse_location_id(loc_id):
    if not loc_id or len(loc_id) < 10: return -1, -1, -1
    return int(loc_id[0:5]), int(loc_id[5:8]), int(loc_id[8:10])

def parse_carrier_id(car_id):
    if not car_id: return 0
    clean_id = ''.join(filter(str.isdigit, car_id))
    return int(clean_id) + 1 if clean_id else 0

def generate_optimized_sequence(num_batches=10, start_id=None):
    print(f"--- Generating Optimized Sequence (Count: {num_batches}, Start ID: {start_id or 'Minimum'}) ---")
    
    selected_ids = []
    inv_scenario = ""
    all_target_dest_map = {} 
    cmd_info_map = {}        
    
    csv_source = 'DB/cur_cmd_master.csv'
    try:
        with open(csv_source, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            start_collecting = (start_id is None)
            
            for row in reader:
                current_run_id = row['selection_run_id']
                if not start_collecting:
                    if current_run_id == start_id: start_collecting = True
                    else: continue
                
                if current_run_id not in selected_ids:
                    if len(selected_ids) >= num_batches: break
                    selected_ids.append(current_run_id)
                
                if not inv_scenario: inv_scenario = row['inv_scenario']
                p_id = parse_carrier_id(row['parent_carrier_id'])
                if p_id == 0: continue
                
                ws_num = int(row['dest_position'])
                dest_bay = -(ws_num + 1)
                
                if p_id not in all_target_dest_map:
                    all_target_dest_map[p_id] = []
                    cmd_info_map[p_id] = [] # Changed to list to store all destination rows
                all_target_dest_map[p_id].append(dest_bay)
                cmd_info_map[p_id].append(row) # Store all matching rows for this carrier
                
    except FileNotFoundError:
        print(f"Error: {csv_source} not found.")
        return None, None

    if not selected_ids:
        print("Error: No IDs collected.")
        return None, None

    print(f"Collected Batches: {selected_ids}")

    # 3. 讀取庫存與映射
    carrier_to_parent = {}
    with open('DB/cur_carrier.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            carrier_to_parent[row['carrier_id']] = parse_carrier_id(row['parent_carrier_id'])

    box_pos, stacks = {}, {}
    with open('DB/cur_inventory.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['scenario'] == inv_scenario:
                p_id = carrier_to_parent.get(row['carrier_id'])
                if p_id and p_id in all_target_dest_map:
                    r, b, l = parse_location_id(row['location_id'])
                    box_pos[p_id] = (r, b, l)
                    stacks.setdefault((r, b), []).append(p_id)
    
    for col in stacks: stacks[col].sort(key=lambda x: box_pos[x][2])

    target_set = set(all_target_dest_map.keys())
    target_stacks = {}
    for tid in target_set:
        if tid in box_pos:
            col = (box_pos[tid][0], box_pos[tid][1])
            target_stacks.setdefault(col, []).append(tid)
    for col in target_stacks: target_stacks[col].sort(key=lambda x: box_pos[x][2])

    # 4. 懸吊系統評分邏輯 (Greedy 排序)
    def get_score(tid):
        r, b, l = box_pos[tid]
        bi = sum(1 for o in stacks[(r, b)] if box_pos[o][2] < l)
        ui = sum(1 for o in stacks[(r, b)] if o in target_set and box_pos[o][2] > l)
        di = min(abs(r - (-1)) + abs(b - (-(w+1))) for w in range(3))
        return (2.0 * bi) - (5.0 * ui) + (0.5 * di)

    final_seq, candidates = [], {col: s.pop(0) for col, s in target_stacks.items() if s}

    while candidates:
        best_tid = min(candidates.values(), key=get_score)
        final_seq.append(best_tid)
        best_col = (box_pos[best_tid][0], box_pos[best_tid][1])
        if target_stacks.get(best_col): candidates[best_col] = target_stacks[best_col].pop(0)
        else: del candidates[best_col]

    # 6. 寫入結果
    output_file = 'resequence.csv'
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        # 新增 original_run_id 欄位
        fieldnames = ["selection_run_id", "original_run_id", "inv_scenario", "parent_carrier_id", "dest_position", "cmd_id"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        local_now = datetime.now() + timedelta(hours=8)
        new_run_id = "RESEQ_" + local_now.strftime("%Y%m%d_%H%M%S")
        
        for tid in final_seq:
            # Write ALL destination rows for this carrier to support Transfer missions
            for info in cmd_info_map[tid]:
                writer.writerow({
                    "selection_run_id": new_run_id,
                    "original_run_id": info['selection_run_id'], # 保存原始 Run ID
                    "inv_scenario": inv_scenario,
                    "parent_carrier_id": info['parent_carrier_id'],
                    "dest_position": info['dest_position'],
                    "cmd_id": info['cmd_id']
                })

    print(f"Done! Resequenced {len(final_seq)} jobs into {output_file}")
    return output_file, new_run_id

if __name__ == '__main__':
    count = 10
    start = None
    if len(sys.argv) > 1: count = int(sys.argv[1])
    if len(sys.argv) > 2: start = sys.argv[2]
    generate_optimized_sequence(count, start)
