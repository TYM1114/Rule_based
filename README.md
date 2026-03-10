# RB Solver (Rule-Based Operations Solver)

此專案為專注於 **規則導向 (Rule-Based, RB)** 的倉儲作業最佳化引擎，主要負責管理懸吊式儲存系統中的 AGV 調度，包括出庫 (Target)、回庫 (Return)、翻箱 (Reshuffle) 與轉運 (Transfer) 任務。

---


### 1. 編譯：
```bash
python setup.py build_ext --inplace
```

### 2. 執行模擬
您可以手動指定任務批次 ID，或直接執行以讀取預設任務：
```bash
# 方式 A: 指定 ID
python main.py 20260203174303

# 方式 B: 執行後依提示輸入
python main.py
```

---

##  物理規則與邏輯 (Physical Logic)


1.  **底部存取**：AGV 僅能從最下方進行取箱或放箱。
2.  **垂直阻擋 (Vertical Blocking)**：
    *   **低層級 (Level 小) 阻擋高層級 (Level 大)**。
    *   *範例*：要拿到頂層 Level 7 的箱子，必須先移走掛在同一個 Bay 下方 Level 0~6 的所有箱子。
3.  **翻箱規則 (Reshuffle)**：
    *   當發生阻擋時，系統會從該 Bay **最底層 (Level 0)** 的箱子開始搬移至其他可用儲位。
4.  **掛載規則**：
    *   箱子「由上往下」掛載。第一個箱子放在 Level 7，後續箱子依序掛在現有箱子的下方。

---

## 三、 數據來源 (Data Sources)

系統從 `DB/` 目錄下的 CSV 檔案讀取數據：
*   **`cur_cmd_master.csv`**：定義任務 ID (`selection_run_id`) 與目標工作站。
*   **`cur_inventory.csv`**：根據場景 (`inv_scenario`) 初始化貨架上的箱子分佈。
*   **`cur_carrier.csv`**：映射 Carrier ID 與 Parent Carrier ID。
*   **`cur_cmd_detail.csv`**：提供 SKU 數量以計算揀貨時間。

**座標解析規則** (`location_id`):
*   `0000100205` -> Row: `00001` (x), Bay: `002` (y), Level: `05` (z)。

---

## 四、 輸出結果說明

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
