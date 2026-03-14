# RB Solver (Rule-Based Operations Solver)

基於規則的懸吊式倉儲 AGV 調度引擎。

## 核心功能與更新 (2026/03/14)

### 1. 高效批量模擬系統
- **`run_experiments.py`**：支援全自動化的批量測試。
- **記憶體快取 (RAM-Caching)**：將大型 CSV 資料 (100MB+) 一次性載入記憶體，大幅減少磁碟 I/O，使 100 個實驗可在 10 秒內跑完。
- **獨立日誌系統**：每個實驗結果以 `output_[run_id].csv` 獨立存檔，防止數據覆寫。

### 2. 現代化架構整合
- **`config.yaml`**：統一管理所有物理參數與時間參數 (t_travel, t_handle, t_port_handle, t_unit_process)。
- **`YardSimulationController`**：封裝模擬流程，支援 `db` 與 `random` 雙模式切換。
- **`SequenceOptimizer`**：支援跨批次的任務序列優化，降低翻堆率。

## 資料流程 (Data Bridge)

1. **同步**：`python DB.py` (SQLAlchemy 抓取最新庫存與指令)。
2. **解析**：`data_generator.py` 處理 10 位數座標與 ID 映射。
3. **執行**：`main.py` 呼叫編譯後的 C++ 核心 `rb_solver`。

## 快速啟動

```bash
# 1. 編譯核心 (修改 C++ 或 Cython 後執行)
python setup.py build_ext --inplace

# 2. 跑單一 ID 測試
python main.py --mode db --run_id 20260203174258

# 3. 跑批量高效模擬
python run_experiments.py --start_id 20260203174258 --limit 100
```

---

## 注意事項
- **時間參數對應**：
  - `t_port_handle` $\rightarrow$ 對應舊版的 `t_process` (固定加工時間)。
  - `t_unit_process` $\rightarrow$ 對應舊版的 `t_pick` (單一品項加工時間)。
- **日誌位置**：所有產出物皆在 `logs/` 資料夾中。
