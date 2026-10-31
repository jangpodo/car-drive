                if valid_position(pos, rows, cols):
                    if action == "start":
                        st.session_state.start = pos
                        st.session_state.grid[pos] = False
                    elif action == "goal":
                        st.session_state.goal = pos
                        st.session_state.grid[pos] = False
                    elif action == "obstacle":
                        if pos not in (st.session_state.start, st.session_state.goal):
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
        except (ValueError, TypeError, KeyError):
            pass

    st.markdown(
        "**사용 방법:** 도구 선택 → 지도 칸에 마우스 올리기 → **F** 키. "
        "장애물은 마우스 버튼을 누른 채 드래그해 여러 칸을 한 번에 지정할 수 있습니다."
    )
    st.caption("초록색 S = 출발점 · 빨간색 G = 종착점 · 짙은 회색 = 장애물")

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
        if st.button("🧩 미로형 장애물 무작위 생성", use_container_width=True):
            st.session_state.grid = generate_maze(
                rows, cols, st.session_state.start, st.session_state.goal
            )
            st.session_state.result_a = None
            st.session_state.result_b = None
            st.rerun()
    with c3:
        run = st.button(
            "🔎 경로 탐색 및 자동차 이동",
            type="primary",
            use_container_width=True,
        )

    if run:
        if st.session_state.start is None or st.session_state.goal is None:
            st.warning("먼저 출발점과 종착점을 각각 하나씩 설치해 주세요.")
        else:
            grid = st.session_state.grid.copy()
            start = st.session_state.start
            goal = st.session_state.goal
            st.session_state.result_a = (
                search(grid, start, goal, "A*")
                if algorithm in ("A*", "두 알고리즘 비교") else None
            )
            st.session_state.result_b = (
                search(grid, start, goal, "BFS")
                if algorithm in ("BFS", "두 알고리즘 비교") else None
            )

            result = st.session_state.result_a or st.session_state.result_b
            if result and result.found:
                st.subheader("🚗 자동차 주행 시뮬레이션")
                area = st.empty()
                started = time.perf_counter()
                frames = min(40, max(2, len(result.path)))
                indices = sorted({
                    round(i * (len(result.path) - 1) / (frames - 1))
                    for i in range(frames)
                })
                for i, idx in enumerate(indices):
                    area.plotly_chart(
                        draw_result(grid, start, goal, result, result.path[idx]),
                        use_container_width=True,
                        key=f"animation_{i}_{time.time_ns()}",
                    )
                    wait = 5 * (i + 1) / len(indices) - (time.perf_counter() - started)
                    if wait > 0:
                        time.sleep(wait)
                st.success("목적지에 도착했습니다!")
            elif result:
                st.warning(result.message)

    for result in (st.session_state.result_a, st.session_state.result_b):
        if result is not None:
            st.subheader(f"{result.algorithm} 탐색 결과")
            st.write(result.message)
            st.metric(
                "이동 거리",
                f"{len(result.path) - 1}칸" if result.found else "경로 없음",
            )
            m1, m2 = st.columns(2)
            m1.metric("탐색 노드 수", len(result.visited))
            m2.metric("실행 시간", f"{result.elapsed_ms:.3f} ms")
            if st.session_state.start and st.session_state.goal:
                st.plotly_chart(
                    draw_result(
                        st.session_state.grid,
                        st.session_state.start,
                        st.session_state.goal,
                        result,
                    ),
                    use_container_width=True,
                )


if __name__ == "__main__":
    main()
