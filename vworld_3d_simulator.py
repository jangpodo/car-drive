import streamlit as st
import streamlit.components.v1 as components
from urllib.parse import quote

st.set_page_config(page_title="서울 3D 운전 교실", page_icon="🚗", layout="wide")
st.title("🚗 서울 3D 운전 교실")
st.caption("브이월드 3D 지도 위에서 실제 지리 좌표를 사용해 자유 주행하는 시뮬레이터")

st.markdown(
    "**W/S 또는 ↑/↓:** 전진·후진　 "
    "**A/D 또는 ←/→:** 좌회전·우회전　 "
    "**C:** 카메라 따라가기 전환　 "
    "**스페이스:** 정지"
)

try:
    api_key = st.secrets["VWORLD_API_KEY"]
except Exception:
    st.error(
        "브이월드 인증키를 찾을 수 없습니다. "
        "Streamlit Cloud의 Settings → Secrets에 "
        '`VWORLD_API_KEY = "발급받은_인증키"`를 등록해 주세요.'
    )
    st.stop()

if not str(api_key).strip():
    st.error("VWORLD_API_KEY 값이 비어 있습니다.")
    st.stop()

encoded_key = quote(str(api_key).strip(), safe="")

html = r"""
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
html, body { margin:0; padding:0; overflow:hidden; background:#dce8ef;
  font-family:Arial,sans-serif; }
#app { position:relative; width:100%; height:720px; overflow:hidden; }
#vmap { width:100%; height:720px; background:#dce8ef; }
#hud { position:absolute; z-index:10; top:12px; left:12px;
  padding:11px 15px; min-width:155px; line-height:1.75;
  color:#fff; background:rgba(20,35,52,.90); border-radius:10px;
  box-shadow:0 3px 12px rgba(0,0,0,.2); pointer-events:none; font-size:14px; }
#hud b { color:#ffe08a; }
#help { position:absolute; z-index:10; bottom:12px; left:12px;
  padding:8px 11px; color:#fff; background:rgba(20,35,52,.86);
  border-radius:8px; font-size:12px; pointer-events:none; }
#follow { position:absolute; z-index:11; right:12px; top:12px;
  border:0; border-radius:8px; padding:9px 12px; color:#fff;
  background:#245b87; font-weight:bold; cursor:pointer; }
#status { position:absolute; z-index:10; top:58px; left:12px;
  max-width:calc(100% - 30px); padding:7px 10px; color:#182b3c;
  background:rgba(255,255,255,.91); border-radius:7px; font-size:12px; }
#error { display:none; position:absolute; z-index:20; top:110px; left:12px;
  right:12px; padding:13px; color:white; background:#8b2424;
  border-radius:8px; white-space:pre-wrap; font-size:13px; }
</style>
<script src="https://map.vworld.kr/js/webglMapInit.js.do?version=3.0&apiKey=__VWORLD_KEY__"></script>
</head>
<body>
<div id="app">
  <div id="vmap"></div>
  <div id="hud">
    속도 <b><span id="speed">0</span></b> km/h<br>
    방향 <b><span id="direction">북쪽</span></b><br>
    앞바퀴 조향 <b><span id="steering">0</span></b>°
  </div>
  <div id="status">서울시청에서 시작 · 실제 지도 좌표 기반 · 도로 주행 경로 제한은 아직 적용되지 않은 자유 주행 모드</div>
  <button id="follow" type="button">카메라 따라가기: 켜짐 (C)</button>
  <div id="help">WASD 운전 · 마우스로 지도 이동/회전 · 휠로 확대/축소 · C 카메라 전환</div>
  <div id="error"></div>
</div>

<script>
(function () {
  const errorBox = document.getElementById("error");
  function showError(message) {
    errorBox.style.display = "block";
    errorBox.textContent = message;
  }

  if (!window.vw) {
    showError("브이월드 3D 지도 라이브러리를 불러오지 못했습니다.\\n인증키, 등록된 서비스 URL, 네트워크 연결을 확인해 주세요.");
    return;
  }

  const startLon = 126.9780; // 서울시청 경도
  const startLat = 37.5665;  // 서울시청 위도
  const startHeight = 1.0;

  const options = {
    mapId: "vmap",
    initPosition: new vw.CameraPosition(
      new vw.CoordZ(startLon, startLat, 1600),
      new vw.Direction(0, -48, 0)
    ),
    logo: true,
    navigation: true
  };

  const map = new vw.Map();
  map.setOption(options);
  map.setMapId("vmap");
  map.setInitPosition(new vw.CameraPosition(
    new vw.CoordZ(startLon, startLat, 1600),
    new vw.Direction(0, -48, 0)
  ));

  let viewer = null;
  let carParts = [];
  let car = { lon: startLon, lat: startLat, heading: 0, speed: 0, steer: 0 };
  let cameraFollow = true;
  let lastTime = 0;
  const keys = Object.create(null);

  function setFollowButton() {
    document.getElementById("follow").textContent =
      "카메라 따라가기: " + (cameraFollow ? "켜짐" : "꺼짐") + " (C)";
  }
  document.getElementById("follow").addEventListener("click", function () {
    cameraFollow = !cameraFollow;
    setFollowButton();
    if (!cameraFollow && viewer && typeof Cesium !== "undefined") {
      viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
    }
  });

  window.addEventListener("keydown", function (e) {
    const controlled = ["KeyW","KeyA","KeyS","KeyD","ArrowUp","ArrowDown",
                        "ArrowLeft","ArrowRight","Space","KeyC"];
    if (controlled.includes(e.code)) e.preventDefault();
    keys[e.code] = true;
    if (e.code === "Space") car.speed = 0;
    if (e.code === "KeyC" && !e.repeat) {
      cameraFollow = !cameraFollow;
      setFollowButton();
      if (!cameraFollow && viewer && typeof Cesium !== "undefined") {
        viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
      }
    }
  });
  window.addEventListener("keyup", function (e) { keys[e.code] = false; });
  window.addEventListener("blur", function () {
    Object.keys(keys).forEach(k => keys[k] = false);
  });

  // 동서/남북 미터 오프셋을 경위도로 변환한다.
  function offsetPosition(lon, lat, eastMeters, northMeters) {
    const metersPerLon = 111320 * Math.cos(lat * Math.PI / 180);
    return {
      lon: lon + eastMeters / metersPerLon,
      lat: lat + northMeters / 110540
    };
  }

  function makePart(name, dimensions, color, dx, dy, dz, steeringWheel) {
    const pos = Cesium.Cartesian3.fromDegrees(car.lon, car.lat, startHeight + dz);
    const entity = viewer.entities.add({
      name: name,
      position: pos,
      orientation: Cesium.Transforms.headingPitchRollQuaternion(
        pos, new Cesium.HeadingPitchRoll(car.heading, 0, 0)
      ),
      box: {
        dimensions: new Cesium.Cartesian3(dimensions[0], dimensions[1], dimensions[2]),
        material: Cesium.Color.fromCssColorString(color)
      }
    });
    const part = { entity, dx, dy, dz, steeringWheel: !!steeringWheel, type: "box" };
    carParts.push(part);
    return part;
  }

  function makeWheel(name, dx, dy, front) {
    const pos = Cesium.Cartesian3.fromDegrees(car.lon, car.lat, startHeight + 0.43);
    const entity = viewer.entities.add({
      name: name,
      position: pos,
      orientation: Cesium.Transforms.headingPitchRollQuaternion(
        pos, new Cesium.HeadingPitchRoll(car.heading, 0, 0)
      ),
      ellipsoid: {
        radii: new Cesium.Cartesian3(0.22, 0.40, 0.40),
        material: Cesium.Color.fromCssColorString("#202328")
      }
    });
    carParts.push({
      entity, dx, dy, dz: 0.43, steeringWheel: front, type: "wheel"
    });
  }

  function updateCarParts() {
    for (const part of carParts) {
      // 차체 방향에 맞춰 각 부품의 위치를 회전시킨다.
      const east = part.dx * Math.cos(car.heading) + part.dy * Math.sin(car.heading);
      const north = -part.dx * Math.sin(car.heading) + part.dy * Math.cos(car.heading);
      const p = offsetPosition(car.lon, car.lat, east, north);
      const pos = Cesium.Cartesian3.fromDegrees(p.lon, p.lat, startHeight + part.dz);
      const h = car.heading + (part.steeringWheel ? car.steer : 0);
      part.entity.position = pos;
      part.entity.orientation = Cesium.Transforms.headingPitchRollQuaternion(
        pos, new Cesium.HeadingPitchRoll(h, 0, 0)
      );
    }
  }

  function createCar() {
    // 간단한 블록 형태의 자동차: 실제 지도 위에서 미터 단위 크기로 표현
    makePart("자동차 차체", [1.85, 4.15, 0.72], "#c92e38", 0, 0, 0.68, false);
    makePart("자동차 객실", [1.55, 1.95, 0.72], "#8fc4d8", 0, -0.20, 1.36, false);
    makePart("자동차 앞부분", [1.72, 0.72, 0.20], "#a91f2a", 0, 1.55, 1.08, false);

    makeWheel("왼쪽 앞바퀴", -1.00, 1.28, true);
    makeWheel("오른쪽 앞바퀴", 1.00, 1.28, true);
    makeWheel("왼쪽 뒷바퀴", -1.00, -1.30, false);
    makeWheel("오른쪽 뒷바퀴", 1.00, -1.30, false);
    updateCarParts();
  }

  function animate(time) {
    requestAnimationFrame(animate);
    if (!viewer || typeof Cesium === "undefined") return;
    if (!lastTime) lastTime = time;
    const dt = Math.min((time - lastTime) / 1000, 0.04);
    lastTime = time;

    if (keys.KeyW || keys.ArrowUp) car.speed = Math.min(13.9, car.speed + 4.0 * dt);
    else if (keys.KeyS || keys.ArrowDown) car.speed = Math.max(-4.0, car.speed - 4.0 * dt);
    else car.speed *= Math.pow(0.94, dt * 60);

    let targetSteer = 0;
    if (keys.KeyA || keys.ArrowLeft) targetSteer = -0.48;
    if (keys.KeyD || keys.ArrowRight) targetSteer = 0.48;
    car.steer += (targetSteer - car.steer) * Math.min(1, dt * 8);

    // 휠베이스 2.7m인 간단한 자전거 모델로 차체 방향을 계산
    if (Math.abs(car.speed) > 0.02) {
      car.heading += (car.speed / 2.7) * Math.tan(car.steer) * dt;
    }

    const east = Math.sin(car.heading) * car.speed * dt;
    const north = Math.cos(car.heading) * car.speed * dt;
    const next = offsetPosition(car.lon, car.lat, east, north);
    car.lon = next.lon;
    car.lat = next.lat;

    updateCarParts();

    const kmh = Math.round(Math.abs(car.speed) * 3.6);
    const dirs = ["북쪽","북동쪽","동쪽","남동쪽","남쪽","남서쪽","서쪽","북서쪽"];
    const degrees = ((car.heading * 180 / Math.PI) % 360 + 360) % 360;
    document.getElementById("speed").textContent = kmh;
    document.getElementById("direction").textContent = dirs[Math.round(degrees / 45) % 8];
    document.getElementById("steering").textContent =
      Math.round(car.steer * 180 / Math.PI);

    if (cameraFollow) {
      const target = Cesium.Cartesian3.fromDegrees(car.lon, car.lat, 0);
      viewer.camera.lookAt(
        target,
        new Cesium.HeadingPitchRange(car.heading, Cesium.Math.toRadians(-32), 34)
      );
    }
  }

  // 브이월드 3D 지도가 준비된 뒤 지도 내부의 Cesium Viewer에 자동차를 추가
  vw.ws3dInitCallBack = function () {
    try {
      // 브이월드 공식 예제에서 사용하는 Cesium Viewer 접근 방식
      viewer = ws3d.viewer;
      if (!viewer) {
        showError("브이월드 지도 Viewer를 찾지 못했습니다. 인증키와 3D 지도 초기화 상태를 확인해 주세요.");
        return;
      }

      // 브이월드 기본 3D 건물 레이어를 표시한다.
      try {
        const buildingLayer = map.getElementById("facility_build");
        if (buildingLayer && buildingLayer.show) buildingLayer.show();
      } catch (e) {
        // 기본 설정에서 건물 레이어가 이미 표시 중일 수 있다.
      }

      createCar();
      setFollowButton();
      requestAnimationFrame(animate);
    } catch (err) {
      showError("자동차 생성 중 오류가 발생했습니다: " + err.message);
    }
  };

  map.start();

  // 초기화가 지연되거나 콜백이 오지 않을 때 사용자에게 상태를 알린다.
  setTimeout(function () {
    if (!viewer && errorBox.style.display !== "block") {
      showError("브이월드 지도 초기화가 오래 걸리고 있습니다. 인증키의 서비스 URL에 car-drive-ty2kofhslkkbneko5hrhmm.streamlit.app 도메인이 등록되어 있는지 확인해 주세요.");
    }
  }, 18000);
})();
</script>
</body>
</html>
"""

html = html.replace("__VWORLD_KEY__", encoded_key)
components.html(html, height=730, scrolling=False)
