# RB Solver (Rule-Based Operations Solver)

此專案為專注於 **規則導向 (Rule-Based, RB)** 的倉儲作業最佳化引擎，主要負責管理懸吊式儲存系統中的 AGV 調度，包括出庫 (Target)、回庫 (Return)、翻箱 (Reshuffle) 與轉運 (Transfer) 任務。

---

## 核心工作流與資料橋接 (Workflow & Data Bridge)

本系統採用「非同步資料交換」模式，透過 CSV 檔案作為資料庫與運算引擎之間的橋樑。開發者需遵循以下流程進行完整測試或執行：

### 1. 資料同步 (DB -> CSV)
系統使用 **`DB.py`** 搭配 **`models.py`** (SQLAlchemy) 從 PostgreSQL 抓取最新狀態。
- **執行指令**：`python DB.py`
- **橋接邏輯**：
  - 從資料庫抓取：庫存 (`cur_inventory`)、儲位配置 (`cfg_location`)、任務主表 (`cur_cmd_master`) 與明細 (`cur_cmd_detail`)。
  - **輸出路徑**：所有資料會轉存至 `DB/` 目錄下的 `.csv` 檔案。這些檔案是 RB Solver 的唯一輸入來源。

### 2. 編譯核心 (Cython Build)
由於核心邏輯使用 C++ 撰寫，每次修改 `YardSystem.h` 或 `rb_solver.pyx` 後必須重新編譯：
- **編譯指令**：`python setup.py build_ext --inplace`
- **結構說明**：
  - `YardSystem.h`: 物理規則定義（3D 座標、垂直阻擋）。
  - `yard_system.pxd`: Cython 介面宣告。
  - `rb_solver.pyx`: 啟發式調度演算法實作。

### 3. 序列優化與模擬 (Optimization & Simulation)
透過 **`main.py`** 串接所有邏輯。
- **多批次優化 (推薦)**：執行 `python main.py multi`。
  1. 呼叫 `gen_sequence.py`：讀取 `DB/` 中的任務，進行跨批次序列重排以降低翻箱率，生成 `resequence.csv`。
  2. 呼叫 `rb_solver`：根據優化後的序列，執行物理模擬。
- **單一 ID 模式**：`python main.py [run_id]`。直接執行特定批次，不進行跨批次重排。

### 4. 結果分析 (Output)
- **輸出檔案**：`output_missions_python.csv`。
- 包含所有 AGV 動作指令 (Target, Reshuffle, Return, Transfer) 及其對應的物理時間戳 (makespan)。

---

## 開發者接手指南 (Developer Guide)

### 檔案維護說明
- **修改物理規則 (如儲位層級、阻擋判定)**：修改 `YardSystem.h`。
- **修改調度策略 (如 AGV 分配邏輯、回庫權重)**：修改 `rb_solver.pyx`。
- **修改資料表欄位對應**：修改 `models.py` (資料庫層) 與 `main.py` (讀取層)。
- **修改任務排序邏輯**：修改 `gen_sequence.py`。

### 快速啟動指令 (完整流程)
```bash
# 1. 同步資料庫資料
python DB.py

# 2. 編譯 C++ 核心
python setup.py build_ext --inplace

# 3. 執行多批次優化模擬 (預設抓取前 10 個批次)
python main.py multi
```

### 進階執行參數
- **指定批次數量與起始點**：
  `python main.py multi [批次數量] [起始批次ID]`
  *範例：* `python main.py multi 5 run_20240310_01`

- **僅執行序列優化 (不進行模擬)**：
  `python gen_sequence.py [數量] [起始ID]`

---

## 依賴環境 (Environment)
- Python 3.8+
- Cython, NumPy, Pandas
- SQLAlchemy, Psycopg2 (用於 DB 連線)
- C++ 編譯器 (gcc/clang)
