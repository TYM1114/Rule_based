# RB Solver (Rule-Based Operations Solver)

此專案為專注於 **規則導向 (Rule-Based, RB)** 的倉儲作業最佳化引擎，主要負責管理懸吊式儲存系統中的 AGV 調度，包括出庫 (Target)、回庫 (Return)、翻箱 (Reshuffle) 與轉運 (Transfer) 任務。

---

### 專案架構與橋接 (Cython Architecture)
本系統採用 Cython 進行 C++ 核心與 Python 的橋接，並實作了 **定義與邏輯分離** 的維護架構，確保代碼的高效性與可擴展性：

- **`YardSystem.h` (C++)**: 核心物理引擎，定義系統的 3D 座標空間、阻擋判定與移動規則。
- **`yard_system.pxd` (Cython Definition)**: 專屬的橋接定義檔，作為 Python 存取 C++ 的介面宣告。
- **`rb_solver.pyx` (Cython Logic)**: 封裝任務調度的啟發式規則 (Heuristics)。透過 `cimport yard_system` 引入定義，專注於執行出庫、翻箱與回庫的邏輯運算。
- **`main.py` (Python)**: 主控流程。負責從 CSV/DB 載入資料、呼叫 `rb_solver` 並輸出模擬結果。

---

### 1. 編譯：
```bash
python setup.py build_ext --inplace
```

### 2. 執行模擬

您可以手動指定單一任務批次 ID，或使用 **多批次優化模式 (Multi-batch Optimization)** 進行序列重排：

#### A. 多批次優化模式 (推薦)
此模式會從 `cur_cmd_master.csv` 中抓取指定數量的連續批次，並進行懸吊式系統的任務優化排序。

```bash
# 基本用法：抓取前 10 個批次並優化
python main.py multi

# 進階用法：從指定 ID 開始，抓取後續共 n 個批次 (包含起始 ID)
# python main.py multi [批次數量] [起始 ID]
python main.py multi 10 run_20240310_01
```
*   **ID 處理**：支援任何字串格式的 `selection_run_id`。
*   **邏輯**：程式會根據 CSV 中的物理順序，收集從「起始 ID」開始的 $n$ 個唯一 ID。

#### B. 單一 ID 模式
直接執行特定批次 ID 的模擬：
```bash
python main.py [run_id]
```

#### C. 手動重排 (不執行模擬)
如果您只想生成優化後的 `resequence.csv`：
```bash
# python gen_sequence.py [批次數量] [起始 ID]
python gen_sequence.py 5 run_abc_123
```

---

### 3. 輸出紀錄
執行結束後，系統會生成 `output_missions_python.csv`，其中包含：
- **mission_type**: target (出庫), reshuffle (翻箱), return (回庫), transfer (轉運)。
- **makespan**: 總完工時間 (秒)。
- **src_pos / dst_pos**: 物理座標或工作站編號。