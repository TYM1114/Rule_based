from libcpp.vector cimport vector
from libcpp.unordered_map cimport unordered_map

cdef extern from "YardSystem.h":
    """
    #ifndef AGENT_DEFINED
    #define AGENT_DEFINED
    #include "YardSystem.h"
    struct Agent {
        int id;
        Coordinate currentPos;
        double availableTime;
    };
    #endif
    """
    struct Coordinate:
        int row
        int bay
        int tier

    struct Agent:
        int id
        Coordinate currentPos
        double availableTime

    cppclass YardSystem:
        YardSystem() nogil
        YardSystem(int rows, int bays, int tiers, int totalBoxes) nogil
        void initBox(int boxId, int r, int b, int t) nogil
        void moveBox(int r1, int b1, int r2, int b2) nogil
        void removeBox(int id) nogil
        Coordinate getBoxPosition(int id) nogil
        bint isTop(int id) nogil
        vector[int] getBlockingBoxes(int id) nogil
        bint canReceiveBox(int r, int b) nogil
        int MAX_ROWS, MAX_BAYS, MAX_TIERS
        vector[vector[vector[int]]] grid
        vector[vector[int]] nextAvailableTier
