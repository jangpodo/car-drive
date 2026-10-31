
    return fig


def main():
    st.set_page_config(page_title="자율주행 로봇 경로 탐색기", page_icon="🤖", layout="wide")
    st.title("🤖 자율주행 로봇 경로 탐색기")
    st.caption("지도 크기를 직접 정하고, 지도 칸을 클릭해 장애물을 배치한 뒤 경로를 탐색하세요.")

    with st.sidebar:
        st.header("지도 설정")
        rows = st.number_input("행 수 (세로)", min_value=5, max_value=80, value=20, step=1)
        cols = st.number_input("열 수 (가로)", min_value=5, max_value=80, value=20, step=1)
        algorithm = st.selectbox("탐색 알고리즘", ["A*", "BFS", "두 알고리즘 비교"])
        st.caption("예: 행 50, 열 50 → 50×50 칸")
        st.markdown("---")
        st.write("**장애물 배치 방법**")
        st.write("아래 지도에서 빈 칸을 클릭하면 장애물이 추가되고, 장애물 칸을 클릭하면 제거됩니다.")
        st.caption("초록색 S: 출발점 · 빨간색 G: 목적지")

    rows, cols = int(rows), int(cols)
    shape = (rows, cols)
    if "grid" not in st.session_state or st.session_state.get("grid_shape") != shape:
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

    st.subheader(f"지도 편집 ({rows} × {cols})")
    st.info("지도 칸을 클릭해 장애물을 배치하거나 제거하세요. 출발점과 목적지는 장애물로 바뀌지 않습니다.")

    edit_fig = make_figure(st.session_state.grid, start, goal)
    clicked = plotly_events(
        edit_fig,
        click_event=True,
        select_event=False,
        hover_event=False,
        override_height=edit_fig.layout.height,
        key=f"map_click_{rows}_{cols}",
    )
    if clicked:
        point = clicked[-1]
        if "x" in point and "y" in point:
            c, r = int(round(point["x"])), int(round(point["y"]))
            pos = (r, c)
            if valid_position(pos, rows, cols) and pos not in (start, goal):
                st.session_state.grid[pos] = not st.session_state.grid[pos]
                st.session_state.result_a = None
                st.session_state.result_b = None
                st.session_state.robot_step = 0
                st.rerun()

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("🧹 장애물 전체 지우기", use_container_width=True):
            st.session_state.grid = np.zeros(shape, dtype=bool)
            st.session_state.result_a = None
            st.session_state.result_b = None
            st.rerun()
    with b2:
        if st.button("🎲 무작위 장애물", use_container_width=True):
            rng = np.random.default_rng()
            grid = rng.random(shape) < 0.20
            grid[start] = False
            grid[goal] = False
            st.session_state.grid = grid
            st.session_state.result_a = None
            st.session_state.result_b = None
            st.rerun()
    with b3:
        run = st.button("🔎 경로 탐색 및 자동차 이동", type="primary", use_container_width=True)

    if run:
        grid = st.session_state.grid.copy()
        grid[start] = False
        grid[goal] = False
        st.session_state.result_a = search(grid, start, goal, "A*") if algorithm in ("A*", "두 알고리즘 비교") else None
        st.session_state.result_b = search(grid, start, goal, "BFS") if algorithm in ("BFS", "두 알고리즘 비교") else None
        st.session_state.robot_step = 0

        # 경로가 있으면 지도 크기와 관계없이 약 5초 동안 자동차를 움직여 보여준다.
        animation_result = (
            st.session_state.result_a
            if st.session_state.result_a is not None
            else st.session_state.result_b
        )
        if animation_result is not None and animation_result.found:
            st.markdown("---")
            st.subheader("🚗 자동차 주행 애니메이션")
            st.caption("지도 크기와 경로 길이에 관계없이 약 5초 동안 주행합니다.")
            animation_area = st.empty()
            path = animation_result.path
            frame_count = min(50, max(2, len(path)))
            frame_indices = sorted(set(
                round(i * (len(path) - 1) / (frame_count - 1))
                for i in range(frame_count)
            ))
            animation_started = time.perf_counter()
            total_duration = 5.0

            for frame_number, path_index in enumerate(frame_indices):
                robot_pos = path[path_index]
                frame_fig = make_figure(
                    grid, start, goal, animation_result, robot_pos
                )
                # 자동차 이모지를 현재 위치에 표시한다.
                frame_fig.add_trace(go.Scatter(
                    x=[robot_pos[1]], y=[robot_pos[0]],
                    mode="text",
                    text=["🚗"],
                    textfont=dict(size=max(12, min(25, 700 // max(rows, cols)))),
                    name="자동차",
                    hovertemplate="자동차 현재 위치<extra></extra>",
                    showlegend=False,
                ))
                elapsed = time.perf_counter() - animation_started
                progress = min(100, int((elapsed / total_duration) * 100))
                animation_area.plotly_chart(
                    frame_fig,
                    use_container_width=True,
                    key=f"drive_frame_{rows}_{cols}_{frame_number}_{time.time_ns()}",
                )
                plt_dummy = None
                target_time = total_duration * (frame_number + 1) / len(frame_indices)
                remaining = animation_started + target_time - time.perf_counter()
                if remaining > 0:
                    time.sleep(remaining)

            st.success("자동차가 목적지에 도착했습니다!")

    result_a = st.session_state.result_a
    result_b = st.session_state.result_b
    primary = result_a if result_a is not None else result_b

    if primary is not None:
        st.markdown("---")
        st.subheader("탐색 결과")
        result_fig = make_figure(st.session_state.grid, start, goal, primary)
        st.plotly_chart(result_fig, use_container_width=True)
        if primary.found:
            st.success(primary.message)
            st.metric("이동 거리", f"{len(primary.path) - 1} 칸")
        else:
            st.warning(primary.message)
            st.metric("이동 거리", "경로 없음")
        m1, m2 = st.columns(2)
        m1.metric("탐색 노드 수", len(primary.visited))
        m2.metric("실행 시간", f"{primary.elapsed_ms:.3f} ms")

        if result_a is not None and result_b is not None:
            st.subheader("A*와 BFS 비교")
