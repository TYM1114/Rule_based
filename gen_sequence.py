import csv
import random
import sys
import os

# --- Parsing Tools ---
def parse_location_id(loc_id):
    if not loc_id or len(loc_id) < 10: return -1, -1, -1
    return int(loc_id[0:5]), int(loc_id[5:8]), int(loc_id[8:10])

def parse_carrier_id(car_id):
    if not car_id: return 0
    clean_id = ''.join(filter(str.isdigit, car_id))
    return int(clean_id) + 1 if clean_id else 0

def generate_optimized_sequence(num_batches=10):
    print(f"--- Generating Optimized Sequence from {num_batches} random batches ---")
    
    # 1. 獲取所有可用的 Run IDs
    all_ids = []
    try:
        with open('DB/cur_cmd_master.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            all_ids = list(set(row['selection_run_id'] for row in reader))
    except FileNotFoundError:
        print("Error: DB/cur_cmd_master.csv not found.")
        return

    if not all_ids:
        print("Error: No Run IDs found.")
        return

    selected_ids = random.sample(all_ids, min(num_batches, len(all_ids)))
    print(f"Selected Batches: {selected_ids}")

    # 2. 獲取場景與任務池
    inv_scenario = ""
    all_target_dest_map = {} # parent_id -> [dest_bays]
    cmd_info_map = {}        # parent_id -> {cmd_id, batch_id, ...}
    
    with open('DB/cur_cmd_master.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['selection_run_id'] in selected_ids:
                if not inv_scenario: inv_scenario = row['inv_scenario']
                p_id = parse_carrier_id(row['parent_carrier_id'])
                if p_id == 0: continue
                
                ws_num = int(row['dest_position'])
                dest_bay = -(ws_num + 1)
                
                if p_id not in all_target_dest_map:
                    all_target_dest_map[p_id] = []
                    cmd_info_map[p_id] = row
                all_target_dest_map[p_id].append(dest_bay)

    # 3. 讀取庫存與映射
    carrier_to_parent = {}
    with open('DB/cur_carrier.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            carrier_to_parent[row['carrier_id']] = parse_carrier_id(row['parent_carrier_id'])

    box_pos = {} # id -> (r, b, l)
    stacks = {}  # (r, b) -> [ids sorted by level 0..7]
    with open('DB/cur_inventory.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['scenario'] == inv_scenario:
                p_id = carrier_to_parent.get(row['carrier_id'])
                if p_id and p_id in all_target_dest_map:
                    r, b, l = parse_location_id(row['location_id'])
                    box_pos[p_id] = (r, b, l)
                    stacks.setdefault((r, b), []).append(p_id)
    
    for col in stacks:
        stacks[col].sort(key=lambda x: box_pos[x][2])

    target_set = set(all_target_dest_map.keys())
    target_stacks = {}
    for tid in target_set:
        if tid in box_pos:
            col = (box_pos[tid][0], box_pos[tid][1])
            target_stacks.setdefault(col, []).append(tid)
    for col in target_stacks:
        target_stacks[col].sort(key=lambda x: box_pos[x][2]) # 從 Level 小 (底部) 開始

    # 4. 懸吊系統評分邏輯
    def get_score(tid):
        r, b, l = box_pos[tid]
        wbi, wui, wdi = [2.0, 5.0, 0.5]
        # Bi: 下方阻擋 (Level < l)
        bi = sum(1 for o in stacks[(r, b)] if box_pos[o][2] < l)
        # Ui: 上方解鎖 (Level > l 且是目標)
        ui = sum(1 for o in stacks[(r, b)] if o in target_set and box_pos[o][2] > l)
        # Di: 距離 (假設工作站在 Row -1, Bay -1/-2/-3)
        di = min(abs(r - (-1)) + abs(b - (-(w+1))) for w in range(3))
        return (wbi * bi) - (wui * ui) + (wdi * di)

    # 5. Greedy 排序
    final_seq = []
    candidates = {col: s.pop(0) for col, s in target_stacks.items() if s}

    while candidates:
        best_tid = min(candidates.values(), key=get_score)
        final_seq.append(best_tid)
        best_col = (box_pos[best_tid][0], box_pos[best_tid][1])
        if target_stacks.get(best_col):
            candidates[best_col] = target_stacks[best_col].pop(0)
        else:
            del candidates[best_col]

    # 6. 寫入結果
    output_file = 'resequence.csv'
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        # 保持與 cur_cmd_master.csv 相同的格式
        fieldnames = ["selection_run_id", "inv_scenario", "parent_carrier_id", "dest_position", "cmd_id"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        new_run_id = "RESEQ_" + "".join(random.choices("0123456789", k=5))
        for tid in final_seq:
            info = cmd_info_map[tid]
            writer.writerow({
                "selection_run_id": new_run_id,
                "inv_scenario": inv_scenario,
                "parent_carrier_id": info['parent_carrier_id'],
                "dest_position": info['dest_position'],
                "cmd_id": info['cmd_id']
            })

    print(f"Done! Resequenced {len(final_seq)} jobs into {output_file}")
    return output_file, new_run_id


if __name__ == '__main__':
    n = 10
    if len(sys.argv) > 1:
        n = int(sys.argv[1])
    generate_optimized_sequence(n)
