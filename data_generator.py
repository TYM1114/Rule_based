import argparse
import csv
import random
import time
import os

class YardDataGenerator:
    def __init__(self):
        pass

    # ==========================================
    # 1. 隨機生成模式 (Random Generator Mode)
    # ==========================================
    def generate_random(self, max_row, max_bay, max_level, total_boxes, mission_count, workstation_count):
        capacity = max_row * max_bay * max_level
        if total_boxes > capacity:
            raise ValueError(f"Error: Total boxes exceeds yard capacity!")
        
        heights = [0] * (max_row * max_bay)
        all_boxes = []

        for i in range(1, total_boxes + 1):
            placed = False
            attempts = 0
            while not placed:
                if attempts < 1000:
                    r, b = random.randint(0, max_row - 1), random.randint(0, max_bay - 1)
                    idx = r * max_bay + b
                    attempts += 1
                else:
                    found_slot = False
                    for tr in range(max_row):
                        for tb in range(max_bay):
                            tidx = tr * max_bay + tb
                            if heights[tidx] < max_level:
                                r, b, idx = tr, tb, tidx
                                found_slot = True
                                break
                        if found_slot: break

                if heights[idx] < max_level:
                    all_boxes.append({'id': i, 'row': r, 'bay': b, 'level': heights[idx]})
                    heights[idx] += 1
                    placed = True

        candidates = all_boxes.copy()
        random.shuffle(candidates)
        
        mission_count = min(mission_count, len(candidates))
        base_time = 1705363200

        parent_quantity_map = {}
        job_sequence = []
        target_dest_map = {}

        for i in range(mission_count):
            box = candidates[i]
            p_id = box['id']
            job_sequence.append(p_id)
            
            num_stages = random.randint(1, min(3, workstation_count))
            ws_pool = list(range(0, workstation_count))
            random.shuffle(ws_pool)
            
            # RB Solver expects negative bays for workstations: WS 0 -> -1, WS 1 -> -2
            target_dest_map[p_id] = [-(ws + 1) for ws in ws_pool[:num_stages]]
            parent_quantity_map[p_id] = random.randint(10, 50)

        config_dict = {
            'max_row': max_row, 'max_bay': max_bay, 'max_level': max_level, 'total_boxes': total_boxes,
            'workstation_count': workstation_count
        }

        selection_run_id_info = {
            "Random": {"order_scenario": "random", "selection_algo_ver": "N/A", "batch_algo_ver": "N/A"}
        }
        
        return config_dict, all_boxes, job_sequence, parent_quantity_map, target_dest_map, selection_run_id_info

    # ==========================================
    # 2. 資料庫匯入模式 (DB Import Mode)
    # ==========================================
    def parse_location_id(self, loc_id):
        if not loc_id or len(loc_id) < 10: return -1, -1, -1
        return int(loc_id[0:5]), int(loc_id[5:8]), int(loc_id[8:10])

    def parse_carrier_id(self, car_id):
        if not car_id: return 0
        clean_id = ''.join(filter(str.isdigit, car_id))
        return int(clean_id) + 1 if clean_id else 0

    def load_simulation_data(self, run_id, target_run_id, base_config):
        print(f"\n[DataGen] Loading data for ID: {run_id}")
        job_sequence = []
        target_dest_map = {}
        target_cmd_ids = set() 
        selection_run_id_info = {}

        # Metadata extraction
        try:
            with open('DB/cur_cmd_master.csv', 'r', encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    s_id = str(row.get('selection_run_id', '')).strip()
                    if s_id and s_id not in selection_run_id_info and target_run_id == s_id:
                        selection_run_id_info[s_id] = {
                            'order_scenario': str(row.get('order_scenario', '')).strip() or 'N/A',
                            'inv_scenario': str(row.get('inv_scenario', '')).strip() or 'N/A',
                            'selection_algo_ver': str(row.get('selection_algo_ver', '')).strip() or 'N/A',
                            'batch_algo_ver': str(row.get('batch_algo_ver', '')).strip() or 'N/A'
                        }
        except Exception as e: print(f"Metadata read error: {e}")

        csv_source = 'DB/cur_cmd_master.csv'
        if os.path.exists('resequence.csv'):
            with open('resequence.csv', 'r', encoding='utf-8-sig') as f:
                if run_id in f.read(): csv_source = 'resequence.csv'

        # Step 1: Commands
        inv_scenario = ""
        try:
            with open(csv_source, 'r', encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    csv_run_id = str(row.get('selection_run_id', '')).strip()
                    reseq_run_id = str(row.get('reseq_id', '')).strip()
                    
                    if run_id.strip() in (csv_run_id, reseq_run_id):
                        if not inv_scenario: inv_scenario = str(row.get('inv_scenario', '')).strip()
                        p_id = self.parse_carrier_id(row.get('parent_carrier_id', ''))
                        if p_id == 0: continue
                        
                        dest_str = str(row.get('dest_position', '0')).strip()
                        ws_id = int(dest_str) if dest_str else 0
                        dest_bay = -(ws_id + 1)
                        
                        if p_id not in job_sequence: job_sequence.append(p_id)
                        if p_id not in target_dest_map: target_dest_map[p_id] = []
                        target_dest_map[p_id].append(dest_bay)
                        
                        cmd_id = str(row.get('cmd_id', '')).strip()
                        if cmd_id: target_cmd_ids.add(cmd_id)
        except Exception as e: print(f"Command load error: {e}")

        # Step 2: Carrier Mapping
        carrier_to_parent = {}
        try:
            with open('DB/cur_carrier.csv', 'r', encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    carrier_to_parent[row['carrier_id']] = self.parse_carrier_id(row['parent_carrier_id'])
        except Exception as e: print(f"Carrier mapping error: {e}")

        # Step 3: Inventory
        boxes = []
        seen_parents = set()
        max_id = 0
        try:
            with open('DB/cur_inventory.csv', 'r', encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    if row['scenario'] == inv_scenario:
                        c_id = row.get('carrier_id')
                        p_id = carrier_to_parent.get(c_id)
                        r, b, l = self.parse_location_id(row.get('location_id', ''))
                        if p_id and p_id not in seen_parents:
                            boxes.append({'id': p_id, 'row': r, 'bay': b, 'level': l})
                            seen_parents.add(p_id)
                            if p_id > max_id: max_id = p_id
        except Exception as e: print(f"Inventory load error: {e}")

        # Step 4: SKU Quantity
        parent_quantity_map = {}
        try:
            with open('DB/cur_cmd_detail.csv', 'r', encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    if str(row.get('cmd_id', '')).strip() in target_cmd_ids:
                        c_id = row.get('carrier_id', '').strip()
                        qty = int(float(row.get('quantity', '0') or 0))
                        p_id = carrier_to_parent.get(c_id)
                        if p_id: parent_quantity_map[p_id] = parent_quantity_map.get(p_id, 0) + qty
        except Exception as e: print(f"SKU quantity load error: {e}")
        
        for p_id in job_sequence:
            if p_id not in parent_quantity_map: parent_quantity_map[p_id] = 10 
            
        config = {
            'max_row': base_config['yard']['max_row'],
            'max_bay': base_config['yard']['max_bay'],
            'max_level': base_config['yard']['max_level'],
            'total_boxes': max_id,
            'agv_count': base_config['solver']['agv_count'],
            'port_count': base_config['yard']['port_count'],
            'workstation_count': base_config['yard']['workstation_count']
        }
        return config, boxes, job_sequence, parent_quantity_map, target_dest_map, selection_run_id_info

    def generate_db(self, base_config, run_id, target_run_id):
        return self.load_simulation_data(run_id, target_run_id, base_config)
