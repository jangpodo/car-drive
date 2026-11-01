import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="3D 운전 교실", page_icon="🚗", layout="wide")
st.title("🚗 3D 운전 교실")
st.caption("앞바퀴 조향과 세부 자동차 모델을 추가한 3D 운전 시뮬레이터입니다.")
st.markdown(
    "**W/S 또는 ↑/↓:** 전진·후진　 **A/D 또는 ←/→:** 좌회전·우회전　 "
    "**마우스 드래그:** 시점 회전　 **마우스 휠:** 줌　 **스페이스:** 정지"
)

html = r"""
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<style>
html, body { margin:0; padding:0; overflow:hidden; background:#b9d9ef; font-family:Arial,sans-serif; }
#game { width:100%; height:650px; position:relative; overflow:hidden; }
#hud { position:absolute; z-index:2; top:12px; left:12px; padding:10px 14px;
       background:#172638e8; color:white; border-radius:10px; line-height:1.7;
       pointer-events:none; font-size:14px; min-width:135px; }
#help { position:absolute; z-index:2; bottom:10px; right:10px; padding:8px 11px;
        background:#172638dd; color:white; border-radius:8px; font-size:12px;
        pointer-events:none; }
#error { display:none; position:absolute; z-index:3; inset:12px; height:max-content;
         color:white; background:#7b2020; padding:14px; border-radius:8px; }
canvas { display:block; }
</style>
</head>
<body>
<div id="game">
  <div id="hud">
    속도 <b><span id="speed">0</span></b> km/h<br>
    방향 <b><span id="dir">북쪽</span></b><br>
    조향각 <b><span id="steer">0</span></b>°
  </div>
  <div id="help">WASD 운전 · A/D 앞바퀴 조향 · 드래그 시점 회전 · 휠 줌</div>
  <div id="error"></div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
(() => {
  const root = document.getElementById("game");
  const errorBox = document.getElementById("error");
  if (!window.THREE) {
    errorBox.style.display = "block";
    errorBox.textContent = "3D 라이브러리를 불러오지 못했습니다. 새로고침하거나 인터넷 연결을 확인해 주세요.";
    return;
  }

  const T = THREE;
  const scene = new T.Scene();
  scene.background = new T.Color(0xb9d9ef);
  scene.fog = new T.Fog(0xb9d9ef, 85, 190);

  const camera = new T.PerspectiveCamera(62, root.clientWidth / 650, 0.1, 300);
  const renderer = new T.WebGLRenderer({ antialias: true, powerPreference: "low-power" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.setSize(root.clientWidth, 650);
  renderer.shadowMap.enabled = false;
  root.appendChild(renderer.domElement);

  scene.add(new T.HemisphereLight(0xffffff, 0x718064, 1.6));
  const sun = new T.DirectionalLight(0xffffff, 0.9);
  sun.position.set(-25, 45, 20);
  scene.add(sun);

  const mat = (color, roughness=0.8, metalness=0) =>
    new T.MeshStandardMaterial({ color, roughness, metalness });

  const grassMat = mat(0x6d9d61);
  const roadMat = mat(0x343b43);
  const curbMat = mat(0xb9b9b2);
  const lineMat = mat(0xf5df8a);
  const whiteMat = mat(0xf4f1df);

  function box(parent, w, h, d, material, x, y, z) {
    const mesh = new T.Mesh(new T.BoxGeometry(w, h, d), material);
    mesh.position.set(x, y, z);
    parent.add(mesh);
    return mesh;
  }

  // 바닥과 십자 도로
  const ground = new T.Mesh(new T.PlaneGeometry(400, 400), grassMat);
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.12;
  scene.add(ground);
  box(scene, 15, 0.08, 220, roadMat, 0, -0.035, 0);
  box(scene, 220, 0.08, 15, roadMat, 0, -0.035, 0);

  box(scene, 0.35, 0.12, 220, curbMat, -7.7, 0.02, 0);
  box(scene, 0.35, 0.12, 220, curbMat, 7.7, 0.02, 0);
  box(scene, 220, 0.12, 0.35, curbMat, 0, 0.02, -7.7);
  box(scene, 220, 0.12, 0.35, curbMat, 0, 0.02, 7.7);

  for (let p = -100; p <= 100; p += 14) {
    box(scene, 0.14, 0.025, 5, lineMat, 0, 0.025, p);
    box(scene, 5, 0.025, 0.14, lineMat, p, 0.025, 0);
  }

  // 주변 건물
  const buildingMats = [
    mat(0xd9c7ad), mat(0xc4d4dc), mat(0xe0b9a8),
    mat(0xd4d0bd), mat(0xb9c8b2), mat(0xd2c1dc)
  ];
  let seed = 17;
  function rand() {
    seed = (seed * 9301 + 49297) % 233280;
    return seed / 233280;
  }
  for (let x = -3; x <= 3; x++) {
    for (let z = -3; z <= 3; z++) {
      if (Math.abs(x) <= 1 || Math.abs(z) <= 1) continue;
      const bx = x * 25 + (rand() - 0.5) * 3;
      const bz = z * 25 + (rand() - 0.5) * 3;
      const w = 8 + rand() * 4, d = 8 + rand() * 4, h = 7 + rand() * 15;
      const building = box(scene, w, h, d,
        buildingMats[Math.floor(rand() * buildingMats.length)], bx, h / 2, bz);
      // 건물 정면에 간단한 창문 띠
      const windowMat = mat(0x91b9c8, 0.35, 0.15);
      for (let yy = 2.2; yy < h - 1; yy += 3.2) {
        box(scene, w * 0.72, 0.75, 0.06, windowMat, bx, yy, bz + d / 2 + 0.04);
      }
    }
  }

  // 가로수
  const trunkMat = mat(0x765034), leafMat = mat(0x397c45);
  const trunkGeo = new T.CylinderGeometry(0.18, 0.24, 1.8, 6);
  const leafGeo = new T.SphereGeometry(1.05, 7, 6);
  for (let z = -85; z <= 85; z += 28) {
    for (const x of [-12, 12]) {
      const trunk = new T.Mesh(trunkGeo, trunkMat);
      trunk.position.set(x, 0.9, z);
      scene.add(trunk);
      const crown = new T.Mesh(leafGeo, leafMat);
      crown.position.set(x, 2.25, z);
      scene.add(crown);
    }
  }

  // 자동차 모델: 앞쪽은 +Z 방향
  const car = new T.Group();
  scene.add(car);

  const paint = mat(0xc92732, 0.32, 0.28);
  const paintDark = mat(0x861b25, 0.4, 0.2);
  const glass = mat(0x8fc5d8, 0.22, 0.18);
  const dark = mat(0x171c22, 0.75);
  const rubber = mat(0x17191c, 0.95);
  const rim = mat(0xc6cbd0, 0.28, 0.75);
  const lampMat = new T.MeshStandardMaterial({ color:0xfff0bd, emissive:0x665020 });
  const tailMat = new T.MeshStandardMaterial({ color:0xe51e2a, emissive:0x5a0000 });

  // 차체와 앞/뒤 범퍼
  box(car, 2.05, 0.58, 3.8, paint, 0, 0.78, 0);
  box(car, 1.92, 0.18, 0.22, dark, 0, 0.55, 1.92);
  box(car, 1.92, 0.18, 0.22, dark, 0, 0.55, -1.92);
  box(car, 1.72, 0.12, 0.55, paintDark, 0, 1.08, 1.48);

  // 지붕과 객실
  box(car, 1.62, 0.78, 1.85, paint, 0, 1.42, -0.25);
  box(car, 1.49, 0.53, 0.08, glass, 0, 1.48, 0.72);   // 앞유리
  box(car, 1.49, 0.50, 0.08, glass, 0, 1.48, -1.20);  // 뒷유리
  box(car, 0.08, 0.48, 1.45, glass, -0.82, 1.47, -0.25);
  box(car, 0.08, 0.48, 1.45, glass, 0.82, 1.47, -0.25);
  box(car, 1.78, 0.10, 0.22, paintDark, 0, 1.86, -0.25);

  // 사이드미러
  box(car, 0.22, 0.12, 0.18, dark, -1.02, 1.35, 0.45);
  box(car, 0.22, 0.12, 0.18, dark, 1.02, 1.35, 0.45);

  // 전조등과 후미등
  box(car, 0.38, 0.16, 0.08, lampMat, -0.68, 0.88, 1.94);
  box(car, 0.38, 0.16, 0.08, lampMat, 0.68, 0.88, 1.94);
  box(car, 0.38, 0.17, 0.08, tailMat, -0.68, 0.88, -1.94);
  box(car, 0.38, 0.17, 0.08, tailMat, 0.68, 0.88, -1.94);

  // 앞 그릴
  box(car, 0.72, 0.20, 0.045, dark, 0, 0.72, 1.965);

  // 바퀴는 회전축과 타이어/휠을 분리해 앞바퀴가 실제로 방향을 틀도록 구성
  const wheelGeo = new T.CylinderGeometry(0.40, 0.40, 0.28, 16);
  const rimGeo = new T.CylinderGeometry(0.22, 0.22, 0.292, 12);
  const wheels = [];
  const frontWheelPivots = [];

  for (const x of [-1.03, 1.03]) {
    for (const z of [-1.18, 1.18]) {
      const pivot = new T.Group();
      pivot.position.set(x, 0.43, z);
      car.add(pivot);

      const tire = new T.Mesh(wheelGeo, rubber);
      tire.rotation.z = Math.PI / 2;
      pivot.add(tire);

      const wheelFace = new T.Mesh(rimGeo, rim);
      wheelFace.rotation.z = Math.PI / 2;
      wheelFace.position.x = (x < 0 ? -0.012 : 0.012);
      pivot.add(wheelFace);

      // 휠 중앙 허브
      const hub = new T.Mesh(new T.CylinderGeometry(0.075, 0.075, 0.31, 10), dark);
      hub.rotation.z = Math.PI / 2;
      pivot.add(hub);

      wheels.push(pivot);
      if (z > 0) frontWheelPivots.push(pivot);
    }
  }

  const keys = Object.create(null);
  let speed = 0;
  let yaw = 0;
  let steering = 0;
  let orbit = 0;
  let pitch = 0.2;
  let distance = 10;
  let dragging = false;
  let lastX = 0, lastY = 0;

  window.addEventListener("keydown", (e) => {
    if (["KeyW","KeyA","KeyS","KeyD","Space","ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.code)) {
      e.preventDefault();
    }
    keys[e.code] = true;
    if (e.code === "Space") speed = 0;
  });
  window.addEventListener("keyup", (e) => { keys[e.code] = false; });
  window.addEventListener("blur", () => {
    for (const k in keys) keys[k] = false;
  });

  renderer.domElement.addEventListener("pointerdown", (e) => {
    dragging = true;
    lastX = e.clientX; lastY = e.clientY;
    renderer.domElement.setPointerCapture(e.pointerId);
  });
  renderer.domElement.addEventListener("pointerup", () => { dragging = false; });
  renderer.domElement.addEventListener("pointercancel", () => { dragging = false; });
  renderer.domElement.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    orbit -= (e.clientX - lastX) * 0.006;
    pitch = Math.max(-0.05, Math.min(0.8, pitch + (e.clientY - lastY) * 0.004));
    lastX = e.clientX; lastY = e.clientY;
  });
  renderer.domElement.addEventListener("wheel", (e) => {
    distance = Math.max(5, Math.min(20, distance + e.deltaY * 0.01));
  }, { passive: true });

  const speedText = document.getElementById("speed");
  const dirText = document.getElementById("dir");
  const steerText = document.getElementById("steer");
  const directions = ["북쪽","북동쪽","동쪽","남동쪽","남쪽","남서쪽","서쪽","북서쪽"];
  const clock = new T.Clock();

  function animate() {
    requestAnimationFrame(animate);
    const dt = Math.min(clock.getDelta(), 0.04);

    if (keys.KeyW || keys.ArrowUp) speed = Math.min(10, speed + 5 * dt);
    else if (keys.KeyS || keys.ArrowDown) speed = Math.max(-5, speed - 5 * dt);
    else speed *= Math.pow(0.94, dt * 60);

    // A/D 입력으로 앞바퀴 조향각을 부드럽게 변경
    let steerTarget = 0;
    if (keys.KeyA || keys.ArrowLeft) steerTarget = 0.52;
    if (keys.KeyD || keys.ArrowRight) steerTarget = -0.52;
    steering += (steerTarget - steering) * Math.min(1, dt * 9);

    // 앞바퀴의 회전 방향과 차체의 회전 방향을 일치시킴
    if (Math.abs(speed) > 0.03) {
      yaw += steering * 1.9 * dt * (speed < 0 ? -1 : 1);
    }
    car.rotation.y = yaw;
    car.position.x = Math.max(-103, Math.min(103, car.position.x + Math.sin(yaw) * speed * dt));
    car.position.z = Math.max(-103, Math.min(103, car.position.z + Math.cos(yaw) * speed * dt));

    // 앞바퀴만 좌우로 꺾이고, 모든 바퀴는 주행에 따라 회전
    for (const wheel of wheels) {
      wheel.rotation.x -= speed * dt / 0.4;
    }
    for (const frontWheel of frontWheelPivots) {
      frontWheel.rotation.y = steering;
    }

    const angle = yaw + orbit;
    const horizontal = distance * Math.cos(pitch);
    camera.position.set(
      car.position.x - Math.sin(angle) * horizontal,
      2.1 + distance * Math.sin(pitch),
      car.position.z - Math.cos(angle) * horizontal
    );
    camera.lookAt(car.position.x, 1, car.position.z);

    speedText.textContent = Math.round(Math.abs(speed) * 12);
    const deg = ((yaw * 180 / Math.PI) % 360 + 360) % 360;
    dirText.textContent = directions[Math.round(deg / 45) % 8];
    steerText.textContent = Math.round(steering * 180 / Math.PI);
    renderer.render(scene, camera);
  }

  animate();

  function resize() {
    const width = Math.max(1, root.clientWidth);
    camera.aspect = width / 650;
    camera.updateProjectionMatrix();
    renderer.setSize(width, 650);
  }
  window.addEventListener("resize", resize);
})();
</script>
</body>
</html>
"""
components.html(html, height=670, scrolling=False)
