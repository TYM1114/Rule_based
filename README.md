# Rule-Based Solver

本專案是一個針對**懸吊式自動化倉儲系統**開發的模擬與調度平台。核心演算法採用 Rule-Based 策略，並透過 Cython (C++) 進行運算加速，旨在優化 AGV 的調度、貨櫃的出庫序列以及翻堆（Reshuffle）過程中的儲位分配。

## 系統架構

1.  **資料層 (DB.py / data_generator.py)**：支援從 PostgreSQL 資料庫匯入真實訂單與庫存快照，或隨機生成實驗數據。
2.  **序列優化層 (gen_sequence.py)**：在模擬開始前，根據貨櫃所在的深度與未來需求，對出庫目標進行預排序。
3.  **核心求解器 (rb_solver.pyx / YardSystem.h)**：
    *   **YardSystem (C++)**：管理 3D 網格空間（Row, Bay, Tier），模擬懸吊系統特有的「底部存取」邏輯。
    *   **Rule-Based Solver**：動態計算 AGV 分派、翻堆路徑與工作站轉移邏輯。
4.  **控制與日誌 (main.py)**：協調整體流程，並輸出詳細的任務日誌（Mission Log）與效能統計。

---

## 系統實體狀態 (Entity States)

系統透過以下維度維護即時狀態，作為決策基準：

*   **AGV 狀態**：
    *   `availableTime`：AGV 完成上一個任務並可再次接受分派的時間點。
    *   `currentPos`：AGV 目前所在的 3D 座標（或是工作站 Port）。
*   **儲位/網格狀態 (gridBusyTime)**：
    *   記錄每個 Bay (r, b) 何時會「解鎖」。當 AGV 正在執行存取任務時，該 Bay 會被鎖定，直到 `t_handle` 完成。
*   **工作站 Port 狀態 (portBusyTime)**：
    *   記錄每個 Port 何時完成 Picking（包含 `t_process` + `SKU_qty * t_pick`）。這決定了下一個貨櫃何時能進入，以及當前貨櫃何時能離開。
*   **貨櫃狀態 (containerAvailableTime)**：
    *   貨櫃完成上一步驟（如翻堆、加工）後，可以被下一個 AGV 搬運的時間。

---

## 任務階段狀態機 (Mission Lifecycle States)

每個目標貨櫃的出庫任務會經歷以下狀態轉換：

### State A: 判定與翻堆 (Reshuffle Condition)
*   **進入條件**：目標貨櫃 `targetId` 在目前的序列首位。
*   **判定邏輯**：調用 `yard.isTop(targetId)`。
    *   **True**：進入 **State B (Target Retrieval)**。
    *   **False**：進入 **Reshuffle 迴圈**。
        *   **操作**：尋找最下方的阻擋箱 -> 尋找最佳空位（依據 Lookahead 懲罰值）-> 指派 AGV -> 完成後更新 `gridBusyTime` 與 `containerAvailableTime` -> 重新回到 **State A**。

### State B: 目標出庫 (Target Retrieval)
*   **進入條件**：`targetId` 處於其所在的 Bay 的最下方（無阻擋）。
*   **操作**：計算所有工作站 Port 的完工時間 -> 選擇最快完工的 `(Workstation, Port)`。
*   **轉換**：移動至工作站 -> 進入 **State C (Processing)**。

### State C: 加工處理 (Processing at Workstation)
*   **持續時間**：`t_handle` (放下) + `t_process` (準備時間) + `SKU_qty * t_pick` (揀貨時間)。
*   **狀態更新**：更新 `portBusyTime` 與 `agvs.availableTime`。

### State D: 動態決策：轉移或回庫 (Transfer vs. Return)
加工完成後，系統會檢查 `target_dest_map` 是否還有下一個站點：
1.  **直接轉移 (Transfer)**：
    *   **條件**：有下一個站點 `next_ws` 且該站點有 **閒置 Port**（`earliest_free_time <= current_makespan`）。
    *   **結果**：不回倉儲區，直接從 WS-A 搬運至 WS-B -> 回到 **State C**。
2.  **重新入庫與排隊 (Re-queue & Return)**：
    *   **條件**：`next_ws` 的所有 Port 均在忙碌中，或已無後續站點。
    *   **結果**：執行 Return 任務 -> 尋找倉儲區最優儲位（考慮未來出庫需求）-> 若還有站點，將 `targetId` 重新插入 `c_seq` 的末尾，等待下一次觸發。

---

## 演算法階段說明

### 1. 出庫序列優化 (Sequence Optimization)
在任務開始前，系統會對待出庫清單進行評分，分值愈低優先權愈高：
*   **公式**：`Score = 2.0 * Bi - 5.0 * Ui + 0.5 * Di`
    *   `Bi`：目標箱下方阻擋物數量。
    *   `Ui`：目標箱上方是否藏有其他高優先權目標。
    *   `Di`：距離工作站的距離。

### 2. 懸吊系統物理特性
本模擬器特別模擬了**懸吊式（Top-Down Storage, Bottom-Up Access）**倉儲：
*   **存取點**：AGV 從貨架底部進入。
*   **層級邏輯**：Level 0 為最底層，Level 7 為最頂層。
*   **阻擋判定**：若要取出 Level 3 的貨櫃，Level 0, 1, 2 均視為阻擋物（Blockers）。

---

## 快速開始

### 編譯與執行
1. **編譯核心**：`python setup.py build_ext --inplace`
2. **批量實驗**：`python main.py multi 10 [START_ID]`

---

## 輸出結果
模擬結束後，系統會在 `logs/[TIMESTAMP]/` 下生成：
*   `execution_log.txt`：詳細的系統運行與狀態切換日誌。
*   `output_missions.csv`：包含每一筆任務的詳細執行數據（Makespan, Duration Breakdown 等）。
