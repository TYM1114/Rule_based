# RB Solver (Rule-Based Operations Solver)

此專案為專注於 **規則導向 (Rule-Based, RB)** 的倉儲作業最佳化引擎，主要負責管理黑盒子儲存系統 (Black Box Storage) 中的 AGV 調度，包括出庫 (Target)、回庫 (Return) 與翻箱 (Reshuffle) 任務。

## 專案概述

本系統透過預設的啟發式規則 (Heuristics) 來優化貨櫃在儲存區與工作站之間的移動。核心邏輯由 C++ 撰寫以確保運算效能，並透過 Cython 封裝供 Python 環境呼叫。

### 核心功能
- **純規則導向調度 (Pure Rule-Based Scheduling)**：採用啟發式演算法進行 AGV 與任務分配。
- **懸吊式系統優化 (Suspended System Logic)**：針對底部存取、向下掛載的物理結構進行路徑與阻擋優化。
- **智慧回庫演算法 (Enhanced Return-to-Storage Logic)**：優先選擇未來任務阻擋最少且路徑成本最低的儲位。
- **序列優化 (Sequence Optimization)**：透過 `gen_sequence.py` 從多個批次中挑選並生成最優化任務序列。
- **資料庫整合 (DB Integration)**：支援透過 SQLAlchemy 從 PostgreSQL 自動抓取並導出 CSV 數據。

## 架構說明

- **Python 層 (流程調度與模擬)**：
  - `main.py`：主流程控制。支援從 `resequence.csv` 讀取優化序列，並執行 `rb_solver`。
  - `DB.py` & `models.py`：資料庫連接與 ORM 定義。負責從雲端/本地數據庫同步數據。
  - `gen_sequence.py`：任務重排優化邏輯，旨在降低翻堆率 (Reshuffle Rate)。
- **Cython 橋接層**：
  - `rb_solver.pyx`：封裝 C++ `YardSystem`，實作任務分配、翻堆與回庫決策。
- **C++ 核心層**：
  - `YardSystem.h`：定義 **懸吊式 3D 矩陣**。包含 `nextAvailableTier` 計算、垂直阻擋判定與物理移動邏輯。

## 物理規則與邏輯 (Physical Rules)

### 1. 懸吊式系統架構 (Suspended System)
- **存取方向**：AGV 從 **底部 (Level 0 之下)** 進行取箱與放箱。
- **座標定義**：
  - **Level 7**：最頂層 (靠近天花板，起始掛載位置)。
  - **Level 0**：最底層 (靠近地面，存取口位置)。
- **掛載規則**：箱子是「由上往下」掛載。第一個箱子掛在 Level 7，後續箱子掛在現有最下方箱子的下方 (z - 1)。
- **阻擋判定 (Vertical Blocking)**：
  - **下方阻擋上方**：Level 較小的箱子會阻擋 Level 較大的箱子。
  - *範例*：若要取出 Level 7 的箱子，必須先將 Level 0~6 的所有箱子進行翻箱 (Reshuffle)。

### 2. 儲位搜尋邏輯 (Slot Searching)
- **可用位置**：新的箱子必須放置在該 Bay 目前 **最下方箱子的更下方**。
- **層級計算**：`nextAvailableTier` 若為空則從 `MAX_TIERS - 1` (Level 7) 開始。

## 資料對應與初始化 (Data Mapping)

### 1. 數據獲取與同步
- 使用 `python DB.py` 同步最新庫存與命令資料至 `DB/` 目錄下。
- 數據源包括：`cur_inventory.csv`, `cur_carrier.csv`, `cur_cmd_master.csv`, `cur_cmd_detail.csv`。

### 2. 座標解析 (Location ID: 10位數)
- **Row (x)**：`id[0:5]` (0-5)
- **Bay (y)**：`id[5:8]` (0-10)
- **Level (z)**：`id[8:10]` (0-7)

### 3. ID 映射基準
- 系統內部統一使用 **Parent Carrier ID** 作為唯一標識符。
- 解析邏輯：`int(''.join(filter(str.isdigit, car_id))) + 1` (確保 ID > 0)。

## 編譯與執行

### 1. 環境準備
'''bash
pip install setuptools numpy cython pandas sqlalchemy psycopg2-binary python-dotenv
'''

### 2. 編譯 C++ 核心
'''bash
python setup.py build_ext --inplace
'''

### 3. 執行模擬
- **單一批次**：`python main.py [run_id]`
- **優化序列模式**：`python main.py multi` (會自動觸發 `gen_sequence.py`)

## 測試與驗證 (Testing Standards)
- **Makespan 評估**：計算總完工時間，目標為最小化 AGV 閒置與翻箱等待。
- **輸出紀錄**：`output_missions_python.csv` 包含詳細的任務分解 (Target, Reshuffle, Return, Transfer) 與時間戳。
- **驗證指標**：確保同一時間同一座標僅有一個箱子，且 AGV 任務路徑在時間軸上不重疊。
