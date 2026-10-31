import os
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="3D 자율주행 시뮬레이터", page_icon="🚗", layout="wide")

def get_api_key():
    try:
        value = st.secrets.get("VWORLD_API_KEY", "")
        if value:
            return value
    except Exception:
        pass
    return os.getenv("VWORLD_API_KEY", "")

api_key = get_api_key()

st.title("🚗 브이월드 3D 자율주행 시뮬레이터")
st.caption("실제 3D 지도 위에서 출발점과 목적지를 지정하고 가상 자동차의 이동을 관찰하는 초기 버전입니다.")

with st.sidebar:
    st.subheader("주행 설정")
    speed = st.slider("이동 속도 (m/s)", min_value=1, max_value=30, value=8)
    st.caption(f"현재 설정: 약 {speed * 3.6:.1f} km/h")
    st.markdown("---")
    st.markdown("**사용 방법**")
    st.write("1. 지도에서 출발점 버튼을 선택하고 지도를 클릭합니다.")
    st.write("2. 목적지 버튼을 선택하고 지도를 클릭합니다.")
    st.write("3. 주행 시작을 누르면 자동차가 이동합니다.")
    st.write("4. 카메라를 자동차 따라가기 또는 자유 관찰로 바꿀 수 있습니다.")

if not api_key:
    st.error("브이월드 API 키를 찾을 수 없습니다.")
    st.markdown("""
    프로젝트 폴더에 `.streamlit/secrets.toml` 파일을 만들고 다음과 같이 입력하세요.

    ```toml
    VWORLD_API_KEY = "새로 발급한 API 키"
    ```

    또는 환경변수 `VWORLD_API_KEY`를 설정하세요.
    """)
    st.stop()

# API 키는 브라우저에서 지도 API를 호출하기 위해 HTML에 전달됩니다.
# 따라서 브이월드에서 서비스 URL/도메인 제한을 설정하고, 키를 공개 저장소에 올리지 마세요.
html = r"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://map.vworld.kr/js/webglMapInit.js.do?version=3.0&apiKey=__VWORLD_KEY__"></script>
<style>
html, body { margin:0; padding:0; width:100%; height:100%; overflow:hidden; font-family:Arial,sans-serif; }
#map { width:100%; height:100%; min-height:650px; background:#e5e7eb; }
#panel { position:absolute; z-index:10; top:12px; left:12px; width:260px; background:rgba(255,255,255,.96);
  padding:12px; border-radius:12px; box-shadow:0 3px 14px #0002; }
button, select { padding:8px 10px; margin:3px 2px; border:1px solid #cbd5e1; border-radius:7px; background:white; cursor:pointer; }
button.active { background:#dbeafe; border-color:#2563eb; font-weight:bold; }
button.primary { background:#2563eb; color:white; border-color:#2563eb; }
.small { font-size:12px; color:#475569; line-height:1.45; }
#status { margin-top:8px; font-size:13px; color:#0f172a; }
</style>
</head>
<body>
<div id="map"></div>
<div id="panel">
  <b>🚗 3D 주행 설정</b><br>
  <button id="pickStart" class="active">🟢 출발점 선택</button>
  <button id="pickGoal">🔴 목적지 선택</button>
  <hr>
  <label>카메라 </label>
  <select id="camera">
    <option value="free">자유 관찰</option>
    <option value="follow" selected>자동차 따라가기</option>
  </select><br>
  <button id="start" class="primary">▶ 주행 시작</button>
  <button id="pause">⏸ 일시정지</button>
  <button id="reset">↺ 초기화</button>
  <div id="status">지도를 클릭해 출발점을 지정하세요.</div>
  <p class="small">
    ※ 현재 버전은 출발점과 목적지를 직선으로 연결하는 주행 시각화입니다.
    실제 도로를 따라가는 길찾기는 별도의 도로 경로 API 연결이 필요합니다.
  </p>
</div>
<script>
(function() {
  const SPEED_MPS = __SPEED__;
  let map, viewer, pickMode = "start";
  let startCart = null, goalCart = null, carEntity = null, startEntity = null, goalEntity = null, routeEntity = null;
  let running = false, distance = 0, totalDistance = 0, lastTime = null;
  let startWorld = null, goalWorld = null;

  const statusEl = document.getElementById("status");
  function status(t) { statusEl.textContent = t; }

  function setPickMode(mode) {
    pickMode = mode;
    document.getElementById("pickStart").classList.toggle("active", mode === "start");
    document.getElementById("pickGoal").classList.toggle("active", mode === "goal");
    status(mode === "start" ? "지도를 클릭해 출발점을 지정하세요." : "지도를 클릭해 목적지를 지정하세요.");
  }
  document.getElementById("pickStart").onclick = () => setPickMode("start");
  document.getElementById("pickGoal").onclick = () => setPickMode("goal");

  function clearEntity(entity) { if (entity && viewer) viewer.entities.remove(entity); }
  function makePoint(position, color, label) {
    return viewer.entities.add({
      position,
      point: { pixelSize: 14, color, outlineColor: Cesium.Color.WHITE, outlineWidth: 3, heightReference: Cesium.HeightReference.CLAMP_TO_GROUND },
      label: { text: label, font: "bold 14px sans-serif", pixelOffset: new Cesium.Cartesian2(0, -22),
        fillColor: Cesium.Color.WHITE, outlineColor: Cesium.Color.BLACK, outlineWidth: 3,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE, heightReference: Cesium.HeightReference.CLAMP_TO_GROUND }
    });
  }

  function updateRoute() {
    if (!startCart || !goalCart) return;
    clearEntity(routeEntity);
    startWorld = Cesium.Cartesian3.fromDegrees(startCart.lon, startCart.lat, 2);
    goalWorld = Cesium.Cartesian3.fromDegrees(goalCart.lon, goalCart.lat, 2);
    totalDistance = Cesium.Cartesian3.distance(startWorld, goalWorld);
    routeEntity = viewer.entities.add({
      polyline: { positions: [startWorld, goalWorld], width: 6, material: Cesium.Color.YELLOW,
        clampToGround: true }
    });
    clearEntity(carEntity);
    carEntity = viewer.entities.add({
      position: startWorld,
      point: { pixelSize: 18, color: Cesium.Color.ORANGE, outlineColor: Cesium.Color.WHITE, outlineWidth: 3 },
      label: { text: "🚗 자동차", font: "bold 14px sans-serif", pixelOffset: new Cesium.Cartesian2(0, -25),
        fillColor: Cesium.Color.WHITE, outlineColor: Cesium.Color.BLACK, outlineWidth: 3,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE }
    });
    distance = 0;
    running = false;
    status("경로 설정 완료 · 직선 거리 약 " + (totalDistance / 1000).toFixed(2) + " km");
  }

  function initMap() {
    const options = {
      mapId: "map",
      initPosition: new vw.CameraPosition(
        new vw.CoordZ(127.0276, 37.4979, 4500),
        new vw.Direction(0, -45, 0)
      ),
      logo: true,
      navigation: true
    };
    map = new vw.Map();
    map.setOption(options);
    map.setMapId("map");
    map.setInitPosition(new vw.CameraPosition(
      new vw.CoordZ(127.0276, 37.4979, 4500),
      new vw.Direction(0, -45, 0)
    ));
    map.start();
  }

  // VWorld WebGL API가 생성된 후 Cesium viewer를 연결합니다.
  vw.ws3dInitCallBack = function() {
    viewer = window.viewer || (typeof window.vw3d !== "undefined" ? window.vw3d : null);
    if (!viewer && window.Cesium && window.viewer) viewer = window.viewer;
    if (!viewer) {
      status("3D 지도는 로드되었지만 지도 객체를 찾지 못했습니다. 브이월드 API 버전/초기화 상태를 확인하세요.");
      return;
    }
    const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
    handler.setInputAction(function(click) {
      const cartesian = viewer.camera.pickEllipsoid(click.position, viewer.scene.globe.ellipsoid);
      if (!cartesian) return;
      const c = Cesium.Cartographic.fromCartesian(cartesian);
      const point = { lon: Cesium.Math.toDegrees(c.longitude), lat: Cesium.Math.toDegrees(c.latitude) };
      if (pickMode === "start") {
        startCart = point; clearEntity(startEntity);
        startEntity = makePoint(cartesian, Cesium.Color.LIME, "출발");
      } else {
        goalCart = point; clearEntity(goalEntity);
        goalEntity = makePoint(cartesian, Cesium.Color.RED, "목적지");
      }
      if (startCart && goalCart) updateRoute();
      else status("반대쪽 지점도 지도에서 선택하세요.");
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
    status("3D 지도 준비 완료 · 출발점과 목적지를 선택하세요.");
  };

  document.getElementById("start").onclick = function() {
    if (!startCart || !goalCart || !carEntity) { status("출발점과 목적지를 먼저 선택하세요."); return; }
    if (distance >= totalDistance) distance = 0;
    running = true; lastTime = null; status("자동차 주행 중 · 설정 속도 " + SPEED_MPS + " m/s");
  };
  document.getElementById("pause").onclick = function() { running = false; status("일시정지됨"); };
  document.getElementById("reset").onclick = function() {
    running = false; distance = 0;
    if (carEntity && startWorld) carEntity.position = startWorld;
    status("초기화 완료");
  };

  function animate(now) {
    if (running && carEntity && totalDistance > 0) {
      if (lastTime !== null) distance = Math.min(totalDistance, distance + SPEED_MPS * ((now - lastTime) / 1000));
      lastTime = now;
      const t = Math.min(1, distance / totalDistance);
      const pos = Cesium.Cartesian3.lerp(startWorld, goalWorld, t, new Cesium.Cartesian3());
      carEntity.position = pos;
      if (document.getElementById("camera").value === "follow") {
        viewer.camera.lookAt(pos, new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-25), 180));
      } else {
        viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
      }
      if (t >= 1) { running = false; status("목적지 도착 · 이동 거리 " + totalDistance.toFixed(0) + " m"); }
    }
    requestAnimationFrame(animate);
  }
  initMap();
  requestAnimationFrame(animate);
})();
</script>
</body>
</html>
"""
html = html.replace("__VWORLD_KEY__", api_key).replace("__SPEED__", str(speed))
components.html(html, height=720, scrolling=False)
st.info("현재는 3D 지도 표시와 직선 주행 시각화까지 구현한 시작 버전입니다. 실제 도로를 따라가는 경로 탐색은 브이월드 경로안내 API 또는 도로 네트워크 데이터와 추가 연결해야 합니다.")
