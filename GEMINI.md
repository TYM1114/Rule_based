# RB Solver (Rule-Based Operations Solver)

此專案為專注於 **規則導向 (Rule-Based, RB)** 的倉儲作業最佳化引擎，主要負責管理黑盒子儲存系統 (Black Box Storage) 中的 AGV 調度，包括出庫 (Target)、回庫 (Return) 與翻箱 (Reshuffle) 任務。

## 專案概述

本系統透過預設的啟發式規則 (Heuristics) 來優化貨櫃在儲存區與工作站之間的移動。核心邏輯由 C++ 撰寫以確保運算效能，並透過 Cython 封裝供 Python 環境呼叫。

### 核心功能
- **純規則導向調度 (Pure Rule-Based Scheduling)**：採用啟發式演算法進行 AGV 與任務分配。
- **懸吊式系統優化 (Suspended System Logic)**：針對底部存取、向下掛載的物理結構進行路徑與阻擋優化。
- **智慧回庫演算法 (Enhanced Return-to-Storage Logic)**：優先選擇未來任務阻擋最少且路徑成本最低的儲位。
- **序列優化 (Sequence Optimization)**：透過 `gen_sequence.py` (SequenceOptimizer) 從多個批次中挑選並生成最優化任務序列。
- **資料庫整合 (DB Integration)**：支援透過 SQLAlchemy 從 PostgreSQL 自動抓取並導出 CSV 數據。

## 架構說明 (2026/03/14 升級)

系統已整合現代化基礎設施，提升參數管理、日誌追蹤與資料載入的效率。

- **Python 層 (流程調度與模擬)**：
  - `main.py`：採用 `YardSimulationController` 類別化架構。整合 `DualLogger` 以實現終端機與檔案雙向輸出。支援 `--mode`, `--run_id` 等多樣化參數。
  - `config.yaml`：全域參數設定檔，管理倉儲大小、移動時間、AGV 數量與算法特定權重。
  - `data_generator.py`：取代 `data_loader.py`。支援隨機模擬生成與資料庫匯入，並優化了 `target_dest_map` 的映射邏輯。
  - `gen_sequence.py`：重構為 `SequenceOptimizer` 類別，提供更結構化的任務序列優化 Pipeline。
  - `DB.py` & `models.py`：資料庫連接與 ORM 定義。負責從雲端/本地數據庫同步數據。
- **Cython 橋接層**：
  - `rb_solver.pyx`：封裝 C++ `YardSystem`，實作任務分配、翻堆與回庫決策。**核心邏輯保持不變**。
- **C++ 核心層**：
  - `YardSystem.h`：定義 **懸吊式 3D 矩陣**。包含垂直阻擋判定與物理移動邏輯。

## 物理規則與邏輯 (Physical Rules)

### 1. 懸吊式系統架構 (Suspended System)
- **存取方向**：AGV 從 **底部 (Level 0 之下)** 進行取箱與放箱。
- **座標定義**：**Level 7** (最頂層) 至 **Level 0** (最底層)。
- **掛載規則**：由上往下掛載。
- **阻擋判定**：Level 較小的箱子會阻擋 Level 較大的箱子。

### 2. 儲位搜尋邏輯 (Slot Searching)
- **可用位置**：放置在該 Bay 目前最下方箱子的更下方。
- **層級計算**：`nextAvailableTier` 計算。

## 資料對應與初始化 (Data Mapping)

### 1. 數據獲取與同步
- 使用 `python DB.py` 同步最新庫存與命令資料至 `DB/` 目錄。
- 支援 `.env` 管理資料庫密鑰（參考 `.env.example`）。

### 2. 座標與 ID 映射
- **座標 (10位數)**：`Row[0:5]`, `Bay[5:8]`, `Level[8:10]`。
- **ID 映射**：系統內部統一使用 `Parent Carrier ID` 作為唯一標識符。
- **工作站映射**：WS 0 映射至 Bay -1，WS 1 映射至 Bay -2，依此類推。

## 編譯與執行

### 1. 環境準備
'''bash
pip install setuptools numpy cython pandas sqlalchemy psycopg2-binary python-dotenv pyyaml
'''

### 2. 編譯 C++ 核心
'''bash
python setup.py build_ext --inplace
'''

### 3. 執行模擬
- **資料庫模式 (預設)**：`python main.py --mode db --run_id [ID]`
- **隨機模擬模式**：`python main.py --mode random`
- **優化序列模式 (Multi-batch)**：`python main.py --multi [count] [start_id]`

## 測試與驗證 (Testing Standards)
- **自動化日誌**：每次執行結果自動存於 `logs/YYYYMMDD_HHMMSS/` 下。
- **Makespan 評估**：最小化總完工時間。
- **輸出紀錄**：`output_missions_python.csv` 包含詳細的任務分解 (Target, Reshuffle, Return, Transfer)。
