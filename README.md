# RB Solver (Rule-Based Operations Solver) 專案文檔

本系統為 **懸吊式 3D 倉儲** 的調度優化引擎，採用 **Python (流程) + Cython (橋接) + C++ (物理核心)** 架構。

## 一、 數據來源與抓取邏輯 (Data Sources)

系統模擬的所有初始狀態與任務指令均從以下 CSV 檔案抓取：

### 1. 任務與場景定義 (`cur_cmd_master.csv`)
*   **抓取欄位**：`selection_run_id` (測試批次 ID), `inv_scenario` (庫存場景名稱), `parent_carrier_id` (目標箱子), `dest_position` (目標工作站)。
*   **用途**：決定本次模擬要執行哪一組任務，以及初始場景。

### 2. 初始庫存分佈 (`cur_inventory.csv`)
*   **抓取欄位**：`scenario` (對應場景), `carrier_id` (子容器), `location_id` (10位數座標字串)。
*   **用途**：根據 `inv_scenario` 篩選出所有箱子的初始位置。

### 3. 載體映射關係 (`cur_carrier.csv`)
*   **抓取欄位**：`carrier_id`, `parent_carrier_id`。
*   **用途**：將子容器 ID 統一映射為 **Parent ID**（實體箱子），作為模擬器中的唯一標識符。

### 4. 訂單明細 (`cur_cmd_detail.csv`)
*   **抓取欄位**：`cmd_id`, `quantity` (SKU 數量)。
*   **用途**：計算 Picking 時間（公式：`t_process + qty * t_pick + t_process`）。

---

## 二、 座標解析與空間定義

針對 `location_id` (10位字串，如 `0000100205`) 的解析規則：
*   **Row (x)**：`id[0:5]` -> 第 1-5 位 (範圍 0-5)。
*   **Bay (y)**：`id[5:8]` -> 第 6-8 位 (範圍 0-10)。
*   **Level (z)**：`id[8:10]` -> 第 9-10 位 (範圍 0-7)。
*   **高度定義**：**Level 7 為天花板（頂層），Level 0 為地面（存取口）**。

---

## 三、 核心物理規則 (Physical Logic)

本系統模擬的是 **懸吊式 (Suspended) 倉儲**，具有以下硬體特性：

1.  **底部存取**：AGV 僅能從最下方（Level 0 之下）進行取箱或放箱。
2.  **垂直阻擋 (Vertical Blocking)**：
    *   低層級 (Level 小) 的箱子會阻擋高層級 (Level 大) 的箱子。
    *   *範例*：要拿到 Level 7 的箱子，必須先移走掛在它下方的 Level 0~6 箱子。
3.  **翻箱規則 (Reshuffle)**：
    *   當發生阻擋時，系統會從 **該 Bay 最底層 (Level 0)** 的箱子開始搬移。
    *   代碼實作：選取 `blockers[0]` 作為翻箱對象，確保與 C++ 物理狀態同步。
4.  **掛載規則**：
    *   箱子是由上往下掛。第一個箱子掛在 Level 7，後續箱子依序掛在其下方。
    *   新位置必須是該 Bay 目前最下方箱子的 `z - 1`。

---

## 四、 任務類型 (Mission Types)

1.  **Retrieve (出庫/Target)**：將目標箱子從貨架運送到工作站 Port。
2.  **Reshuffle (翻箱)**：將阻擋物移至其他 Bay 的最下方，選擇未來阻擋懲罰最小的儲位。
3.  **Return (回庫)**：任務完成後，根據 **前瞻性阻擋評估 (Lookahead Penalty)** 找尋最優儲位重新掛載。
4.  **Transfer (轉運)**：若箱子有連續多個目的地且 Port 有空位，直接在工作站間移動，不回庫。

---

## 五、 驗證機制

*   **時間驗證**：確保同一台 AGV 沒有重疊任務。
*   **空間驗證**：確保箱子移動路徑連續（起點 = 上次終點），且同一座標同一時間僅有一個箱子。
*   **魯棒性測試**：透過 `batch_test.py` 進行隨機批次測試，確保算法在不同數據分佈下均能正確執行。

---

### 專案結構簡介
*   `YardSystem.h`：C++ 核心物理引擎（不可刪除）。
*   `rb_solver.pyx`：Cython 橋接與任務分配邏輯（核心）。
*   `main.py`：數據讀取、模擬啟動與結果輸出。
