# RB Solver (Rule-Based Operations Solver)

此專案為專注於 **規則導向 (Rule-Based, RB)** 的倉儲作業最佳化引擎，主要負責管理黑盒子儲存系統 (Black Box Storage) 中的 AGV 調度，包括出庫 (Target)、回庫 (Return) 與翻箱 (Reshuffle) 任務。

## 專案概述

編譯指令
'''bash
pip install setuptools numpy cython pandas matplotlib

python setup.py build_ext --inplace

python main.py
'''
本系統透過預設的啟發式規則 (Heuristics) 來優化貨櫃在儲存區與工作站之間的移動。核心邏輯由 C++ 撰寫以確保運算效能，並透過 Cython 封裝供 Python 環境呼叫與測試。

### 核心功能
- **純規則導向調度 (Pure Rule-Based Scheduling)**：完全採用啟發式演算法進行 AGV 與任務分配。
- **懸吊式系統優化 (Suspended System Logic)**：針對底部存取、向下掛載的物理結構進行路徑與阻擋優化。
- **智慧回庫演算法 (Enhanced Return-to-Storage Logic)**：優先選擇未來任務阻擋最少且路徑成本最低的儲位。
- **前瞻性阻擋評估 (Lookahead Penalty)**：在移動貨櫃時，根據未來任務序列對可能造成阻擋的動作進行懲罰權重計算。

## 架構說明

- **Python 層 (流程調度與模擬)**：
  - `main.py`：資料載入與主流程，負責從 CSV 初始化堆場狀態並執行模擬。
  - `models.py`：定義資料結構。
- **Cython 橋接層**：
  - `rb_solver.pyx`：封裝 C++ `YardSystem`，實作任務分配、翻堆與回庫決策邏輯。
- **C++ 核心層**：
  - `YardSystem.h`：定義 **懸吊式 3D 矩陣**。包含 `nextAvailableTier` 計算、垂直阻擋判定與物理移動邏輯。

## 物理規則與邏輯 (Physical Rules)

### 1. 懸吊式系統架構 (Suspended System)
- **存取方向**：AGV 從 **底部 (Level 0 之下)** 進行取箱與放箱。
- **座標定義**：
  - **Level 7**：最頂層 (靠近天花板，起始掛載位置)。
  - **Level 0**：最底層 (靠近地面，存取口位置)。
- **掛載規則**：箱子是「由上往下」掛載。第一個箱子放在 Level 7，後續箱子依序掛在現有箱子的下方。
- **阻擋判定 (Vertical Blocking)**：
  - **下方阻擋上方**：Level 較小的箱子會阻擋 Level 較大的箱子。
  - *範例*：若要取出 Level 7 的箱子，必須先移走掛在同一個 Bay 中 Level 0~6 的所有箱子。

### 2. 儲位搜尋邏輯 (Slot Searching)
- **可用位置**：新的箱子 (Return 或 Reshuffle) 必須放置在該 Bay 目前 **最下方箱子的更下方**。
- **層級計算**：透過 `nextAvailableTier` 動態追蹤每個 Bay 下一個可掛載的 Level。

## 資料對應與初始化 (Data Mapping & Initialization)

### 1. 庫存初始化基準 (Source of Truth)
- **初始狀態**：必須以 `cur_inventory.csv` 為基準。
- **情境過濾**：根據 `inv_scenario` 篩選對應情境的箱子分佈。
- **映射關係**：透過 `cur_carrier.csv` 將 `carrier_id` (子容器) 映射回 `parent_carrier_id` (實體箱子)，並以此進行 `YardSystem` 初始化。

### 2. 儲位編碼與座標解析
- **Row (x)**：`int(location_id[0:5])` (範圍 0-5)
- **Bay (y)**：`int(location_id[5:8])` (範圍 0-10)
- **Level (z)**：`int(location_id[8:10])` (範圍 0-7)

### 3. 工作站座標對應 (Workstations)
- **目的地座標**：格式為 `(-1, -ws_num, -1)`。
- **映射邏輯**：`dest_position` (0, 1) 映射為 `ws_num`，對應座標之 Bay 數值為 `-1, -2` 等。

## 編譯與執行

### 編譯指令
```bash
python setup.py build_ext --inplace
```

### 執行模擬
```bash
python main.py
```

## 測試規範 (Testing Standards)
- **Makespan 評估**：以單個 `selection_run_id` 為一組任務，計算總完工時間。
- **驗證指標**：所有 `target` 任務必須完成且對應生成 `return` 任務，且所有 Reshuffle 動作必須符合垂直存取物理規則。

---

# 核心邏輯與數據抓取更新 (v1.1)

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
