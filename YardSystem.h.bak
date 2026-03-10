#ifndef YARDSYSTEM_H
#define YARDSYSTEM_H

#include <vector>
#include <iostream>
#include <algorithm>

struct Coordinate {
    int row; // x
    int bay; // y
    int tier; // z

    bool operator==(const Coordinate& other) const {
        return row == other.row && bay == other.bay && tier == other.tier;
    }
};

class YardSystem {
public:
    std::vector<std::vector<std::vector<int>>> grid;
    std::vector<Coordinate> boxLocations;
    std::vector<std::vector<int>> nextAvailableTier; // 下一個可以放箱子的層級 (懸吊系統：最下方箱子的下面)

    int MAX_ROWS;
    int MAX_BAYS;
    int MAX_TIERS;

    YardSystem() : MAX_ROWS(0), MAX_BAYS(0), MAX_TIERS(0) {}

    YardSystem(int rows, int bays, int tiers, int totalBoxes) 
        : MAX_ROWS(rows), MAX_BAYS(bays), MAX_TIERS(tiers) {
        
        grid.assign(rows, std::vector<std::vector<int>>(bays, std::vector<int>(tiers, 0)));
        nextAvailableTier.assign(rows, std::vector<int>(bays, tiers - 1));
        boxLocations.assign(totalBoxes + 10, {-1, -1, -1});
    }

    void updateNextAvailable(int r, int b) {
        if (r < 0 || r >= MAX_ROWS || b < 0 || b >= MAX_BAYS) return;
        // 從底部(0)向上找第一個有箱子的位置
        for (int t = 0; t < MAX_TIERS; ++t) {
            if (grid[r][b][t] > 0) {
                nextAvailableTier[r][b] = t - 1; // 下一個箱子放它下面
                return;
            }
        }
        nextAvailableTier[r][b] = MAX_TIERS - 1; // 如果全空，從頂部(7)開始掛
    }

    void initBox(int boxId, int r, int b, int t) {
        if (r < 0 || r >= MAX_ROWS || b < 0 || b >= MAX_BAYS || t < 0 || t >= MAX_TIERS) return;
        if (boxId <= 0 || boxId >= (int)boxLocations.size()) return;

        grid[r][b][t] = boxId;
        boxLocations[boxId] = {r, b, t};
        updateNextAvailable(r, b);
    }

    // 懸吊系統的 moveBox：移走最下方的箱子，放到另一個 Bay 的最下方
    bool moveBox(int fromRow, int fromBay, int toRow, int toBay) {
        if (fromRow < 0 || fromRow >= MAX_ROWS || fromBay < 0 || fromBay >= MAX_BAYS) return false;
        if (toRow < 0 || toRow >= MAX_ROWS || toBay < 0 || toBay >= MAX_BAYS) return false;
        
        // 找到來源 Bay 最下方的箱子 (即 t = nextAvailableTier + 1)
        int currentTier = -1;
        for (int t = 0; t < MAX_TIERS; ++t) {
            if (grid[fromRow][fromBay][t] > 0) {
                currentTier = t;
                break;
            }
        }
        if (currentTier == -1) return false;

        int boxId = grid[fromRow][fromBay][currentTier];
        int targetTier = nextAvailableTier[toRow][toBay];
        
        if (targetTier < 0) return false; // 目標 Bay 已滿(到底了)

        // 執行移動
        grid[fromRow][fromBay][currentTier] = 0; 
        grid[toRow][toBay][targetTier] = boxId; 
        boxLocations[boxId] = {toRow, toBay, targetTier};

        updateNextAvailable(fromRow, fromBay);
        updateNextAvailable(toRow, toBay);

        return true;
    }

    void removeBox(int boxId) {
        if (boxId <= 0 || boxId >= (int)boxLocations.size()) return;
        Coordinate pos = boxLocations[boxId];
        if (pos.row < 0) return;

        grid[pos.row][pos.bay][pos.tier] = 0;
        boxLocations[boxId] = {-1, -1, -1}; 
        updateNextAvailable(pos.row, pos.bay);
    }

    Coordinate getBoxPosition(int boxId) const {
        if (boxId <= 0 || boxId >= (int)boxLocations.size()) return {-1, -1, -1};
        return boxLocations[boxId];
    }

    // 阻擋判定：在懸吊系統中，下方(Level較小)的箱子阻擋了上方(Level較大)的箱子
    std::vector<int> getBlockingBoxes(int boxId) const {
        std::vector<int> blockers;
        if (boxId <= 0 || boxId >= (int)boxLocations.size()) return blockers;
        Coordinate pos = boxLocations[boxId];
        if (pos.row < 0) return blockers;

        // AGV 從下面來，所以 0 ... pos.tier-1 是阻擋物
        for (int t = 0; t < pos.tier; ++t) {
            int b_id = grid[pos.row][pos.bay][t];
            if (b_id > 0) blockers.push_back(b_id);
        }
        // 注意：為了 Reshuffle 邏輯，順序應該是從最下面開始移，所以要 reverse 或保持 0->tier 順序
        return blockers; 
    }

    bool canReceiveBox(int r, int b) const {
        if (r < 0 || r >= MAX_ROWS || b < 0 || b >= MAX_BAYS) return false;
        return nextAvailableTier[r][b] >= 0;
    }

    bool isTop(int boxId) const {
        if (boxId <= 0) return true;
        Coordinate pos = boxLocations[boxId];
        if (pos.row < 0) return true; 

        // 檢查下方是否有任何箱子
        for (int t = 0; t < pos.tier; ++t) {
            if (grid[pos.row][pos.bay][t] > 0) return false;
        }
        return true;
    }
};

#endif
