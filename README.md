

## 數據來源 (Data Sources)

系統從 `DB/` 目錄下的 CSV 檔案讀取數據：
*   **`cur_cmd_master.csv`**：定義任務 ID (`selection_run_id`) 與目標工作站。
*   **`cur_inventory.csv`**：根據場景 (`inv_scenario`) 初始化貨架上的箱子分佈。
*   **`cur_carrier.csv`**：映射 Carrier ID 與 Parent Carrier ID。
*   **`cur_cmd_detail.csv`**：提供 SKU 數量以計算揀貨時間。

**座標解析規則** (`location_id`):
*   `0000100205` -> Row: `00001` (x), Bay: `002` (y), Level: `05` (z)。

---

## 輸出結果說明

### 1. 任務清單 (`output_missions_python.csv`)
紀錄每台 AGV 的詳細動作，關鍵欄位如下：
*   **`start_s` / `end_s`**：
    *   **定義**：僅計入 AGV **接觸箱子** 的時間（排除空車移動）。
    *   **Target 任務**：`end_s` 額外包含交接時間 (`t_process`)。
*   **`duration_breakdown`**：展示任務時間組成。
    *   格式：`t_handle + (移動與等待) + t_handle (+ t_process for Target)`。

### 2. 模擬摘要 (Console Summary)
模擬結束後，終端機會印出本次執行的統計數據：
*   各任務類型 (Target, Reshuffle, Return, Transfer) 的總次數。
*   總完工時間 (Final Makespan)。

---

## 五、 專案架構
*   `YardSystem.h`：C++ 核心物理引擎，定義 3D 矩陣與阻擋判定。
*   `rb_solver.pyx`：Cython 橋接層，實作算法。
*   `main.py`：主程式，負責數據解析與結果輸出。
*   `models.py`：Python 層的資料結構定義。
