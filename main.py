
"""
자율주행 로봇 경로 탐색기
실행: streamlit run main.py
"""

from __future__ import annotations

import heapq
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

Position = Tuple[int, int]

# 마우스 올리기 + F 키 입력을 지원하는 지도 편집기
map_editor = components.declare_component(
    "robot_map_editor",
    path=str(Path(__file__).parent / "map_editor")
)


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
    candidates = [(r-1, c), (r+1, c), (r, c-1), (r, c+1)]
    return [p for p in candidates if valid_position(p, rows, cols)]


def manhattan(a: Position, b: Position) -> int:
    return abs(a[0]-b[0]) + abs(a[1]-b[1])


def reconstruct_path(
    parent: Dict[Position, Position],
    start: Position,
    goal: Position
) -> List[Position]:

    if start == goal:
        return [start]

    if goal not in parent:
        return []

    path = [goal]

    while path[-1] != start:
        path.append(parent[path[-1]])

    return list(reversed(path))


def search(
    grid: np.ndarray,
    start: Position,
    goal: Position,
    algorithm: str
) -> SearchResult:

    began = time.perf_counter()
    rows, cols = grid.shape

    if grid[start] or grid[goal]:
        return SearchResult(
            algorithm, [], set(), False, 0,
            "출발점 또는 목적지에 장애물이 있습니다."
        )

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

            if (
                current in closed
                or current_g != g_score.get(current, float("inf"))
            ):
                continue

            if current == goal:
                found = True
                break

            closed.add(current)

            for nxt in neighbors(current, rows, cols):

                if grid[nxt] or nxt in closed:
                    continue

                new_g = current_g + 1

                if new_g < g_score.get(nxt, float("inf")):

                    g_score[nxt] = new_g
                    parent[nxt] = current

                    heapq.heappush(
                        queue,
                        (
                            new_g + manhattan(nxt, goal),
                            new_g,
                            nxt
                        )
                    )

        visited = closed | ({goal} if found else set())

    path = reconstruct_path(parent, start, goal) if found else []

    elapsed = (time.perf_counter() - began) * 1000

    return SearchResult(
        algorithm,
        path,
        visited,
        bool(path),
        elapsed,
        "경로를 찾았습니다." if path else "목적지까지 경로가 없습니다."
    )


def draw_result(
    grid: np.ndarray,
    start: Position,
    goal: Position,
    result: SearchResult,
    robot: Position | None = None
) -> go.Figure:

    rows, cols = grid.shape
    z = np.zeros((rows, cols), dtype=int)

    z[grid] = 1

    for p in result.visited:
        if not grid[p]:
            z[p] = 2

    for p in result.path:
        if not grid[p]:
            z[p] = 3

    fig = go.Figure(
        go.Heatmap(
            z=z,
            colorscale=[
                [0.00, "#F8FAFC"],
                [0.24, "#F8FAFC"],
                [0.25, "#374151"],
                [0.49, "#374151"],
                [0.50, "#FDE68A"],
                [0.74, "#FDE68A"],
                [0.75, "#60A5FA"],
                [1.00, "#60A5FA"]
            ],
            zmin=0,
            zmax=3,
            showscale=False,
            xgap=2,
            ygap=2,
            hovertemplate="행 %{y}, 열 %{x}<extra></extra>"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[start[1], goal[1]],
            y=[start[0], goal[0]],
            mode="markers+text",
            marker=dict(
                size=18,
                color=["#16A34A", "#DC2626"]
            ),
            text=["S", "G"],
            textposition="middle center",
            textfont=dict(color="white"),
            name="출발점 / 목적지"
        )
    )

    if robot is not None:

        fig.add_trace(
            go.Scatter(
                x=[robot[1]],
                y=[robot[0]],
                mode="markers+text",
                marker=dict(
                    size=20,
                    color="#7C3AED",
                    symbol="diamond"
                ),
                text=["🚗"],
                textposition="top center",
                name="로봇"
            )
        )

    fig.update_layout(
        height=min(
            850,
            max(
                350,
                rows * max(9, min(22, 650 // max(rows, cols))) + 80
            )
        ),
        margin=dict(l=10, r=10, t=20, b=10)
    )

    fig.update_yaxes(autorange="reversed", scaleanchor="x")
    fig.update_xaxes(title="열")

    return fig


def main():

    st.set_page_config(
        page_title="자율주행 로봇 경로 탐색기",
        page_icon="🤖",
        layout="wide"
    )

    st.title("🤖 자율주행 로봇 경로 탐색기")

    st.caption(
        "오른쪽 도구를 선택하고, 원하는 칸에 마우스를 올린 뒤 "
        "F 키를 눌러 배치하세요."
    )

    with st.sidebar:

        st.header("지도 설정")

        rows = int(
            st.number_input("행 수", 5, 60, 20, 1)
        )

        cols = int(
            st.number_input("열 수", 5, 60, 20, 1)
        )

        algorithm = st.selectbox(
            "탐색 알고리즘",
            ["A*", "BFS", "두 알고리즘 비교"]
        )

    shape = (rows, cols)

    if st.session_state.get("grid_shape") != shape:

        st.session_state.grid = np.zeros(shape, dtype=bool)
        st.session_state.start = None
        st.session_state.goal = None
        st.session_state.grid_shape = shape
        st.session_state.result_a = None
        st.session_state.result_b = None

    if "grid" not in st.session_state:
        st.session_state.grid = np.zeros(shape, dtype=bool)

    if "start" not in st.session_state:
        st.session_state.start = None

    if "goal" not in st.session_state:
        st.session_state.goal = None

    left, right = st.columns([5, 1])

    with left:

        st.subheader(f"백지 지도 ({rows} × {cols})")

        obstacles = [
            f"{r},{c}"
            for r in range(rows)
            for c in range(cols)
            if st.session_state.grid[r, c]
        ]

        event = map_editor(
            rows=rows,
            cols=cols,
            obstacles=obstacles,
            start=(
                f"{st.session_state.start[0]},{st.session_state.start[1]}"
                if st.session_state.start else None
            ),
            goal=(
                f"{st.session_state.goal[0]},{st.session_state.goal[1]}"
                if st.session_state.goal else None
            ),
            key="robot_map"
        )

    # F 키 입력 이벤트는 한 번만 처리
    if (
        isinstance(event, dict)
        and event.get("nonce")
        != st.session_state.get("last_event_nonce")
    ):

        st.session_state.last_event_nonce = event.get("nonce")
        cell = event.get("cell", "")

        try:

            r, c = map(int, cell.split(","))
            pos = (r, c)

            if valid_position(pos, rows, cols):

                action = event.get("action")

                if action == "start":

                    st.session_state.start = pos
                    st.session_state.grid[pos] = False

                elif action == "goal":

                    st.session_state.goal = pos
                    st.session_state.grid[pos] = False

                elif action == "obstacle":

                    if pos not in (
                        st.session_state.start,
                        st.session_state.goal
                    ):
                        st.session_state.grid[pos] = True

                elif action == "erase":

                    st.session_state.grid[pos] = False

                    if st.session_state.start == pos:
                        st.session_state.start = None

                    if st.session_state.goal == pos:
                        st.session_state.goal = None

                st.session_state.result_a = None
                st.session_state.result_b = None

                st.rerun()

        except (ValueError, TypeError):
            pass

    st.markdown(
        "**사용 순서:** 오른쪽 도구에서 기능 선택 → "
        "지도 칸에 마우스 올리기 → 키보드 **F** 누르기. "
        "출발점과 목적지는 각각 한 개씩 지정할 수 있어."
    )

    st.caption(
        "초록색 S = 출발점 · 빨간색 G = 종착점 · "
        "짙은 회색 = 장애물"
    )

    st.subheader("도구")

    tool_cols = st.columns(4)

    tool_names = [
        "🟢 출발점",
        "🔴 종착점",
        "⬛ 장애물",
        "⌫ 블럭 삭제"
    ]

    for col, name in zip(tool_cols, tool_names):
        with col:
            st.write(name)

    st.info(
        "실제 도구 선택과 F 키 입력은 "
        "지도 오른쪽의 도구 패널에서 진행해."
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        if st.button("🧹 전체 초기화", use_container_width=True):

            st.session_state.grid = np.zeros(shape, dtype=bool)
            st.session_state.start = None
            st.session_state.goal = None
            st.session_state.result_a = None
            st.session_state.result_b = None

            st.rerun()

    with c2:

        if st.button("🎲 무작위 장애물", use_container_width=True):

            rng = np.random.default_rng()

            st.session_state.grid = rng.random(shape) < 0.20

            if st.session_state.start:
                st.session_state.grid[st.session_state.start] = False

            if st.session_state.goal:
                st.session_state.grid[st.session_state.goal] = False

            st.session_state.result_a = None
            st.session_state.result_b = None

            st.rerun()

    with c3:

        run = st.button(
            "🔎 경로 탐색 및 자동차 이동",
            type="primary",
            use_container_width=True
        )

    if run:

        if (
            st.session_state.start is None
            or st.session_state.goal is None
        ):

            st.warning(
                "먼저 출발점과 종착점을 각각 하나씩 설치해 주세요."
            )

        else:

            grid = st.session_state.grid.copy()
            start = st.session_state.start
            goal = st.session_state.goal

            st.session_state.result_a = (
                search(grid, start, goal, "A*")
                if algorithm in ("A*", "두 알고리즘 비교")
                else None
            )

            st.session_state.result_b = (
                search(grid, start, goal, "BFS")
                if algorithm in ("BFS", "두 알고리즘 비교")
                else None
            )

            result = (
                st.session_state.result_a
                or st.session_state.result_b
            )

            if result and result.found:

                st.subheader("🚗 자동차 주행")

                area = st.empty()
                started = time.perf_counter()

                frames = min(40, max(2, len(result.path)))

                indices = sorted(
                    set(
                        round(
                            i * (len(result.path) - 1) / (frames - 1)
                        )
                        for i in range(frames)
                    )
                )

                for i, idx in enumerate(indices):

                    area.plotly_chart(
                        draw_result(
                            grid,
                            start,
                            goal,
                            result,
                            result.path[idx]
                        ),
                        use_container_width=True,
                        key=f"animation_{i}_{time.time_ns()}"
                    )

                    wait = (
                        5 * (i + 1) / len(indices)
                        - (time.perf_counter() - started)
                    )

                    if wait > 0:
                        time.sleep(wait)

                st.success("목적지에 도착했습니다!")

            elif result:

                st.warning(result.message)

    for result in (
        st.session_state.result_a,
        st.session_state.result_b
    ):

        if result is not None:

            st.subheader(f"{result.algorithm} 탐색 결과")
            st.write(result.message)

            st.metric(
                "이동 거리",
                f"{len(result.path)-1}칸"
                if result.found else "경로 없음"
            )

            m1, m2 = st.columns(2)

            m1.metric("탐색 노드 수", len(result.visited))
            m2.metric("실행 시간", f"{result.elapsed_ms:.3f} ms")

            if (
                st.session_state.start
                and st.session_state.goal
            ):

                st.plotly_chart(
                    draw_result(
                        st.session_state.grid,
                        st.session_state.start,
                        st.session_state.goal,
                        result
                    ),
                    use_container_width=True
                )


if __name__ == "__main__":
    main()
