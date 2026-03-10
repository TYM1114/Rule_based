# RB Solver (Rule-Based Operations Solver)



## 核心工作流與資料橋接 (Workflow & Data Bridge)

### 1. 資料同步 (DB -> CSV)
系統使用 **`DB.py`** 從 PostgreSQL 抓取資料並存至 `DB/` 目錄。

### 2. 資料載入與解析 (`data_loader.py`)
為了提高維護性，資料解析邏輯已從 `main.py` 抽離至 **`data_loader.py`**：
- **解析邏輯**：處理 10 位數座標 (`parse_location_id`) 與 Carrier ID 映射。
- **資料封裝**：讀取 CSV 並轉換為 Python 物件，供編譯後的 C++ 核心使用。
- **ID 一致性**：確保 `RESHUFFLE` 與 `RETURN` 任務繼承其目標箱子的 `CMD_ID`，避免受資料庫歷史紀錄干擾。

### 3. 編譯核心 (Cython Build)
每次修改 `YardSystem.h` 或 `rb_solver.pyx` 後必須重新編譯：
- **編譯指令**：`python setup.py build_ext --inplace`

### 4. 序列優化 (`gen_sequence.py`)
- **多批次優化**：跨批次重排任務以降低翻箱率。
- **優化標籤**：生成 `RESEQ_YYYYMMDD_HHMMSS` 格式的 ID 
- **原始追蹤**：在 `resequence.csv` 中保留 `selection_run_id`，確保輸出結果能對應回原始任務。

### 5. 執行模擬 (`main.py`)
- **多批次模式**：`python main.py multi n selection_id`
- **結果輸出**：`output_missions_python.csv` 

---


- **修改資料讀取與欄位對應**：修改 `data_loader.py`。
- **修改物理規則 (如儲位、阻擋判定)**：修改 `YardSystem.h`。
- **修改調度策略**：修改 `rb_solver.pyx`。
- **修改任務排序權重**：修改 `gen_sequence.py`。

---

## 快速啟動指令
```bash
# 1. 同步資料
python DB.py

# 2. 編譯核心
python setup.py build_ext --inplace

# 3. 執行優化模擬
python main.py multi
```
