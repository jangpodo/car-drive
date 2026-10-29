"""
자율주행 로봇 경로 탐색 시뮬레이터

실행 방법:
    pip install streamlit numpy matplotlib
    streamlit run main.py
"""

from __future__ import annotations

import heapq
import random
import time
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

Position = Tuple[int, int]


@dataclass
class SearchResult:
    algorithm: str
    path: List[Position]
    visited: Set[Position]
    found: bool
    elapsed_ms: float
    explored_count: int
    message: str = ""


def manhattan(a: Position, b: Position) -> int:
    """상하좌우 이동 격자에서 맨해튼 거리를 계산한다."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def valid_position(pos: Position, rows: int, cols: int) -> bool:
    """좌표가 지도 범위 안에 있는지 확인한다."""
    return 0 <= pos[0] < rows and 0 <= pos[1] < cols


def neighbors(pos: Position, rows: int, cols: int) -> List[Position]:
    """상하좌우 이웃 좌표를 반환한다."""
    r, c = pos
    candidates = [
        (r - 1, c),
        (r + 1, c),
        (r, c - 1),
        (r, c + 1),
    ]
    return [
        p for p in candidates
        if valid_position(p, rows, cols)
    ]


def reconstruct_path(
    came_from: Dict[Position, Position],
    start: Position,
    goal: Position,
) -> List[Position]:
    """부모 좌표 정보를 따라 최종 경로를 만든다."""
    if start == goal:
        return [start]

    if goal not in came_from:
        return []

    path = [goal]
    current = goal

    while current != start:
        current = came_from[current]
        path.append(current)

    path.reverse()
    return path


def bfs_search(
    grid: np.ndarray,
    start: Position,
    goal: Position,
) -> SearchResult:
    """BFS로 최단 경로를 탐색한다."""
    started = time.perf_counter()
    rows, cols = grid.shape

    if (
        not valid_position(start, rows, cols)
        or not valid_position(goal, rows, cols)
    ):
        return SearchResult(
            "BFS", [], set(), False, 0.0, 0,
            "좌표가 지도 범위를 벗어났습니다.",
        )

    if grid[start] or grid[goal]:
        return SearchResult(
            "BFS", [], set(), False, 0.0, 0,
            "출발점 또는 목적지가 장애물입니다.",
        )

    if start == goal:
        elapsed = (time.perf_counter() - started) * 1000
        return SearchResult(
            "BFS", [start], {start}, True, elapsed, 1,
            "출발점과 목적지가 같습니다.",
        )

    queue = deque([start])
    visited = {start}
    came_from: Dict[Position, Position] = {}
    found = False

    while queue:
        current = queue.popleft()

        if current == goal:
            found = True
            break

        for nxt in neighbors(current, rows, cols):
            if nxt not in visited and not grid[nxt]:
                visited.add(nxt)
                came_from[nxt] = current
                queue.append(nxt)

    path = (
        reconstruct_path(came_from, start, goal)
        if found or goal in came_from
        else []
    )

    elapsed = (time.perf_counter() - started) * 1000

    return SearchResult(
        "BFS",
        path,
        visited,
        bool(path),
        elapsed,
        len(visited),
        "경로를 찾았습니다."
        if path else "목적지까지 경로가 없습니다.",
    )


def astar_search(
    grid: np.ndarray,
    start: Position,
    goal: Position,
) -> SearchResult:
    """A* 알고리즘으로 맨해튼 거리를 이용해 경로를 탐색한다."""
    started = time.perf_counter()
    rows, cols = grid.shape

    if (
        not valid_position(start, rows, cols)
        or not valid_position(goal, rows, cols)
    ):
        return SearchResult(
            "A*", [], set(), False, 0.0, 0,
            "좌표가 지도 범위를 벗어났습니다.",
        )

    if grid[start] or grid[goal]:
        return SearchResult(
            "A*", [], set(), False, 0.0, 0,
            "출발점 또는 목적지가 장애물입니다.",
        )

    if start == goal:
        elapsed = (time.perf_counter() - started) * 1000
        return SearchResult(
            "A*", [start], {start}, True, elapsed, 1,
            "출발점과 목적지가 같습니다.",
        )

    # 우선순위 큐: (f 점수, g 점수, 좌표)
    frontier = [
        (manhattan(start, goal), 0, start)
    ]

    came_from: Dict[Position, Position] = {}
    g_score: Dict[Position, int] = {start: 0}
    closed: Set[Position] = set()
    found = False

    while frontier:
        _, current_g, current = heapq.heappop(frontier)

        if current in closed:
            continue

        if current_g != g_score.get(
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

            tentative_g = current_g + 1

            if tentative_g < g_score.get(
                nxt, float("inf")
            ):
                came_from[nxt] = current
                g_score[nxt] = tentative_g

                priority = (
                    tentative_g + manhattan(nxt, goal)
                )

                heapq.heappush(
                    frontier,
                    (priority, tentative_g, nxt),
                )

    path = (
        reconstruct_path(came_from, start, goal)
        if found else []
    )

    elapsed = (time.perf_counter() - started) * 1000
    explored = closed | ({goal} if found else set())

    return SearchResult(
        "A*",
        path,
        explored,
        bool(path),
        elapsed,
        len(explored),
        "경로를 찾았습니다."
        if path else "목적지까지 경로가 없습니다.",
    )


def generate_grid(
    rows: int,
    cols: int,
    obstacle_ratio: float,
    seed: int,
) -> np.ndarray:
    """무작위 장애물 지도를 생성한다."""
    rng = np.random.default_rng(seed)

    grid = rng.random((rows, cols)) < obstacle_ratio

    # 출발점과 목적지는 항상 비워 둔다.
    grid[0, 0] = False
    grid[rows - 1, cols - 1] = False

    return grid


def draw_grid(
    grid: np.ndarray,
    start: Position,
    goal: Position,
    result: Optional[SearchResult] = None,
    robot_position: Optional[Position] = None,
    title: str = "자율주행 로봇 경로 지도",
):
    """지도와 탐색 영역, 최종 경로, 로봇 위치를 그린다."""
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch

    rows, cols = grid.shape

    # 0=빈 칸, 1=장애물, 2=탐색 영역, 3=최종 경로
    image = np.zeros((rows, cols), dtype=int)
    image[grid] = 1

    if result is not None:
        for pos in result.visited:
            if valid_position(pos, rows, cols) and not grid[pos]:
                image[pos] = 2

        for pos in result.path:
            if valid_position(pos, rows, cols) and not grid[pos]:
                image[pos] = 3

    cmap = ListedColormap([
        "#F4F6F8",
        "#374151",
        "#FDE68A",
        "#60A5FA",
    ])

    fig, ax = plt.subplots(
        figsize=(
            min(12, max(5, cols * 0.45)),
            min(9, max(4, rows * 0.45)),
        )
    )

    ax.imshow(image, cmap=cmap, vmin=0, vmax=3)

    ax.set_xticks(np.arange(-0.5, cols, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, rows, 1), minor=True)
    ax.grid(
        which="minor",
        color="#CBD5E1",
        linestyle="-",
        linewidth=0.6,
    )
    ax.tick_params(which="minor", bottom=False, left=False)

    ax.set_xticks(range(cols))
    ax.set_yticks(range(rows))
    ax.set_xlabel("열 (column)")
    ax.set_ylabel("행 (row)")
    ax.set_title(title)

    ax.scatter(
        start[1], start[0],
        s=180, marker="o",
        color="#16A34A",
        edgecolors="white",
        linewidths=1.5,
        label="출발점",
        zorder=5,
    )

    ax.scatter(
        goal[1], goal[0],
        s=200, marker="*",
        color="#DC2626",
        edgecolors="white",
        linewidths=1.0,
        label="목적지",
        zorder=5,
    )

    if robot_position is not None:
        ax.scatter(
            robot_position[1], robot_position[0],
            s=130, marker="s",
            color="#7C3AED",
            edgecolors="white",
            linewidths=1.5,
            label="로봇 현재 위치",
            zorder=6,
        )

    handles, labels = ax.get_legend_handles_labels()

    handles.extend([
        Patch(facecolor="#374151", label="장애물"),
        Patch(facecolor="#FDE68A", label="탐색 영역"),
        Patch(facecolor="#60A5FA", label="최종 경로"),
    ])

    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=3,
        frameon=False,
    )

    fig.tight_layout()
    return fig


def run_tests():
    """핵심 기능의 정확성을 확인하는 자동 테스트."""
    tests = []

    # 1. 장애물이 없는 지도에서 최단 경로
    grid = np.zeros((5, 5), dtype=bool)

    a = astar_search(grid, (0, 0), (4, 4))
    b = bfs_search(grid, (0, 0), (4, 4))

    ok = (
        a.found and b.found
        and len(a.path) - 1 == 8
        and len(b.path) - 1 == 8
    )

    tests.append((
        "장애물 없는 지도에서 최단 경로",
        ok,
        f"A*: {max(0, len(a.path)-1)}칸, "
        f"BFS: {max(0, len(b.path)-1)}칸",
    ))

    # 2. 장애물 회피
    grid = np.zeros((5, 5), dtype=bool)
    grid[1:4, 2] = True

    a = astar_search(grid, (0, 0), (4, 4))
    avoids = (
        a.found
        and all(not grid[p] for p in a.path)
    )

    tests.append((
        "장애물 회피",
        avoids,
        "최종 경로에 장애물 칸이 포함되지 않아야 함",
    ))

    # 3. 경로 없음
    grid = np.zeros((5, 5), dtype=bool)
    grid[2, :] = True

    a = astar_search(grid, (0, 0), (4, 4))

    tests.append((
        "경로가 없는 경우 처리",
        not a.found,
        a.message,
    ))

    # 4. 출발점과 목적지가 같음
    grid = np.zeros((3, 3), dtype=bool)

    a = astar_search(grid, (1, 1), (1, 1))

    tests.append((
        "출발점과 목적지가 같은 경우",
        a.found and len(a.path) == 1,
        a.message,
    ))

    # 5. BFS와 A* 경로 길이 비교
    grid = np.zeros((8, 8), dtype=bool)
    grid[1:6, 3] = True
    grid[4, 3] = False

    a = astar_search(grid, (0, 0), (7, 7))
    b = bfs_search(grid, (0, 0), (7, 7))

    same_length = (
        a.found and b.found
        and len(a.path) == len(b.path)
    )

    tests.append((
        "BFS와 A* 경로 길이 일치",
        same_length,
        f"A*: {max(0, len(a.path)-1)}칸, "
        f"BFS: {max(0, len(b.path)-1)}칸",
    ))

    # 6. 상하좌우 한 칸 이동 확인
    steps_valid = (
        bool(a.path)
        and all(
            manhattan(a.path[i], a.path[i + 1]) == 1
            for i in range(len(a.path) - 1)
        )
    )

    tests.append((
        "상하좌우 한 칸 이동만 사용",
        steps_valid,
        "대각선 이동이 없어야 함",
    ))

    # 7. 지도 경계 확인
    bounds_valid = (
        bool(a.path)
        and all(
            valid_position(p, *grid.shape)
            for p in a.path
        )
    )

    tests.append((
        "경로가 지도 경계 안에 있음",
        bounds_valid,
        "모든 좌표가 지도 안에 있어야 함",
    ))

    return tests


def main():
    st.set_page_config(
        page_title="자율주행 로봇 경로 탐색기",
        page_icon="🤖",
        layout="wide",
    )

    st.title("🤖 자율주행 로봇 경로 탐색기")
    st.caption(
        "격자 지도에서 장애물을 피하는 경로를 찾고 "
        "A*와 BFS를 비교하는 시뮬레이터"
    )

    with st.sidebar:
        st.header("지도 설정")

        rows = st.slider(
            "지도 행 수",
            min_value=5,
            max_value=25,
            value=12,
        )

        cols = st.slider(
            "지도 열 수",
            min_value=5,
            max_value=25,
            value=16,
        )

        obstacle_ratio = st.slider(
            "장애물 비율",
            min_value=0.0,
            max_value=0.45,
            value=0.22,
            step=0.01,
        )

        seed = st.number_input(
            "무작위 시드",
            min_value=0,
            max_value=999999,
            value=42,
            step=1,
        )

        algorithm = st.selectbox(
            "탐색 알고리즘",
            ["A*", "BFS", "두 알고리즘 비교"],
        )

        st.markdown("---")

        obstacle_text = st.text_input(
            "직접 배치할 장애물 좌표",
            placeholder="예: 2,3; 2,4; 5,6",
            help=(
                "행,열 형식으로 입력하세요. "
                "여러 좌표는 세미콜론(;)으로 구분합니다. "
                "행과 열은 0부터 시작합니다."
            ),
        )

        apply_obstacles = st.button(
            "좌표로 장애물 적용",
            use_container_width=True,
        )

        st.caption(
            "초록색: 출발점 · 빨간색: 목적지 · 회색: 장애물"
        )

    # 세션 상태 초기화
    if "grid" not in st.session_state:
        st.session_state.grid = generate_grid(
            rows, cols, obstacle_ratio, int(seed)
        )

    if "result_a" not in st.session_state:
        st.session_state.result_a = None

    if "result_b" not in st.session_state:
        st.session_state.result_b = None

    if "robot_step" not in st.session_state:
        st.session_state.robot_step = 0

    # 지도 크기가 변경되면 새 지도 생성
    current_grid = st.session_state.grid

    if current_grid.shape != (rows, cols):
        st.session_state.grid = generate_grid(
            rows, cols, obstacle_ratio, int(seed)
        )
        st.session_state.result_a = None
        st.session_state.result_b = None
        st.session_state.robot_step = 0

    start: Position = (0, 0)
    goal: Position = (rows - 1, cols - 1)

    # 사용자가 입력한 좌표에 장애물 추가
    if apply_obstacles:
        parsed: List[Position] = []

        try:
            for part in obstacle_text.split(";"):
                part = part.strip()

                if not part:
                    continue

                pieces = [
                    piece.strip()
                    for piece in part.split(",")
                ]

                if len(pieces) != 2:
                    raise ValueError(
                        f"좌표 형식이 올바르지 않습니다: {part}"
                    )

                pos = (
                    int(pieces[0]),
                    int(pieces[1]),
                )

                if not valid_position(pos, rows, cols):
                    raise ValueError(
                        f"지도 범위를 벗어난 좌표입니다: {pos}"
                    )

                if pos not in (start, goal):
                    parsed.append(pos)

            updated_grid = st.session_state.grid.copy()

            for pos in parsed:
                updated_grid[pos] = True

            st.session_state.grid = updated_grid
            st.session_state.result_a = None
            st.session_state.result_b = None
            st.session_state.robot_step = 0

            st.success(
                f"장애물 {len(parsed)}개 좌표를 적용했습니다."
            )

        except ValueError as exc:
            st.error(str(exc))

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button(
            "🎲 새 무작위 지도",
            use_container_width=True,
        ):
            st.session_state.grid = generate_grid(
                rows,
                cols,
                obstacle_ratio,
                random.randint(0, 1_000_000),
            )
            st.session_state.result_a = None
            st.session_state.result_b = None
            st.session_state.robot_step = 0
            st.rerun()

    with col2:
        if st.button(
            "🧹 지도 초기화",
            use_container_width=True,
        ):
            st.session_state.grid = np.zeros(
                (rows, cols), dtype=bool
            )
            st.session_state.result_a = None
            st.session_state.result_b = None
            st.session_state.robot_step = 0
            st.rerun()

    with col3:
        if st.button(
            "🔎 경로 탐색 실행",
            type="primary",
            use_container_width=True,
        ):
            grid = st.session_state.grid.copy()

            grid[start] = False
            grid[goal] = False

            if algorithm in ("A*", "두 알고리즘 비교"):
                st.session_state.result_a = astar_search(
                    grid, start, goal
                )
            else:
                st.session_state.result_a = None

            if algorithm in ("BFS", "두 알고리즘 비교"):
                st.session_state.result_b = bfs_search(
                    grid, start, goal
                )
            else:
                st.session_state.result_b = None

            st.session_state.robot_step = 0

    result_a = st.session_state.result_a
    result_b = st.session_state.result_b

    primary_result = (
        result_a if result_a is not None else result_b
    )

    left, right = st.columns([1.55, 1])

    with left:
        fig = draw_grid(
            st.session_state.grid,
            start,
            goal,
            primary_result,
            title="로봇 경로 및 탐색 영역",
        )

        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    with right:
        st.subheader("탐색 결과")

        if primary_result is None:
            st.info(
                "알고리즘을 선택한 뒤 "
                "'경로 탐색 실행'을 눌러 주세요."
            )
        else:
            if primary_result.found:
                st.success(primary_result.message)
                st.metric(
                    "이동 거리",
                    f"{len(primary_result.path) - 1} 칸",
                )
            else:
                st.warning(primary_result.message)
                st.metric("이동 거리", "경로 없음")

            st.metric(
                "탐색 노드 수",
                primary_result.explored_count,
            )

            st.metric(
                "실행 시간",
                f"{primary_result.elapsed_ms:.3f} ms",
            )

        # BFS와 A* 결과 비교표
        if result_a is not None and result_b is not None:
            st.markdown("#### 알고리즘 비교")

            def path_length(result: SearchResult):
                return (
                    len(result.path) - 1
                    if result.found else None
                )

            comparison = {
                "항목": [
                    "경로 발견",
                    "이동 거리(칸)",
                    "탐색 노드 수",
                    "실행 시간(ms)",
                ],
                "A*": [
                    "성공" if result_a.found else "실패",
                    path_length(result_a)
                    if result_a.found else "—",
                    result_a.explored_count,
                    round(result_a.elapsed_ms, 3),
                ],
                "BFS": [
                    "성공" if result_b.found else "실패",
                    path_length(result_b)
                    if result_b.found else "—",
                    result_b.explored_count,
                    round(result_b.elapsed_ms, 3),
                ],
            }

            st.dataframe(
                comparison,
                hide_index=True,
                use_container_width=True,
            )

            st.caption(
                "실행 시간은 컴퓨터와 실행 환경에 따라 달라집니다."
            )

    # 로봇 이동 시뮬레이션
    st.markdown("---")
    st.subheader("🚗 로봇 이동 시뮬레이션")

    anim_result = primary_result

    if anim_result is None or not anim_result.found:
        st.info(
            "먼저 경로 탐색을 성공적으로 실행해야 "
            "이동 시뮬레이션을 볼 수 있습니다."
        )
    else:
        max_step = len(anim_result.path) - 1

        robot_step = st.slider(
            "이동 단계",
            min_value=0,
            max_value=max_step,
            value=min(
                st.session_state.robot_step,
                max_step,
            ),
            key="animation_step_slider",
            help=(
                "슬라이더를 움직여 로봇의 위치를 "
                "한 단계씩 확인할 수 있습니다."
            ),
        )

        st.session_state.robot_step = robot_step
        robot_position = anim_result.path[robot_step]

        anim_fig = draw_grid(
            st.session_state.grid,
            start,
            goal,
            anim_result,
            robot_position,
            title=f"로봇 이동 단계: {robot_step}/{max_step}",
        )

        st.pyplot(anim_fig, use_container_width=True)
        plt.close(anim_fig)

        st.write(
            f"현재 로봇 위치: 행 {robot_position[0]}, "
            f"열 {robot_position[1]}"
        )

        if robot_step == max_step:
            st.success("로봇이 목적지에 도착했습니다.")

    # 자동 테스트
    st.markdown("---")
    st.subheader("🧪 자동 테스트")

    st.write(
        "테스트를 실행해 경로 탐색의 기본 정확성을 확인합니다."
    )

    if st.button("테스트 실행"):
        test_results = run_tests()

        passed = sum(
            1 for _, ok, _ in test_results if ok
        )

        st.write(
            f"**결과: {passed}/{len(test_results)}개 통과**"
        )

        for name, ok, detail in test_results:
            if ok:
                st.success(f"PASS — {name}: {detail}")
            else:
                st.error(f"FAIL — {name}: {detail}")

    with st.expander("알고리즘 설명"):
        st.markdown(
            """
            **BFS(너비 우선 탐색)**는 가까운 단계의 칸부터
            차례대로 탐색합니다. 모든 이동 비용이 1이면
            최단 경로를 보장합니다.

            **A\***는 현재까지의 이동 비용 `g(n)`과
            목적지까지의 예상 비용 `h(n)`을 합친
            `f(n) = g(n) + h(n)`을 사용합니다.

            이 앱은 상하좌우 이동에 맞는 맨해튼 거리를
            휴리스틱으로 사용합니다.

            **주의:** A*가 모든 지도에서 BFS보다 빠른 것은
            아닙니다. 지도와 장애물 배치에 따라 탐색 노드 수와
            실행 시간이 달라집니다.

            이 프로그램은 격자 기반 교육용 시뮬레이터이며,
            실제 로봇의 센서, 운동학, 충돌 회피를
            완전히 모델링하지는 않습니다.
            """
        )


if __name__ == "__main__":
    main()
