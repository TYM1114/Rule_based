# distutils: language = c++
# cython: language_level=3

from libcpp.vector cimport vector
from libcpp.unordered_map cimport unordered_map
from libc.math cimport abs
from yard_system cimport YardSystem, Coordinate, Agent

cdef class PyMissionLog:
    cdef public int mission_no, agv_id, container_id, related_target_id
    cdef public str mission_type, duration_detail
    cdef public tuple src, dst
    cdef public long long start_time, end_time
    cdef public double makespan

def run_rb_solver(dict config, list boxes, list sequence, dict sku_map, dict target_dest_map):
    cdef int i, r, b, t, k, a, p, targetId, blockerId, bestAgvIdx, bestPort, best_return_agv_idx
    cdef int box_id, target_count, path_length, tier_idx, min_target_count_so_far, min_path_so_far
    cdef double minPenalty, bestFinish, bestStart, start, finish, arrivalAtPort, processStart, portFinish, penalty, current_pickup_end
    cdef double best_return_finish, best_return_start, temp_finish_time, container_ready_time, travel_to_port, pickup_start, pickup_end, arrival_at_dst, dropoff_start, best_return_pickup_start
    cdef double best_dropoff_start, best_process_start, best_pickup_end
    cdef unordered_map[int, bint] remaining_targets_map
    cdef list potential_slots, best_class_slots
    cdef dict best_slot
    cdef double travel_to_src, travel_to_dst, pickupTime
    cdef double final_travel_to_src, final_pickupTime # Phase 2 變數
    cdef Coordinate src_coord, bestDst_coord, current_pos_ws
    cdef vector[int] blockers
    cdef bint found_slot, is_returned
    cdef int bestWorkstation, w_id, workstation_bay, best_w_id, schedule_idx, next_schedule_idx, next_dest_bay, next_w_id, best_free_port, current_ws_bay, current_ws_port
    cdef double earliest_free_time, current_makespan
    
    # 系統初始化
    cdef YardSystem yard = YardSystem(config['max_row'], config['max_bay'], config['max_level'], config['total_boxes'])
    for box_item in boxes:
        yard.initBox(box_item['id'], box_item['row'], box_item['bay'], box_item['level'])
        
    cdef vector[int] c_seq
    for seq_item in sequence: c_seq.push_back(seq_item)
    cdef unordered_map[int, int] c_sku_map
    for sku_id, sku_val in sku_map.items(): c_sku_map[sku_id] = sku_val

    # New data structures for multi-destination schedules
    cdef unordered_map[int, vector[int]] c_target_schedules
    cdef unordered_map[int, int] c_target_schedule_idx
    for target_id, dest_list in target_dest_map.items():
        c_target_schedule_idx[target_id] = 0
        for dest_bay in dest_list:
            c_target_schedules[target_id].push_back(dest_bay)

    cdef int agvCount = config['agv_count']
    cdef int portCount = config['port_count']
    cdef int workstationCount = config.get('workstation_count', 1)
    cdef double w_lookahead = config['w_penalty_lookahead']
    cdef double t_travel = config['t_travel']
    cdef double t_handle = config['t_handle']
    cdef double t_process = config['t_process']
    cdef double t_pick = config['t_pick']
    long_long_start_time = config['sim_start_epoch']
    cdef long long sim_start = long_long_start_time

    cdef unordered_map[int, double] containerAvailableTime 
    cdef vector[vector[double]] portBusyTime
    portBusyTime.resize(workstationCount + 1, vector[double](portCount + 1, 0.0))
    cdef vector[vector[double]] gridBusyTime
    gridBusyTime.resize(yard.MAX_ROWS, vector[double](yard.MAX_BAYS, 0.0))
    
    cdef vector[Agent] agvs
    cdef Agent tmp_agv
    for i in range(agvCount):
        tmp_agv.id = i
        tmp_agv.currentPos = Coordinate(0, 0, 0)
        tmp_agv.availableTime = 0.0
        agvs.push_back(tmp_agv)

    cdef list py_logs = []

    cdef int reshuffle_count = 0
    # 任務主迴圈 (changed to while loop for dynamic resizing)
    i = 0
    while i < <int>c_seq.size():
        targetId = c_seq[i]

        # Create a set of remaining targets for efficient lookup
        remaining_targets_map.clear()
        for k in range(i, <int>c_seq.size()):
            remaining_targets_map[c_seq[k]] = True

# Phase 1: Reshuffle (翻堆)
        reshuffle_count = 0
        while not yard.isTop(targetId):
            reshuffle_count += 1
            if reshuffle_count > 100: break
            blockers = yard.getBlockingBoxes(targetId)
            if blockers.empty(): break
            blockerId = blockers[0] # Changed from blockers.back() to pick the bottom-most blocker
            src_coord = yard.getBoxPosition(blockerId)
            if src_coord.row == -1: break 

            bestDst_coord = Coordinate(-1, -1, -1)
            minPenalty = 1e18
            for r in range(yard.MAX_ROWS):
                for b in range(yard.MAX_BAYS):
                    if r == src_coord.row and b == src_coord.bay: continue
                    if not yard.canReceiveBox(r, b): continue
                    penalty = 0
                    t = yard.nextAvailableTier[r][b]
                    if t < yard.MAX_TIERS - 1:
                        for k in range(i, <int>c_seq.size()):
                            if c_seq[k] == yard.grid[r][b][t+1]:
                                penalty = w_lookahead / <double>(k - i + 1)
                                break
                    if penalty < minPenalty:
                        minPenalty = penalty; bestDst_coord = Coordinate(r, b, t)

           
            bestFinish = 1e18
            bestAgvIdx = -1
            bestStart = 0.0
            bestPickupStart = 0.0
            bestPickupEnd = 0.0
            bestDropoffStart = 0.0
            pickupTime = 0.0
            for a in range(agvCount):
                # 1. 提前出發時間
                start_move = max(agvs[a].availableTime, containerAvailableTime[blockerId])
                # 2. 抵達起點並等待
                at_src = start_move + (abs(agvs[a].currentPos.row - src_coord.row) + abs(agvs[a].currentPos.bay - src_coord.bay)) * t_travel
                pickup_start = max(at_src, gridBusyTime[src_coord.row][src_coord.bay])
                pickup_end = pickup_start + t_handle
                # 3. 搬運至終點並等待
                at_dst = pickup_end + (abs(src_coord.row - bestDst_coord.row) + abs(src_coord.bay - bestDst_coord.bay)) * t_travel
                dropoff_start = max(at_dst, gridBusyTime[bestDst_coord.row][bestDst_coord.bay])
                finish = dropoff_start + t_handle
            
                if finish < bestFinish:
                    bestFinish = finish; bestAgvIdx = a; bestStart = start_move
                    bestPickupStart = pickup_start
                    bestPickupEnd = pickup_end
                    bestDropoffStart = dropoff_start
                    pickupTime = pickup_end # 箱子離開貨架的時刻 

            if bestDst_coord.row != -1 and bestAgvIdx != -1:
                yard.moveBox(src_coord.row, src_coord.bay, bestDst_coord.row, bestDst_coord.bay)
                agvs[bestAgvIdx].availableTime = bestFinish
                agvs[bestAgvIdx].currentPos = bestDst_coord
                containerAvailableTime[blockerId] = bestFinish 
                gridBusyTime[src_coord.row][src_coord.bay] = pickupTime # 釋放起點
                gridBusyTime[bestDst_coord.row][bestDst_coord.bay] = bestFinish
                
                pl = PyMissionLog()
                pl.mission_no = len(py_logs) + 1; pl.agv_id = bestAgvIdx; pl.mission_type = "reshuffle"
                pl.container_id = blockerId; pl.related_target_id = targetId
                pl.src = (src_coord.row, src_coord.bay, src_coord.tier); pl.dst = (bestDst_coord.row, bestDst_coord.bay, bestDst_coord.tier)
                pl.start_time = <long long>(bestPickupStart + sim_start); pl.end_time = <long long>(bestFinish + sim_start); pl.makespan = bestFinish
                pl.duration_detail = f"{t_handle} + {bestDropoffStart - bestPickupEnd} + {t_handle}"
                py_logs.append(pl)
            else:
                # 找不到儲位或 AGV，跳出當前目標的 Reshuffle
                break

# Phase 2: Target Retrieval (出庫)
        src_coord = yard.getBoxPosition(targetId)
        if src_coord.row == -1: 
            i += 1
            continue

        final_travel_to_src = 0.0 # 此處保留原變數名
        final_pickupTime = 0.0
        bestFinish = 1e18
        bestPort = -1
        bestAgvIdx = -1
        bestStart = 0.0
        bestPickupStart = 0.0
        bestPickupEnd = 0.0
        bestDropoffStart = 0.0
        bestWorkstation = -1
        current_pickup_end = 0.0

        schedule_idx = c_target_schedule_idx[targetId]
        workstation_bay = c_target_schedules[targetId][schedule_idx]
        w_id = -workstation_bay

        for a in range(agvCount):
            for p in range(1, portCount + 1):
                # 1. 提前出發
                start_move = max(agvs[a].availableTime, containerAvailableTime[targetId])
                # 2. 抵達起點與等待
                at_src = start_move + (abs(agvs[a].currentPos.row - src_coord.row) + abs(agvs[a].currentPos.bay - src_coord.bay)) * t_travel
                pickup_start = max(at_src, gridBusyTime[src_coord.row][src_coord.bay])
                pickup_end = pickup_start + t_handle
                # 3. 搬運至 Port 與等待
                at_port = pickup_end + (abs(src_coord.row - (-1)) + abs(src_coord.bay - workstation_bay)) * t_travel
                processStart = max(at_port, portBusyTime[w_id][p])
                finish_dropoff = processStart + t_handle 
                
                # 計算 Picking 完工時間供 Phase 3 使用
                portFinish = finish_dropoff + t_process + c_sku_map[targetId] * t_pick
                
                if portFinish < bestFinish:
                    bestFinish = portFinish
                    bestAgvIdx = a
                    bestWorkstation = workstation_bay
                    bestPort = p
                    bestStart = start_move
                    bestPickupStart = pickup_start
                    bestPickupEnd = pickup_end
                    bestDropoffStart = processStart
                    final_pickupTime = finish_dropoff # End_s = 140
                    current_pickup_end = pickup_end # 80s

        yard.removeBox(targetId)
        agvs[bestAgvIdx].availableTime = final_pickupTime 
        agvs[bestAgvIdx].currentPos = Coordinate(-1, bestWorkstation, bestPort)
        best_w_id = -bestWorkstation
        portBusyTime[best_w_id][bestPort] = bestFinish
        gridBusyTime[src_coord.row][src_coord.bay] = current_pickup_end # 80s 釋放起點
        
        pl = PyMissionLog()
        pl.mission_no = len(py_logs) + 1; pl.agv_id = bestAgvIdx; pl.mission_type = "target"
        pl.container_id = targetId; pl.related_target_id = targetId
        pl.src = (src_coord.row, src_coord.bay, src_coord.tier); pl.dst = (-1, bestWorkstation, bestPort)
        pl.start_time = <long long>(bestPickupStart + sim_start)
        pl.end_time = <long long>(final_pickupTime + t_process + sim_start)
        pl.makespan = final_pickupTime + t_process
        pl.duration_detail = f"{t_handle} + {bestDropoffStart - bestPickupEnd} + {t_handle} + {t_process}"
        py_logs.append(pl)

# Phase 3: Dynamic Return/Transfer Logic
        is_returned = False
        current_makespan = final_pickupTime 
        current_pos_ws = Coordinate(-1, bestWorkstation, bestPort)
        
        while not is_returned:
            schedule_idx = c_target_schedule_idx[targetId]
            next_schedule_idx = schedule_idx + 1

            if next_schedule_idx < <int>c_target_schedules[targetId].size():
                # This container has a next stop.
                next_dest_bay = c_target_schedules[targetId][next_schedule_idx]
                next_w_id = -next_dest_bay

                # Find if a port is free at the destination workstation "now" (at current_makespan)
                earliest_free_time = 1e18
                best_free_port = -1
                for p in range(1, portCount + 1):
                    if portBusyTime[next_w_id][p] < earliest_free_time:
                        earliest_free_time = portBusyTime[next_w_id][p]
                        best_free_port = p

                if earliest_free_time <= current_makespan:
                    # Port is available, execute direct transfer.
                    c_target_schedule_idx[targetId] = next_schedule_idx
                    
                    # --- Start Transfer Mission Logic ---
                    best_return_finish = 1e18
                    best_return_agv_idx = -1
                    best_return_start = 0.0
                    best_transfer_pickup_start = 0.0
                    best_transfer_pickup_end = 0.0
                    best_transfer_dropoff_start = 0.0

                    container_ready_time = portBusyTime[best_w_id][bestPort]

                    for a in range(agvCount):
                        travel_to_port = (abs(agvs[a].currentPos.row - current_pos_ws.row) + abs(agvs[a].currentPos.bay - current_pos_ws.bay)) * t_travel
                        arrival_at_port = agvs[a].availableTime + travel_to_port
                        pickup_start = max(arrival_at_port, container_ready_time)
                        pickup_end = pickup_start + t_handle
                        
                        travel_to_dst = (abs(current_pos_ws.row - (-1)) + abs(current_pos_ws.bay - next_dest_bay)) * t_travel
                        arrival_at_dst = pickup_end + travel_to_dst
                        dropoff_start = max(arrival_at_dst, portBusyTime[next_w_id][best_free_port])
                        temp_finish_time = dropoff_start + t_handle
                        
                        if temp_finish_time < best_return_finish:
                            best_return_finish = temp_finish_time
                            best_return_agv_idx = a
                            best_return_start = pickup_start - travel_to_port
                            best_transfer_pickup_start = pickup_start
                            best_transfer_pickup_end = pickup_end
                            best_transfer_dropoff_start = dropoff_start

                    # Update state for transfer
                    if best_return_agv_idx != -1:
                        agvs[best_return_agv_idx].availableTime = best_return_finish
                        agvs[best_return_agv_idx].currentPos = Coordinate(-1, next_dest_bay, best_free_port)
                        portBusyTime[next_w_id][best_free_port] = best_return_finish + t_process + c_sku_map[targetId] * t_pick
                        
                        pl = PyMissionLog()
                        pl.mission_no = len(py_logs) + 1
                        pl.agv_id = best_return_agv_idx
                        pl.mission_type = "transfer"
                        pl.container_id = targetId
                        pl.related_target_id = targetId
                        pl.src = (current_pos_ws.row, current_pos_ws.bay, current_pos_ws.tier)
                        pl.dst = (-1, next_dest_bay, best_free_port)
                        pl.start_time = <long long>(best_transfer_pickup_start + sim_start)
                        pl.end_time = <long long>(best_return_finish + sim_start)
                        pl.makespan = best_return_finish
                        pl.duration_detail = f"{t_handle} + {best_transfer_dropoff_start - best_transfer_pickup_end} + {t_handle}"
                        py_logs.append(pl)

                        # Update current state for the next iteration of the inner loop
                        current_makespan = best_return_finish
                        current_pos_ws = Coordinate(-1, next_dest_bay, best_free_port)
                        best_w_id = next_w_id
                        bestPort = best_free_port
                    else:
                        is_returned = True

                else:
                    # Port is busy. Force return and re-queue.
                    c_seq.push_back(targetId)
                    c_target_schedule_idx[targetId] = next_schedule_idx # Ensure it tries the correct destination next time
                    is_returned = True # Break inner loop
            else:
                # No more destinations. Force return.
                is_returned = True # Break inner loop
            
            if is_returned:
                # Common return-to-yard logic
                best_slot = {'r': -1, 'b': -1, 't': -1}
                min_target_count_so_far = 100000
                min_path_so_far = 100000
                for r in range(yard.MAX_ROWS):
                    for b in range(yard.MAX_BAYS):
                        if yard.canReceiveBox(r, b):
                            target_count = 0
                            t = yard.nextAvailableTier[r][b]
                            if t < yard.MAX_TIERS - 1:
                                for k in range(i, <int>c_seq.size()): # Check against future sequence
                                    box_id_in_stack = yard.grid[r][b][t+1]
                                    if remaining_targets_map.count(box_id_in_stack):
                                        target_count += 1
                            path_length = abs(r - current_pos_ws.row) + abs(b - current_pos_ws.bay)
                            if target_count < min_target_count_so_far:
                                min_target_count_so_far = target_count
                                min_path_so_far = path_length
                                best_slot = {'r': r, 'b': b, 't': t}
                            elif target_count == min_target_count_so_far and path_length < min_path_so_far:
                                min_path_so_far = path_length
                                best_slot = {'r': r, 'b': b, 't': t}
                
                bestDst_coord = Coordinate(-1, -1, -1)
                if best_slot['r'] != -1:
                    bestDst_coord = Coordinate(best_slot['r'], best_slot['b'], best_slot['t'])

                if bestDst_coord.row != -1:
                    best_return_finish = 1e18; best_return_agv_idx = -1; best_return_start = 0.0; best_return_pickup_start = 0.0
                    best_return_pickup_end = 0.0; best_return_dropoff_start = 0.0
                    container_ready_time = portBusyTime[best_w_id][bestPort]
                    for a in range(agvCount):
                        travel_to_port = (abs(agvs[a].currentPos.row - current_pos_ws.row) + abs(agvs[a].currentPos.bay - current_pos_ws.bay)) * t_travel
                        arrival_at_port = agvs[a].availableTime + travel_to_port
                        pickup_start = max(arrival_at_port, container_ready_time)
                        pickup_end = pickup_start + t_handle
                        travel_to_dst = (abs(current_pos_ws.row - bestDst_coord.row) + abs(current_pos_ws.bay - bestDst_coord.bay)) * t_travel
                        arrival_at_dst = pickup_end + travel_to_dst
                        dropoff_start = max(arrival_at_dst, gridBusyTime[bestDst_coord.row][bestDst_coord.bay])
                        temp_finish_time = dropoff_start + t_handle
                        if temp_finish_time < best_return_finish:
                            best_return_finish = temp_finish_time; best_return_agv_idx = a
                            best_return_start = pickup_start - travel_to_port; best_return_pickup_start = pickup_start
                            best_return_pickup_end = pickup_end; best_return_dropoff_start = dropoff_start
                    
                    if best_return_agv_idx != -1:
                        yard.initBox(targetId, bestDst_coord.row, bestDst_coord.bay, bestDst_coord.tier)
                        agvs[best_return_agv_idx].availableTime = best_return_finish
                        agvs[best_return_agv_idx].currentPos = bestDst_coord
                        gridBusyTime[bestDst_coord.row][bestDst_coord.bay] = best_return_finish
                        
                        pl = PyMissionLog()
                        pl.mission_no = len(py_logs) + 1; pl.agv_id = best_return_agv_idx; pl.mission_type = "return"
                        pl.container_id = targetId; pl.related_target_id = targetId
                        pl.src = (current_pos_ws.row, current_pos_ws.bay, current_pos_ws.tier)
                        pl.dst = (bestDst_coord.row, bestDst_coord.bay, bestDst_coord.tier)
                        pl.start_time = <long long>(best_return_pickup_start + sim_start); pl.end_time = <long long>(best_return_finish + sim_start)
                        pl.makespan = best_return_finish
                        pl.duration_detail = f"{t_handle} + {best_return_dropoff_start - best_return_pickup_end} + {t_handle}"
                        py_logs.append(pl)
        
        i += 1

    return py_logs
