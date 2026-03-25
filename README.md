# RB Solver (Rule-Based Operations Solver)


## 核心功能與更新 (2026/03/14)

### 1. 高效批量模擬系統
- **`run_experiment_noreset.py`**：支援全自動化的極速批量測試（基於內部引用與記憶體快取）。
- **`run_experiments.py`**：經典批量測試模式（基於 subprocess，每個 ID 獨立重啟）。
- **記憶體快取 (RAM-Caching)**：將大型 CSV 資料 (100MB+) 一次性載入記憶體，執行速度提升 10 倍以上。

### 2. 現代化架構整合
- **`config.yaml`**：統一管理所有物理參數與時間參數。
- **`YardSimulationController`**：封裝模擬流程，支援 `db` 與 `random` 雙模式切換。

---

## 🛠 開發者指南：如何支援高速模擬 (No-Reset Mode)

若要讓 `run_experiment_noreset.py` 正常運作，開發者須在現有架構中實作以下核心邏輯：

### 1. `data_generator.py`：實作記憶體快取類別
必須實作一個類別（如 `BatchDataManager`）來處理全局資料：
- **`load_all_to_ram()`**：在程式啟動時執行一次，將所有大體量 CSV (如 `cur_cmd_detail.csv`) 讀入 `dict` 或 `list` 儲存。
- **`get_data_for_run(run_id)`**：不進行磁碟讀取，改為直接在記憶體中根據 `run_id` 進行資料過濾並返回與原本格式一致的資料結構。

### 2. `main.py`：實作邏輯解耦方法
必須在 `YardSimulationController` 中新增一個不涉及磁碟讀取的方法：
- **`run_with_data(yard_config, boxes, job_sequence, ...)`**：
  - 所有的初始場域狀態、任務序列與加工量映射都必須透過**參數傳遞**進入。
  - 此方法內嚴禁使用 `open()` 讀取任何 CSV。
  - 負責將傳入的參數餵給底層 C++ 核心 (`rb_solver.run_rb_solver`)。

### 3. 參數對齊與翻譯
由於配置檔與 Solver 命名可能不同，需在 `run_with_data` 中完成映射：
- `t_port_handle` (YAML) → `t_process` (Solver 固定加工開銷)
- `t_unit_process` (YAML) → `t_pick` (Solver 單品加工係數)

---

## 資料流程 (Data Bridge)

1. **同步**：`python DB.py` (SQLAlchemy 抓取)。
2. **解析**：`data_generator.py` 處理座標與 ID 映射。
3. **執行**：`main.py` 或 `run_experiment_noreset.py` 呼叫核心 `rb_solver`。

## 快速啟動

```bash
# 1. 編譯核心 (修改 C++ 或 Cython 後執行)
python setup.py build_ext --inplace

# 2. 跑單一 ID 測試 (Disk-based)
python main.py --mode db --run_id 20260203174258

# 3. 跑高速批量模擬 (RAM-cached)
python run_experiment_noreset.py
or
python run_experiment_noreset.py --limit 100

```

---


