import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="3D 운전 교실", page_icon="🚗", layout="wide")
st.title("🚗 3D 운전 교실")
st.caption("가벼운 3D 가상 도로에서 자동차를 운전해 보세요.")
st.markdown(
    "**W/S 또는 ↑/↓:** 전진·후진　 **A/D 또는 ←/→:** 앞바퀴 조향(좌/우)　 "
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
#hud { position:absolute; z-index:2; top:12px; left:12px; padding:9px 13px;
       background:#172638dd; color:white; border-radius:9px; line-height:1.6;
       pointer-events:none; font-size:14px; }
#help { position:absolute; z-index:2; bottom:10px; right:10px; padding:7px 10px;
        background:#172638cc; color:white; border-radius:8px; font-size:12px;
        pointer-events:none; }
#error { display:none; position:absolute; z-index:3; inset:12px; height:max-content;
         color:white; background:#7b2020; padding:14px; border-radius:8px; }
canvas { display:block; }
</style>
</head>
<body>
<div id="game">
  <div id="hud">속도 <span id="speed">0</span> km/h<br>방향 <span id="dir">북쪽</span></div>
  <div id="help">W/S 주행 · A/D 앞바퀴 조향 · 드래그 시점 회전 · 휠 줌 · 스페이스 정지</div>
  <div id="error"></div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
(() => {
  const root = document.getElementById("game");
  const errorBox = document.getElementById("error");
  if (!window.THREE) {
    errorBox.style.display = "block";
    errorBox.textContent = "3D 라이브러리를 불러오지 못했습니다. 페이지를 새로고침하거나 인터넷 연결을 확인해 주세요.";
    return;
  }

  const T = THREE;
  const scene = new T.Scene();
  scene.background = new T.Color(0xb9d9ef);
  scene.fog = new T.Fog(0xb9d9ef, 85, 190);

  const camera = new T.PerspectiveCamera(62, root.clientWidth / 650, 0.1, 300);
  const renderer = new T.WebGLRenderer({
    antialias: false,
    powerPreference: "low-power",
    alpha: false
  });
  renderer.setPixelRatio(1);
  renderer.setSize(root.clientWidth, 650);
  renderer.shadowMap.enabled = false;
  root.appendChild(renderer.domElement);

  scene.add(new T.HemisphereLight(0xffffff, 0x718064, 1.5));
  const sun = new T.DirectionalLight(0xffffff, 0.8);
  sun.position.set(-25, 45, 20);
  scene.add(sun);

  const mat = (color) => new T.MeshLambertMaterial({ color });
  const grassMat = mat(0x6d9d61);
  const roadMat = mat(0x343b43);
  const curbMat = mat(0xb9b9b2);
  const lineMat = mat(0xf5df8a);

  function box(parent, w, h, d, material, x, y, z) {
    const mesh = new T.Mesh(new T.BoxGeometry(w, h, d), material);
    mesh.position.set(x, y, z);
    parent.add(mesh);
    return mesh;
  }

  // 바닥과 도로
  const ground = new T.Mesh(new T.PlaneGeometry(400, 400), grassMat);
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.12;
  scene.add(ground);

  box(scene, 15, 0.08, 220, roadMat, 0, -0.035, 0);
  box(scene, 220, 0.08, 15, roadMat, 0, -0.035, 0);

  // 도로 가장자리
  box(scene, 0.35, 0.12, 220, curbMat, -7.7, 0.02, 0);
  box(scene, 0.35, 0.12, 220, curbMat, 7.7, 0.02, 0);
  box(scene, 220, 0.12, 0.35, curbMat, 0, 0.02, -7.7);
  box(scene, 220, 0.12, 0.35, curbMat, 0, 0.02, 7.7);

  // 중앙 차선
  for (let p = -100; p <= 100; p += 14) {
    box(scene, 0.14, 0.025, 5, lineMat, 0, 0.025, p);
    box(scene, 5, 0.025, 0.14, lineMat, p, 0.025, 0);
  }

  // 건물
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
      const w = 8 + rand() * 4;
      const d = 8 + rand() * 4;
      const h = 7 + rand() * 15;

      box(scene, w, h, d,
        buildingMats[Math.floor(rand() * buildingMats.length)],
        bx, h / 2, bz);
    }
  }

  // 나무
  const trunkMat = mat(0x765034);
  const leafMat = mat(0x397c45);
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

  // 자동차 모델
  const car = new T.Group();
  scene.add(car);

  const paint = mat(0xd93636);
  const dark = mat(0x20252b);
  const glass = mat(0x8fc5d8);
  const lampMat = mat(0xffe8a8);

  box(car, 2.05, 0.58, 3.8, paint, 0, 0.78, 0);
  box(car, 1.62, 0.82, 1.85, paint, 0, 1.43, -0.28);
  box(car, 1.48, 0.58, 1.68, glass, 0, 1.48, -0.28);
  box(car, 1.85, 0.13, 0.8, dark, 0, 1.1, 1.12);
  box(car, 0.34, 0.15, 0.1, lampMat, -0.65, 0.88, 1.92);
  box(car, 0.34, 0.15, 0.1, lampMat, 0.65, 0.88, 1.92);

  const wheelGeo = new T.CylinderGeometry(0.4, 0.4, 0.28, 10);
  const frontWheelPivots = [];
  const allWheels = [];

  // 앞바퀴: 좌우 조향 가능
  for (const x of [-1.03, 1.03]) {
    const pivot = new T.Group();
    pivot.position.set(x, 0.43, 1.18);
    car.add(pivot);

    const wheel = new T.Mesh(wheelGeo, dark);
    wheel.rotation.z = Math.PI / 2;
    pivot.add(wheel);

    frontWheelPivots.push(pivot);
    allWheels.push(wheel);
  }

  // 뒷바퀴: 방향은 고정되고 회전만 함
  for (const x of [-1.03, 1.03]) {
    const wheel = new T.Mesh(wheelGeo, dark);
    wheel.rotation.z = Math.PI / 2;
    wheel.position.set(x, 0.43, -1.18);
    car.add(wheel);
    allWheels.push(wheel);
  }

  const keys = Object.create(null);
  let speed = 0;
  let yaw = 0;
  let steeringAngle = 0;
  let orbit = 0;
  let pitch = 0.2;
  let distance = 10;
  let dragging = false;
  let lastX = 0;
  let lastY = 0;

  window.addEventListener("keydown", (e) => {
    if (["KeyW","KeyA","KeyS","KeyD","Space","ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.code)) {
      e.preventDefault();
    }
    keys[e.code] = true;
    if (e.code === "Space") speed = 0;
  });

  window.addEventListener("keyup", (e) => {
    keys[e.code] = false;
  });

  window.addEventListener("blur", () => {
    for (const k in keys) keys[k] = false;
  });

  // 마우스로 시점 회전
  renderer.domElement.addEventListener("pointerdown", (e) => {
    dragging = true;
    lastX = e.clientX;
    lastY = e.clientY;
    renderer.domElement.setPointerCapture(e.pointerId);
  });

  renderer.domElement.addEventListener("pointerup", () => {
    dragging = false;
  });

  renderer.domElement.addEventListener("pointercancel", () => {
    dragging = false;
  });

  renderer.domElement.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    orbit -= (e.clientX - lastX) * 0.006;
    pitch = Math.max(-0.05, Math.min(0.8, pitch + (e.clientY - lastY) * 0.004));
    lastX = e.clientX;
    lastY = e.clientY;
  });

  // 마우스 휠로 줌
  renderer.domElement.addEventListener("wheel", (e) => {
    distance = Math.max(5, Math.min(20, distance + e.deltaY * 0.01));
  }, { passive: true });

  const speedText = document.getElementById("speed");
  const dirText = document.getElementById("dir");
  const directions = ["북쪽","북동쪽","동쪽","남동쪽","남쪽","남서쪽","서쪽","북서쪽"];
  const clock = new T.Clock();

  function animate() {
    requestAnimationFrame(animate);
    const dt = Math.min(clock.getDelta(), 0.04);

    // W/S: 전진과 후진
    if (keys.KeyW || keys.ArrowUp) {
      speed = Math.min(10, speed + 5 * dt);
    } else if (keys.KeyS || keys.ArrowDown) {
      speed = Math.max(-5, speed - 5 * dt);
    } else {
      speed *= Math.pow(0.94, dt * 60);
    }

    // A/D: 앞바퀴 조향
    const steerInput =
      (keys.KeyD || keys.ArrowRight ? 1 : 0) -
      (keys.KeyA || keys.ArrowLeft ? 1 : 0);

    const maxSteering = 0.48;
    const targetSteering = steerInput * maxSteering;

    // 키를 놓으면 앞바퀴가 중앙으로 돌아옴
    steeringAngle += (targetSteering - steeringAngle) * Math.min(1, 5 * dt);

    for (const pivot of frontWheelPivots) {
      pivot.rotation.y = steeringAngle;
    }

    // 앞바퀴 조향각에 따라 차체가 회전
    const wheelBase = 2.36;
    yaw += (speed / wheelBase) * Math.tan(steeringAngle) * dt;

    car.rotation.y = yaw;

    car.position.x = Math.max(-103, Math.min(103,
      car.position.x + Math.sin(yaw) * speed * dt));

    car.position.z = Math.max(-103, Math.min(103,
      car.position.z + Math.cos(yaw) * speed * dt));

    // 네 바퀴 회전
    for (const wheel of allWheels) {
      wheel.rotation.x -= speed * dt / 0.4;
    }

    // 카메라
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
