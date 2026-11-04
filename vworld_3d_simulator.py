
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="서울 미니 3D 운전 시뮬레이터",
    page_icon="🚗",
    layout="wide"
)

st.title("🚗 서울 미니 3D 운전 시뮬레이터")
st.caption("저사양 그래픽 · 도로 주행 · 3인칭 카메라")

html = r"""
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<style>
html, body {
    margin: 0;
    padding: 0;
    overflow: hidden;
    background: #b9d3df;
    font-family: Arial, sans-serif;
}

#game {
    width: 100%;
    height: 650px;
    position: relative;
    overflow: hidden;
}

#hud {
    position: absolute;
    z-index: 5;
    top: 10px;
    left: 10px;
    background: rgba(15, 25, 35, 0.85);
    color: white;
    padding: 12px;
    border-radius: 8px;
    font-size: 14px;
    line-height: 1.7;
}

#message {
    color: #ffe082;
}

#controls {
    position: absolute;
    z-index: 5;
    bottom: 15px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    gap: 8px;
}

button {
    border: 0;
    border-radius: 8px;
    padding: 13px 18px;
    font-size: 18px;
    font-weight: bold;
    background: rgba(20, 35, 50, 0.88);
    color: white;
    cursor: pointer;
    user-select: none;
}

button:active {
    background: #e49a31;
}

#help {
    position: absolute;
    right: 10px;
    top: 10px;
    z-index: 5;
    background: rgba(15,25,35,0.8);
    color: white;
    padding: 10px;
    border-radius: 8px;
    font-size: 12px;
}
</style>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.min.js"></script>
</head>

<body>
<div id="game">
    <div id="hud">
        <b>서울 미니 드라이빙</b><br>
        속도: <span id="speed">0</span> km/h<br>
        구역: <span id="zone">서울 미니 시가지</span><br>
        <span id="message">도로 위에서 주행하세요.</span>
    </div>

    <div id="help">
        W / ↑ : 전진<br>
        S / ↓ : 후진<br>
        A / ← : 좌회전<br>
        D / → : 우회전<br>
        회전은 교차로에서 가능
    </div>

    <div id="controls">
        <button id="left">↶</button>
        <button id="forward">▲</button>
        <button id="backward">▼</button>
        <button id="right">↷</button>
    </div>
</div>

<script>
(function () {
"use strict";

const game = document.getElementById("game");
const speedText = document.getElementById("speed");
const messageText = document.getElementById("message");

if (!window.THREE) {
    messageText.textContent = "3D 라이브러리 로딩 실패. 인터넷 연결을 확인하세요.";
    return;
}

// ================================
// 저사양 렌더링 설정
// ================================

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xb9d3df);
scene.fog = new THREE.Fog(0xb9d3df, 180, 450);

const camera = new THREE.PerspectiveCamera(
    65,
    game.clientWidth / game.clientHeight,
    0.1,
    600
);

const renderer = new THREE.WebGLRenderer({
    antialias: false,
    powerPreference: "low-power"
});

renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1));
renderer.setSize(game.clientWidth, game.clientHeight);
renderer.shadowMap.enabled = false;

game.insertBefore(renderer.domElement, game.firstChild);

scene.add(new THREE.HemisphereLight(0xffffff, 0x667766, 2));

const sun = new THREE.DirectionalLight(0xffffff, 1.2);
sun.position.set(100, 150, 100);
scene.add(sun);

// ================================
// 재사용 재질
// ================================

const materials = {
    grass: new THREE.MeshLambertMaterial({ color: 0x86a96b }),
    road: new THREE.MeshLambertMaterial({ color: 0x41464c }),
    line: new THREE.MeshLambertMaterial({ color: 0xd8d5c7 }),
    river: new THREE.MeshLambertMaterial({ color: 0x4b9cc7 }),
    bridge: new THREE.MeshLambertMaterial({ color: 0x777c80 }),
    rail: new THREE.MeshLambertMaterial({ color: 0x92999d }),
    car: new THREE.MeshLambertMaterial({ color: 0xe33b32 }),
    window: new THREE.MeshLambertMaterial({ color: 0x8eb8cc }),
    wheel: new THREE.MeshLambertMaterial({ color: 0x222222 })
};

function box(x, y, z, sx, sy, sz, material) {
    const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(sx, sy, sz),
        material
    );
    mesh.position.set(x, y, z);
    scene.add(mesh);
    return mesh;
}

// ================================
// 도시 설정
// ================================

const CITY_LIMIT = 200;
const ROAD_SPACING = 40;
const ROAD_WIDTH = 12;
const HALF_ROAD = ROAD_WIDTH / 2;

// 도시 바닥
box(0, -0.7, 0, 420, 1, 420, materials.grass);

// 한강: z축 방향으로 흐르는 강
box(0, -0.15, 0, 420, 0.25, 28, materials.river);

// 도로망 생성
for (let i = -5; i <= 5; i++) {
    const p = i * ROAD_SPACING;

    // 세로 방향 도로
    box(p, -0.25, 0, ROAD_WIDTH, 0.3, 420, materials.road);

    // 가로 방향 도로
    box(0, -0.25, p, 420, 0.3, ROAD_WIDTH, materials.road);
}

// 한강 다리: 도로가 강을 건너는 부분
for (let x = -160; x <= 160; x += ROAD_SPACING) {
    box(x, 0.05, 0, ROAD_WIDTH, 0.4, 28, materials.bridge);
}

// 도로 중앙선
for (let i = -5; i <= 5; i++) {
    const p = i * ROAD_SPACING;

    for (let z = -190; z <= 190; z += 18) {
        box(p, -0.06, z, 0.25, 0.05, 5, materials.line);
    }

    for (let x = -190; x <= 190; x += 18) {
        box(x, -0.06, p, 5, 0.05, 0.25, materials.line);
    }
}

// ================================
// 낮은 가드레일
// 교차로 부분은 비워서 회전 가능
// ================================

function makeRail(x, z, length, alongX) {
    const railHeight = 0.65;
    const railY = railHeight / 2;

    if (alongX) {
        box(x, railY, z, length, 0.12, 0.18, materials.rail);

        for (let p = -length/2; p <= length/2; p += 4) {
            box(x + p, railY/2, z, 0.12, railHeight, 0.12, materials.rail);
        }
    } else {
        box(x, railY, z, 0.18, 0.12, length, materials.rail);

        for (let p = -length/2; p <= length/2; p += 4) {
            box(x, railY/2, z + p, 0.12, railHeight, 0.12, materials.rail);
        }
    }
}

// 도로 사이 구간에만 가드레일 배치
for (let i = -5; i < 5; i++) {
    for (let j = -5; j < 5; j++) {
        const x = i * ROAD_SPACING;
        const z = j * ROAD_SPACING;

        const segment = ROAD_SPACING - ROAD_WIDTH;

        // 세로 도로 양옆
        makeRail(x - HALF_ROAD - 0.3, z + 20, segment, false);
        makeRail(x + HALF_ROAD + 0.3, z + 20, segment, false);

        // 가로 도로 양옆
        makeRail(x + 20, z - HALF_ROAD - 0.3, segment, true);
        makeRail(x + 20, z + HALF_ROAD + 0.3, segment, true);
    }
}

// ================================
// 저폴리곤 건물
// ================================

const buildingMaterials = [
    0xb9b5ae, 0xc8c3ba, 0xa7b4bd,
    0xd0c6b5, 0x9ba8ad, 0xb5c1b4
].map(c => new THREE.MeshLambertMaterial({ color: c }));

// 각 건물을 도로와 도로 사이 블록 중앙에 배치
// 도로 중심은 40 단위 간격, 도로 폭은 12 단위이므로
// 건물은 도로 위가 아닌 블록 내부에 생성됨
for (let x = -180; x <= 180; x += ROAD_SPACING) {
    for (let z = -180; z <= 180; z += ROAD_SPACING) {
        const bx = x;
        const bz = z;

        const width = 10 + Math.random() * 7;
        const depth = 10 + Math.random() * 7;
        const height = 8 + Math.random() * 35;

        const material = buildingMaterials[
            Math.floor(Math.random() * buildingMaterials.length)
        ];

        box(
            bx, height / 2, bz,
            width, height, depth,
            material
        );

        // 일부 건물에 간단한 옥상 장식 추가
        if (Math.random() > 0.7) {
            box(
                bx, height + 1, bz,
                width * 0.3, 2, depth * 0.3,
                materials.bridge
            );
        }
    }
}

// ================================

// 자동차 생성
// ================================

const car = new THREE.Group();
scene.add(car);

const body = new THREE.Mesh(
    new THREE.BoxGeometry(2.3, 1, 4.2),
    materials.car
);
body.position.y = 1;
car.add(body);

const cabin = new THREE.Mesh(
    new THREE.BoxGeometry(1.7, 0.8, 2),
    materials.window
);
cabin.position.set(0, 1.85, -0.2);
car.add(cabin);

// 바퀴
for (const x of [-1.15, 1.15]) {
    for (const z of [-1.35, 1.35]) {
        const wheel = new THREE.Mesh(
            new THREE.BoxGeometry(0.35, 0.65, 0.8),
            materials.wheel
        );
        wheel.position.set(x, 0.45, z);
        car.add(wheel);
    }
}

// 자동차 시작 위치
car.position.set(0, 0, 80);

// 방향: +Z
let direction = 0;
let speed = 0;
const MAX_SPEED = 24;
const ACCEL = 18;
const BRAKE = 25;

const keys = {};
let touchForward = false;
let touchBackward = false;
let touchLeft = false;
let touchRight = false;

window.addEventListener("keydown", e => {
    keys[e.key.toLowerCase()] = true;
});

window.addEventListener("keyup", e => {
    keys[e.key.toLowerCase()] = false;
});

function bindButton(id, setter) {
    const button = document.getElementById(id);

    button.addEventListener("pointerdown", e => {
        e.preventDefault();
        setter(true);
    });

    button.addEventListener("pointerup", () => setter(false));
    button.addEventListener("pointerleave", () => setter(false));
    button.addEventListener("pointercancel", () => setter(false));
}

bindButton("forward", v => touchForward = v);
bindButton("backward", v => touchBackward = v);
bindButton("left", v => touchLeft = v);
bindButton("right", v => touchRight = v);

// ================================
// 도로 판정
// ================================

function nearestRoad(v) {
    return Math.round(v / ROAD_SPACING) * ROAD_SPACING;
}

function isOnRoad(x, z) {
    const roadX = Math.abs(x - nearestRoad(x)) <= HALF_ROAD - 1;
    const roadZ = Math.abs(z - nearestRoad(z)) <= HALF_ROAD - 1;

    // 도로 교차점 또는 도로 위
    const onRoad = roadX || roadZ;

    // 강은 다리 위치에서만 건널 수 있음
    const inRiver = Math.abs(z) < 14;
    const onBridge = roadX;

    if (inRiver && !onBridge) return false;

    return onRoad;
}

function isIntersection(x, z) {
    const dx = Math.abs(x - nearestRoad(x));
    const dz = Math.abs(z - nearestRoad(z));

    return dx < 3.5 && dz < 3.5;
}

// ================================
// 회전
// ================================

function tryTurn(turn) {
    if (!isIntersection(car.position.x, car.position.z)) {
        messageText.textContent = "교차로에서만 방향을 바꿀 수 있습니다.";
        return;
    }

    // 교차로 중심에 정렬
    car.position.x = nearestRoad(car.position.x);
    car.position.z = nearestRoad(car.position.z);

    direction = (direction + turn + 4) % 4;
    car.rotation.y = direction * Math.PI / 2;

    messageText.textContent = "방향 전환 완료";
}

// ================================
// 카메라
// ================================

const cameraTarget = new THREE.Vector3();

function updateCamera() {
    const angle = car.rotation.y;

    const offset = new THREE.Vector3(
        -Math.sin(angle) * 13,
        7,
        -Math.cos(angle) * 13
    );

    const desired = car.position.clone().add(offset);

    camera.position.lerp(desired, 0.08);

    cameraTarget.set(
        car.position.x,
        car.position.y + 1.2,
        car.position.z
    );

    camera.lookAt(cameraTarget);
}

camera.position.set(0, 8, 95);
camera.lookAt(car.position);

// ================================
// 주행 업데이트
// ================================

let lastTime = performance.now();
let turnCooldown = 0;

function animate(now) {
    requestAnimationFrame(animate);

    const dt = Math.min((now - lastTime) / 1000, 0.05);
    lastTime = now;

    const forward = keys["w"] || keys["arrowup"] || touchForward;
    const backward = keys["s"] || keys["arrowdown"] || touchBackward;
    const left = keys["a"] || keys["arrowleft"] || touchLeft;
    const right = keys["d"] || keys["arrowright"] || touchRight;

    if (forward) {
        speed = Math.min(MAX_SPEED, speed + ACCEL * dt);
    } else if (backward) {
        speed = Math.max(-MAX_SPEED / 2, speed - BRAKE * dt);
    } else {
        speed *= Math.pow(0.92, dt * 60);
    }

    turnCooldown -= dt;

    if (turnCooldown <= 0) {
        if (left) {
            tryTurn(-1);
            turnCooldown = 0.35;
        } else if (right) {
            tryTurn(1);
            turnCooldown = 0.35;
        }
    }

    // 자동차 이동 방향
    let dx = 0;
    let dz = 0;

    if (direction === 0) dz = 1;
    if (direction === 1) dx = 1;
    if (direction === 2) dz = -1;
    if (direction === 3) dx = -1;

    const nextX = car.position.x + dx * speed * dt;
    const nextZ = car.position.z + dz * speed * dt;

    if (isOnRoad(nextX, nextZ)) {
        car.position.x = nextX;
        car.position.z = nextZ;
        messageText.textContent = "도로 주행 중";
    } else {
        speed = 0;
        messageText.textContent = "도로 밖으로 이동할 수 없습니다!";
    }

    // 도시 경계
    car.position.x = THREE.MathUtils.clamp(
        car.position.x, -CITY_LIMIT + 5, CITY_LIMIT - 5
    );

    car.position.z = THREE.MathUtils.clamp(
        car.position.z, -CITY_LIMIT + 5, CITY_LIMIT - 5
    );

    speedText.textContent = Math.round(Math.abs(speed) * 3.6);

    updateCamera();

    renderer.render(scene, camera);
}

requestAnimationFrame(animate);

// 화면 크기 변경
window.addEventListener("resize", function () {
    camera.aspect = game.clientWidth / game.clientHeight;
    camera.updateProjectionMatrix();

    renderer.setSize(game.clientWidth, game.clientHeight);
});

})();
</script>
</body>
</html>
"""

components.html(
    html,
    height=660,
    scrolling=False
)
