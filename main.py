
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
    candidates = [
        (r - 1, c),
        (r + 1, c),
        (r, c - 1),
        (r, c + 1)
    ]
    return [p for p in candidates if valid_position(p, rows, cols)]


def manhattan(a: Position, b: Position) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


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

    if not valid_position(start, rows, cols) or not valid_position(goal, rows, cols):
        return SearchResult(
            algorithm, [], set(), False, 0,
            "출발점 또는 목적지가 지도 밖에 있습니다."
        )

    if grid[start] or grid[goal]:
        return SearchResult(
            algorithm, [], set(), False, 0,
            "출발점과 목적지는 장애물이 될 수 없습니다."
        )

    if start == goal:
        return SearchResult(
            algorithm, [start], {start}, True, 0,
            "출발점과 목적지가 같습니다."
        )

    parent: Dict[Position, Position] = {}
    visited: Set[Position] = {start}
    found = False

    # BFS 알고리즘
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

    # A* 알고리즘
    else:

        queue = [(manhattan(start, goal), 0, start)]
        g_score = {start: 0}
        closed: Set[Position] = set()

        while queue:

            _, current_g, current = heapq.heappop(queue)

            if current in closed or current_g != g_score.get(
                current, float("inf")
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


def make_figure(
    grid: np.ndarray,
    start: Position,
    goal: Position,
    result: SearchResult | None = None,
    robot: Position | None = None
) -> go.Figure:

    rows, cols = grid.shape

    # 0: 빈 칸
    # 1: 장애물
    # 2: 탐색 영역
    # 3: 최종 경로

    values = np.zeros((rows, cols), dtype=int)
    values[grid] = 1

    if result:

        for p in result.visited:
            if valid_position(p, rows, cols) and not grid[p]:
                values[p] = 2

        for p in result.path:
            if valid_position(p, rows, cols) and not grid[p]:
                values[p] = 3

    xs, ys, colors, hover = [], [], [], []

    palette = {
        0: "#F4F6F8",
        1: "#374151",
        2: "#FDE68A",
        3: "#60A5FA"
    }

    for r in range(rows):
        for c in range(cols):

            xs.append(c)
            ys.append(r)

            value = int(values[r, c])
            colors.append(palette[value])

            hover.append(
                f"행: {r}, 열: {c}<br>" +
                {
                    0: "빈 칸",
                    1: "장애물",
                    2: "탐색 영역",
                    3: "최종 경로"
                }[value]
            )

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=xs,
        y=ys,
        mode="markers",
        marker=dict(
            symbol="square",
            size=max(7, min(28, 650 // max(rows, cols))),
            color=colors,
            line=dict(color="#CBD5E1", width=0.7)
        ),
        customdata=[
            [r, c]
            for r in range(rows)
            for c in range(cols)
        ],
        text=hover,
        hovertemplate="%{text}<extra></extra>",
        name="지도"
    ))

    # 출발점
    fig.add_trace(go.Scatter(
        x=[start[1]],
        y=[start[0]],
        mode="markers+text",
        marker=dict(
            symbol="circle",
            size=max(10, min(24, 700 // max(rows, cols))),
            color="#16A34A",
            line=dict(color="white", width=1.5)
        ),
        text=["S"],
        textposition="middle center",
        textfont=dict(color="white"),
        name="출발점"
    ))

    # 목적지
    fig.add_trace(go.Scatter(
        x=[goal[1]],
        y=[goal[0]],
        mode="markers+text",
        marker=dict(
            symbol="star",
            size=max(12, min(27, 750 // max(rows, cols))),
            color="#DC2626",
            line=dict(color="white", width=1)
        ),
        text=["G"],
        textposition="middle center",
        textfont=dict(color="white"),
        name="목적지"
    ))

    # 로봇 위치
    if robot is not None:

        fig.add_trace(go.Scatter(
            x=[robot[1]],
            y=[robot[0]],
            mode="markers",
            marker=dict(
                symbol="diamond",
                size=max(12, min(26, 750 // max(rows, cols))),
                color="#7C3AED",
                line=dict(color="white", width=1.5)
            ),
            name="로봇 위치"
        ))

    fig.update_layout(
        height=min(
            850,
            max(
                350,
                rows * max(8, min(24, 650 // max(rows, cols))) + 100
            )
        ),
        margin=dict(l=10, r=10, t=25, b=10),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0
        ),
        clickmode="event+select",
        plot_bgcolor="white"
    )

    fig.update_xaxes(
        range=[-0.7, cols - 0.3],
        dtick=max(1, cols // 20),
        title="열 (column)",
        showgrid=False,
        zeroline=False
    )

    fig.update_yaxes(
        range=[rows - 0.3, -0.7],
        dtick=max(1, rows // 20),
        title="행 (row)",
        showgrid=False,
        zeroline=False,
        scaleanchor="x"
    )

    return fig


def main():

    st.set_page_config(
        page_title="자율주행 로봇 경로 탐색기",
        page_icon="🤖",
        layout="wide"
    )

    st.title("🤖 자율주행 로봇 경로 탐색기")

    st.caption(
        "지도 크기를 직접 정하고, 지도 칸을 클릭해 장애물을 배치한 뒤 경로를 탐색하세요."
    )

    # 사이드바 설정
    with st.sidebar:

        st.header("지도 설정")

        rows = st.number_input(
            "행 수 (세로)",
            min_value=5,
            max_value=80,
            value=20,
            step=1
        )

        cols = st.number_input(
            "열 수 (가로)",
            min_value=5,
            max_value=80,
            value=20,
            step=1
        )

        algorithm = st.selectbox(
            "탐색 알고리즘",
            ["A*", "BFS", "두 알고리즘 비교"]
        )

        st.caption("예: 행 50, 열 50 → 50×50 칸")

        st.markdown("---")

        st.write("**장애물 배치 방법**")

        st.write(
            "아래 지도에서 빈 칸을 클릭하면 장애물이 추가되고, "
            "장애물 칸을 클릭하면 제거됩니다."
        )

        st.caption("초록색 S: 출발점 · 빨간색 G: 목적지")

    rows, cols = int(rows), int(cols)
    shape = (rows, cols)

    # 지도 초기화
    if (
        "grid" not in st.session_state
        or st.session_state.get("grid_shape") != shape
    ):

        st.session_state.grid = np.zeros(shape, dtype=bool)
        st.session_state.grid_shape = shape
        st.session_state.result_a = None
        st.session_state.result_b = None
        st.session_state.robot_step = 0

    start: Position = (0, 0)
    goal: Position = (rows - 1, cols - 1)

    if "result_a" not in st.session_state:
        st.session_state.result_a = None

    if "result_b" not in st.session_state:
        st.session_state.result_b = None

    # 지도 표시
    st.subheader(f"지도 편집 ({rows} × {cols})")

    st.info(
        "지도 칸을 클릭해 장애물을 배치하거나 제거하세요. "
        "출발점과 목적지는 장애물로 바뀌지 않습니다."
    )

    edit_fig = make_figure(
        st.session_state.grid,
        start,
        goal
    )

    clicked = plotly_events(
        edit_fig,
        click_event=True,
        select_event=False,
        hover_event=False,
        override_height=edit_fig.layout.height,
        key=f"map_click_{rows}_{cols}"
    )

    if clicked:

        point = clicked[-1]

        if "x" in point and "y" in point:

            c = int(round(point["x"]))
            r = int(round(point["y"]))

            pos = (r, c)

            if valid_position(pos, rows, cols) and pos not in (start, goal):

                st.session_state.grid[pos] = not st.session_state.grid[pos]

                st.session_state.result_a = None
                st.session_state.result_b = None
                st.session_state.robot_step = 0

                st.rerun()

    # 버튼
    b1, b2, b3 = st.columns(3)

    with b1:

        if st.button(
            "🧹 장애물 전체 지우기",
            use_container_width=True
        ):

            st.session_state.grid = np.zeros(shape, dtype=bool)
            st.session_state.result_a = None
            st.session_state.result_b = None

            st.rerun()

    with b2:

        if st.button(
            "🎲 무작위 장애물",
            use_container_width=True
        ):

            rng = np.random.default_rng()
            grid = rng.random(shape) < 0.20

            grid[start] = False
            grid[goal] = False

            st.session_state.grid = grid
            st.session_state.result_a = None
            st.session_state.result_b = None

            st.rerun()

    with b3:

        run = st.button(
            "🔎 경로 탐색 및 자동차 이동",
            type="primary",
            use_container_width=True
        )

    # 경로 탐색과 자동차 애니메이션
    if run:

        grid = st.session_state.grid.copy()

        grid[start] = False
        grid[goal] = False

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

        st.session_state.robot_step = 0

        animation_result = (
            st.session_state.result_a
            if st.session_state.result_a is not None
            else st.session_state.result_b
        )

        if animation_result is not None and animation_result.found:

            st.markdown("---")
            st.subheader("🚗 자동차 주행 애니메이션")

            st.caption(
                "지도 크기와 경로 길이에 관계없이 약 5초 동안 주행합니다."
            )

            animation_area = st.empty()

            path = animation_result.path

            frame_count = min(50, max(2, len(path)))

            frame_indices = sorted(set(
                round(
                    i * (len(path) - 1) / (frame_count - 1)
                )
                for i in range(frame_count)
            ))

            animation_started = time.perf_counter()
            total_duration = 5.0

            for frame_number, path_index in enumerate(frame_indices):

                robot_pos = path[path_index]

                frame_fig = make_figure(
                    grid,
                    start,
                    goal,
                    animation_result,
                    robot_pos
                )

                frame_fig.add_trace(go.Scatter(
                    x=[robot_pos[1]],
                    y=[robot_pos[0]],
                    mode="text",
                    text=["🚗"],
                    textfont=dict(
                        size=max(
                            12,
                            min(25, 700 // max(rows, cols))
                        )
                    ),
                    name="자동차",
                    hovertemplate="자동차 현재 위치<extra></extra>",
                    showlegend=False
                ))

                animation_area.plotly_chart(
                    frame_fig,
                    use_container_width=True,
                    key=(
                        f"drive_frame_{rows}_{cols}_"
                        f"{frame_number}_{time.time_ns()}"
                    )
                )

                target_time = (
                    total_duration
                    * (frame_number + 1)
                    / len(frame_indices)
                )

                remaining = (
                    animation_started
                    + target_time
                    - time.perf_counter()
                )

                if remaining > 0:
                    time.sleep(remaining)

            st.success("자동차가 목적지에 도착했습니다!")

    # 탐색 결과
    result_a = st.session_state.result_a
    result_b = st.session_state.result_b

    primary = (
        result_a
        if result_a is not None
        else result_b
    )

    if primary is not None:

        st.markdown("---")
        st.subheader("탐색 결과")

        result_fig = make_figure(
            st.session_state.grid,
            start,
            goal,
            primary
        )

        st.plotly_chart(
            result_fig,
            use_container_width=True
        )

        if primary.found:

            st.success(primary.message)

            st.metric(
                "이동 거리",
                f"{len(primary.path) - 1} 칸"
            )

        else:

            st.warning(primary.message)

            st.metric(
                "이동 거리",
                "경로 없음"
            )

        m1, m2 = st.columns(2)

        m1.metric(
            "탐색 노드 수",
            len(primary.visited)
        )

        m2.metric(
            "실행 시간",
            f"{primary.elapsed_ms:.3f} ms"
        )

        # A*와 BFS 비교
        if result_a is not None and result_b is not None:

            st.subheader("A*와 BFS 비교")

            comparison = {
                "항목": [
                    "경로 발견",
                    "이동 거리(칸)",
                    "탐색 노드 수",
                    "실행 시간(ms)"
                ],

                "A*": [
                    "성공" if result_a.found else "실패",
                    len(result_a.path) - 1 if result_a.found else "—",
                    len(result_a.visited),
                    round(result_a.elapsed_ms, 3)
                ],

                "BFS": [
                    "성공" if result_b.found else "실패",
                    len(result_b.path) - 1 if result_b.found else "—",
                    len(result_b.visited),
                    round(result_b.elapsed_ms, 3)
                ]
            }

            st.dataframe(
                comparison,
                hide_index=True,
                use_container_width=True
            )

        # 로봇 이동 시뮬레이션
        if primary.found:

            st.subheader("🚗 로봇 이동 시뮬레이션")

            step = st.slider(
                "이동 단계",
                0,
                len(primary.path) - 1,
                key="robot_step_slider"
            )

            robot = primary.path[step]

            st.plotly_chart(
                make_figure(
                    st.session_state.grid,
                    start,
                    goal,
                    primary,
                    robot
                ),
                use_container_width=True
            )

            st.write(
                f"현재 위치: 행 {robot[0]}, 열 {robot[1]}"
            )

            if step == len(primary.path) - 1:
                st.success("로봇이 목적지에 도착했습니다.")

    # 알고리즘 설명
    with st.expander("알고리즘 설명"):

        st.markdown(
            "**BFS**는 가까운 칸부터 탐색하며, "
            "모든 이동 비용이 같을 때 최단 경로를 찾습니다.\n\n"

            "**A\\***는 실제 이동 비용 `g(n)`과 "
            "목적지까지의 예상 비용 `h(n)`을 더한 "
            "`f(n)=g(n)+h(n)`을 기준으로 탐색합니다. "

            "이 앱은 상하좌우 이동에 맞는 맨해튼 거리를 사용합니다.\n\n"

            "이 앱은 경로 탐색 학습용 시뮬레이터이며 "
            "실제 로봇의 센서나 물리적 움직임을 제어하지 않습니다."
        )


if __name__ == "__main__":
    main()
