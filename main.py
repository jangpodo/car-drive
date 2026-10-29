"""
자율주행 로봇 경로 탐색기
실행: streamlit run main.py
"""

from __future__ import annotations

import heapq
import time
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from streamlit_plotly_events import plotly_events

Position = Tuple[int, int]


@dataclass
class SearchResult:
    algorithm: str
    path: List[Position]
    visited: Set[Position]
    found: bool
    elapsed_ms: float
    message: str


def valid_position(pos: Position, rows: int, cols: int) -> bool:
    return 0 <= pos[0] < rows and 0 <= pos[1] < cols


def neighbors(pos: Position, rows: int, cols: int) -> List[Position]:
    r, c = pos
    candidates = [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]
    return [p for p in candidates if valid_position(p, rows, cols)]


def manhattan(a: Position, b: Position) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def reconstruct_path(parent: Dict[Position, Position], start: Position, goal: Position) -> List[Position]:
    if start == goal:
        return [start]
    if goal not in parent:
        return []
    path = [goal]
    while path[-1] != start:
        path.append(parent[path[-1]])
    return list(reversed(path))


def search(grid: np.ndarray, start: Position, goal: Position, algorithm: str) -> SearchResult:
    began = time.perf_counter()
    rows, cols = grid.shape

    if not valid_position(start, rows, cols) or not valid_position(goal, rows, cols):
        return SearchResult(algorithm, [], set(), False, 0, "출발점 또는 목적지가 지도 밖에 있습니다.")
    if grid[start] or grid[goal]:
        return SearchResult(algorithm, [], set(), False, 0, "출발점과 목적지는 장애물이 될 수 없습니다.")
    if start == goal:
        return SearchResult(algorithm, [start], {start}, True, 0, "출발점과 목적지가 같습니다.")

    parent: Dict[Position, Position] = {}
    visited: Set[Position] = {start}
    found = False

    if algorithm == "BFS":
        queue = deque([start])
        while queue:
            current = queue.popleft()
            if current == goal:
                found = True
                break
            for nxt in neighbors(current, rows, cols):
                if nxt not in visited and not grid[nxt]:
                    visited.add(nxt)
                    parent[nxt] = current
                    queue.append(nxt)
    else:
        queue = [(manhattan(start, goal), 0, start)]
        g_score = {start: 0}
        closed: Set[Position] = set()
        while queue:
            _, current_g, current = heapq.heappop(queue)
            if current in closed or current_g != g_score.get(current, float("inf")):
                continue
            if current == goal:
                found = True
                break
            closed.add(current)
            for nxt in neighbors(current, rows, cols):
