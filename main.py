    p1, _, _ = bfs(s, g, 5, 5, set())
    p2, _, _ = astar(s, g, 5, 5, set())
    ok = bool(p1) and len(p1) == 9 and len(p1) == len(p2)
    results.append(("장애물 없는 지도에서 최단 경로", ok, f"BFS {max(0, len(p1)-1)}칸 / A* {max(0, len(p2)-1)}칸"))

    # 2. 장애물을 피해 이동
    walls = {(1, 0), (1, 1), (1, 2), (1, 3)}
    p, _, _ = astar((0, 0), (2, 0), 3, 5, walls)
    ok = bool(p) and all(pos not in walls for pos in p)
    results.append(("장애물 회피", ok, "경로에 장애물 칸이 없는지 확인"))

    # 3. 완전히 분리된 목적지
    walls = {(0, 1), (1, 0), (1, 2), (2, 1)}
    p, _, _ = astar((0, 0), (2, 2), 3, 3, walls)
    ok = not p
    results.append(("경로가 없는 지도 처리", ok, "경로 없음으로 반환"))

    # 4. 출발점과 목적지가 동일
    p, _, _ = astar((1, 1), (1, 1), 3, 3, set())
    ok = p == [(1, 1)]
    results.append(("출발점과 목적지가 동일", ok, "길이 0칸인 경로"))

    # 5. BFS와 A* 경로 길이 일치
    walls = {(1, 1), (1, 2), (2, 1)}
    pb, _, _ = bfs((0, 0), (3, 3), 4, 4, walls)
    pa, _, _ = astar((0, 0), (3, 3), 4, 4, walls)
    ok = bool(pb) and len(pb) == len(pa)
    results.append(("BFS와 A* 최단 경로 길이 비교", ok, f"BFS {max(0, len(pb)-1)}칸 / A* {max(0, len(pa)-1)}칸"))

    # 6. 이동이 상하좌우 한 칸인지 검사
    ok = bool(pa) and all(manhattan(pa[i], pa[i+1]) == 1 for i in range(len(pa)-1))
    results.append(("상하좌우 한 칸 이동 규칙", ok, "각 연속 좌표의 맨해튼 거리가 1인지 확인"))
    return results


def initialize_state():
    defaults = {
        "rows": 15,
        "cols": 20,
        "start": (0, 0),
        "goal": (14, 19),
        "walls": set(),
        "result": None,
        "last_seed": 42,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialize_state()

st.title("🤖 자율주행 로봇 경로 탐색 시뮬레이터")
st.write("장애물이 있는 격자 지도에서 로봇의 경로를 찾고, BFS와 A* 알고리즘의 성능을 비교합니다.")
st.caption("이 프로그램은 교육용 격자 시뮬레이션입니다. 실제 로봇의 센서·운동학·안전 제어를 대신하지 않습니다.")

with st.sidebar:
    st.header("지도 설정")
    rows = st.slider("지도 행 수", min_value=5, max_value=25, value=int(st.session_state.rows))
    cols = st.slider("지도 열 수", min_value=5, max_value=30, value=int(st.session_state.cols))
    ratio = st.slider("장애물 비율", min_value=0, max_value=45, value=20, step=5) / 100
    algorithm = st.selectbox("탐색 알고리즘", ["A*", "BFS", "A*와 BFS 비교"])
    st.markdown("---")
    st.subheader("지도 생성")
    seed = st.number_input("무작위 시드", min_value=0, max_value=999999, value=int(st.session_state.last_seed), step=1)
    make_map = st.button("🎲 무작위 지도 생성", use_container_width=True)
    clear_map = st.button("🧹 지도 초기화", use_container_width=True)

# 지도 크기가 바뀌면 출발점과 목적지를 새 지도 범위에 맞춥니다.
size_changed = rows != st.session_state.rows or cols != st.session_state.cols
if size_changed:
    st.session_state.rows, st.session_state.cols = rows, cols
    st.session_state.start = (0, 0)
    st.session_state.goal = (rows - 1, cols - 1)
    st.session_state.walls = {
        p for p in st.session_state.walls
        if 0 <= p[0] < rows and 0 <= p[1] < cols and p not in (st.session_state.start, st.session_state.goal)
    }
    st.session_state.result = None

if make_map:
    st.session_state.start = (0, 0)
    st.session_state.goal = (rows - 1, cols - 1)
    st.session_state.last_seed = int(seed)
    st.session_state.walls = generate_walls(rows, cols, ratio, st.session_state.start, st.session_state.goal, seed=int(seed))
    st.session_state.result = None

if clear_map:
    st.session_state.start = (0, 0)
    st.session_state.goal = (rows - 1, cols - 1)
    st.session_state.walls = set()
    st.session_state.result = None

start = st.session_state.start
goal = st.session_state.goal
walls: Set[Point] = set(st.session_state.walls)

left, right = st.columns([1.45, 1])
with left:
    st.subheader("지도")
    st.markdown("**칸을 선택해 장애물을 추가하거나 제거하세요.** 출발점과 목적지는 편집할 수 없습니다.")
    st.caption("🟩 출발점　🟥 목적지　⬛ 장애물　🟦 탐색 영역　🔵 최종 경로　🟠 로봇")
    # 각 셀은 버튼으로 제공됩니다. 누르면 해당 칸의 장애물이 토글됩니다.
    for r in range(rows):
        cell_cols = st.columns(cols, gap="small")
        for c in range(cols):
            p = (r, c)
            if p == start:
                label = "🟩"
                help_text = "출발점"
            elif p == goal:
                label = "🟥"
                help_text = "목적지"
            elif p in walls:
                label = "⬛"
                help_text = "장애물 (클릭하여 제거)"
            else:
                label = "⬜"
                help_text = "빈 칸 (클릭하여 장애물 추가)"
            if cell_cols[c].button(label, key=f"cell_{r}_{c}", help=f"{help_text}: ({r}, {c})"):
                if p not in (start, goal):
                    updated = set(st.session_state.walls)
                    if p in updated:
                        updated.remove(p)
                    else:
                        updated.add(p)
                    st.session_state.walls = updated
                    st.session_state.result = None
                    st.rerun()

with right:
    st.subheader("탐색 및 결과")
    run_col1, run_col2 = st.columns(2)
    with run_col1:
        run_search = st.button("🔎 경로 탐색", type="primary", use_container_width=True)
    with run_col2:
        run_animation = st.button("▶️ 로봇 이동 재생", use_container_width=True)

    if run_search:
        results = {}
        if algorithm in ("A*", "A*와 BFS 비교"):
            results["A*"] = astar(start, goal, rows, cols, walls)
        if algorithm in ("BFS", "A*와 BFS 비교"):
            results["BFS"] = bfs(start, goal, rows, cols, walls)
        st.session_state.result = results

    results = st.session_state.result
    if results:
        selected_name = "A*" if "A*" in results else "BFS"
        selected_path, selected_visited, selected_ms = results[selected_name]
        if selected_path:
            st.success(f"{selected_name}: 경로를 찾았습니다.")
        else:
            st.error("목적지까지 경로가 없습니다.")

        metrics = st.columns(3)
        metrics[0].metric("이동 거리", f"{max(0, len(selected_path) - 1)}칸" if selected_path else "경로 없음")
        metrics[1].metric("탐색 노드 수", len(selected_visited))
        metrics[2].metric("실행 시간", f"{selected_ms:.3f} ms")
