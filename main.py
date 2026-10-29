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
            comparison = {
                "항목": ["경로 발견", "이동 거리(칸)", "탐색 노드 수", "실행 시간(ms)"],
                "A*": [
                    "성공" if result_a.found else "실패",
                    len(result_a.path) - 1 if result_a.found else "—",
                    len(result_a.visited), round(result_a.elapsed_ms, 3),
                ],
                "BFS": [
                    "성공" if result_b.found else "실패",
                    len(result_b.path) - 1 if result_b.found else "—",
                    len(result_b.visited), round(result_b.elapsed_ms, 3),
                ],
            }
            st.dataframe(comparison, hide_index=True, use_container_width=True)

        if primary.found:
            st.subheader("🚗 로봇 이동 시뮬레이션")
            step = st.slider("이동 단계", 0, len(primary.path) - 1, key="robot_step_slider")
            robot = primary.path[step]
            st.plotly_chart(make_figure(st.session_state.grid, start, goal, primary, robot), use_container_width=True)
            st.write(f"현재 위치: 행 {robot[0]}, 열 {robot[1]}")
            if step == len(primary.path) - 1:
                st.success("로봇이 목적지에 도착했습니다.")

    with st.expander("알고리즘 설명"):
        st.markdown(
            "**BFS**는 가까운 칸부터 탐색하며, 모든 이동 비용이 같을 때 최단 경로를 찾습니다.\n\n"
            "**A\\***는 실제 이동 비용 `g(n)`과 목적지까지의 예상 비용 `h(n)`을 더한 `f(n)=g(n)+h(n)`을 기준으로 탐색합니다. "
            "이 앱은 상하좌우 이동에 맞는 맨해튼 거리를 사용합니다.\n\n"
            "이 앱은 경로 탐색 학습용 시뮬레이터이며 실제 로봇의 센서나 물리적 움직임을 제어하지 않습니다."
        )
