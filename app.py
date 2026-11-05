import streamlit as st
import streamlit.components.v1 as components
import requests, math, json

st.set_page_config(page_title="실제 도시 3D 입체 운전 시뮬레이터", layout="wide")
st.title("🚗 실제 도시 기반 3D 입체 운전 시뮬레이터 (광폭 도로 & 자유 시점)")
st.caption("차량 크기 대비 넓은 도로 폭과 도로 이탈 방지, 마우스 자유 시점 기능이 적용된 시뮬레이터입니다.")

# 사이드바 설정
st.sidebar.header("🗺️ 지도 설정")
place = st.sidebar.text_input("도시/주소 입력", "서울특별시 강남구")
radius = st.sidebar.select_slider("지도 범위 반경", options=[500, 750, 1000, 1500, 2000], value=1000)
terrain_height_scale = st.sidebar.slider("지형 고도(기복) 배율", 0.1, 2.0, 1.0, 0.1)
load = st.sidebar.button("도시 불러오기", type="primary")

@st.cache_data(ttl=3600)
def geocode(q):
    r = requests.get("https://nominatim.openstreetmap.org/search",
        params={"q": q, "format": "json", "limit": 1},
        headers={"User-Agent": "Student3DDrivingSimulator/4.0"}, timeout=25)
    r.raise_for_status()
    a = r.json()
    if not a: raise ValueError("장소를 찾지 못했습니다. 더 구체적인 주소를 입력하세요.")
    return float(a[0]["lat"]), float(a[0]["lon"]), a[0]["display_name"]

@st.cache_data(ttl=3600)
def get_osm(lat, lon, r):
    dlat = r / 111320
    dlon = r / (111320 * max(math.cos(math.radians(lat)), .2))
    s, w, n, e = lat - dlat, lon - dlon, lat + dlat, lon + dlon
    q = f'''[out:json][timeout:90];(
    way["highway"~"motorway|trunk|primary|secondary|tertiary|motorway_link|trunk_link|primary_link|secondary_link"]({s},{w},{n},{e});
    way["building"]({s},{w},{n},{e});
    way["waterway"~"river|canal"]({s},{w},{n},{e});
    way["natural"="water"]({s},{w},{n},{e});
    way["natural"="wood"]({s},{w},{n},{e});
    way["landuse"="forest"]({s},{w},{n},{e});
    );out body geom;'''
    err = None
    for url in ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]:
        try:
            x = requests.post(url, data=q, headers={"User-Agent": "Student3DDrivingSimulator/4.0"}, timeout=110)
            x.raise_for_status()
            return x.json()
        except Exception as ex: err = ex
    raise RuntimeError(f"OSM 요청 실패: {err}")

def convert(data, lat, lon, t_scale):
    out = {"roads": [], "buildings": [], "water": [], "forests": []}
    fx = 111320 * math.cos(math.radians(lat))
    fz = 111320
    
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        g = el.get("geometry", [])
        if len(g) < 2: continue
        
        pts = [[(p["lon"] - lon) * fx * .1, -(p["lat"] - lat) * fz * .1] for p in g]
        
        def get_alt(x, z):
            return (math.sin(x * 0.003) * math.cos(z * 0.003) * 35.0 + math.sin(x * 0.01) * 5.0) * t_scale

        if "highway" in tags:
            hw = tags.get("highway", "")
            try: lanes = int(str(tags.get("lanes", "0")).split(";")[0])
            except: lanes = 0
            
            if lanes >= 2 or (lanes == 0 and hw in ("motorway", "trunk", "primary", "secondary", "tertiary", "motorway_link", "trunk_link", "primary_link")):
                try: width = float(str(tags.get("width", "")).replace("m", "").strip()) * .1
                except: width = max(3.6, lanes * 4.0 * .1 if lanes else 3.6)
                
                # 차 폭(1.5m)의 2배 이상인 최소 3.6m 이상의 폭으로 보장
                final_width = max(width, 3.6)
                
                road_pts = [[p[0], get_alt(p[0], p[1]), p[1]] for p in pts]
                out["roads"].append({
                    "p": road_pts, 
                    "w": final_width, 
                    "bridge": tags.get("bridge") == "yes", 
                    "name": tags.get("name", hw)
                })
                
        elif "building" in tags and len(pts) >= 3:
            try: h = float(str(tags.get("height", "25")).replace("m", "").strip()) * .1
            except: h = 2.5
            base_alt = get_alt(pts[0][0], pts[0][1])
            b_pts = [[p[0], p[1]] for p in pts]
            out["buildings"].append({"p": b_pts, "h": max(2.5, h), "alt": base_alt})
            
        elif "waterway" in tags or "natural" in tags and tags.get("natural") == "water":
            water_pts = [[p[0], get_alt(p[0], p[1]) - 0.5, p[1]] for p in pts]
            out["water"].append({"p": water_pts})
            
        elif tags.get("natural") == "wood" or tags.get("landuse") == "forest":
            if len(pts) >= 3:
                f_pts = [[p[0], p[1]] for p in pts]
                out["forests"].append({"p": f_pts})
                
    return out

if "citydata" not in st.session_state: st.session_state.citydata = None

if load:
    try:
        with st.spinner("실제 도시 및 지형 고도 데이터를 분석하는 중..."):
            lat, lon, name = geocode(place)
            raw = get_osm(lat, lon, radius)
            st.session_state.citydata = convert(raw, lat, lon, terrain_height_scale)
            st.session_state.cityname = name
    except Exception as e: st.error(str(e))

if st.session_state.citydata:
    data = st.session_state.citydata
    st.success(f"📍 {st.session_state.cityname}")
    st.write(f"도로 {len(data['roads'])}개 · 건물 {len(data['buildings'])}개 · 물길 {len(data['water'])}개")
    st.caption("조작 방법: W/S 가속·후진, A/D 조향 | 우측 상단 버튼으로 [자동차 추적 시점]과 [마우스 자유 시점]을 전환할 수 있습니다.")
    
    html = r'''<!DOCTYPE html><html><head><meta charset="utf-8">
<style>body{margin:0;overflow:hidden;font-family:Arial}#game{height:700px;position:relative}
#hud,#help{position:absolute;z-index:4;background:#18212ddd;color:white;padding:10px;border-radius:8px}
#hud{top:10px;left:10px}#help{top:10px;right:10px;font-size:12px;text-align:right;}
#buttons{position:absolute;bottom:12px;left:50%;transform:translateX(-50%);z-index:5;display:flex;gap:6px}
button{font-size:18px;padding:12px;background:#18212ddd;color:white;border:0;border-radius:8px;touch-action:none;cursor:pointer;}
#camBtn{margin-top:5px;background:#2a4365;font-size:11px;padding:5px 8px;border-radius:4px;}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.min.js"></script></head><body>
<div id="game">
<div id="hud">속도 <span id="spd">0</span> km/h<br><span id="msg">도로 위에서만 주행 가능합니다.</span></div>
<div id="help">W/S: 가속·후진 | A/D: 조향<br><button id="camBtn">시점: 차량 추적 모드</button></div>
<div id="buttons"><button id="l">◀</button><button id="f">▲</button><button id="b">▼</button><button id="r">▶</button></div></div>
<script>
const D = __DATA__;
const game = document.getElementById('game'), msg = document.getElementById('msg');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xb8c6d1);
scene.fog = new THREE.Fog(0xb8c6d1, 300, 900);

const camera = new THREE.PerspectiveCamera(65, game.clientWidth / game.clientHeight, .1, 2000);
const renderer = new THREE.WebGLRenderer({antialias: true, powerPreference: 'low-power'});
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.2));
renderer.setSize(game.clientWidth, game.clientHeight);
game.insertBefore(renderer.domElement, game.firstChild);

scene.add(new THREE.HemisphereLight(0xffffff, 0x666666, 2.2));
const sun = new THREE.DirectionalLight(0xffffff, 1.2);
sun.position.set(150, 300, 150);
scene.add(sun);

const material = c => new THREE.MeshLambertMaterial({color: c});
const gray = material(0x858585), roadmat = material(0x363636), watermat = material(0x5a829e), green = material(0x5a7a5a), trunkmat = material(0x554c43);

const terrainGeo = new THREE.PlaneGeometry(4000, 4000, 64, 64);
terrainGeo.rotateX(-Math.PI / 2);
const posAttr = terrainGeo.attributes.position;
for(let i=0; i<posAttr.count; i++) {
    let px = posAttr.getX(i), pz = posAttr.getZ(i);
    let py = (Math.sin(px * 0.003) * Math.cos(pz * 0.003) * 35.0 + Math.sin(px * 0.01) * 5.0);
    posAttr.setY(i, py);
}
terrainGeo.computeVertexNormals();
const ground = new THREE.Mesh(terrainGeo, material(0x7a8c7a));
scene.add(ground);

function road(points, width, mat) {
    for(let i = 0; i < points.length - 1; i++) {
        let a = points[i], b = points[i+1];
        let dx = b[0] - a[0], dz = b[2] - a[2], len = Math.hypot(dx, dz);
        if(len < .1) continue;
        let geo = new THREE.PlaneGeometry(width, len);
        geo.rotateX(-Math.PI / 2);
        let m = new THREE.Mesh(geo, mat);
        let mx = (a[0] + b[0]) / 2, mz = (a[2] + b[2]) / 2, my = (a[1] + b[1]) / 2 + 0.05;
        m.position.set(mx, my, mz);
        m.rotation.y = Math.atan2(dx, dz);
        let dy = b[1] - a[1];
        m.rotation.x = -Math.PI / 2 + Math.atan2(dy, len);
        scene.add(m);
    }
}

function building(p, h, alt) {
    const s = new THREE.Shape();
    s.moveTo(p[0][0], p[0][1]);
    for(let i = 1; i < p.length; i++) s.lineTo(p[i][0], p[i][1]);
    s.closePath();
    const g = new THREE.ExtrudeGeometry(s, {depth: h, bevelEnabled: false});
    g.rotateX(-Math.PI / 2);
    let mesh = new THREE.Mesh(g, gray);
    mesh.position.y = alt;
    scene.add(mesh);
}

for(const r of D.roads) road(r.p, r.w, roadmat);
for(const b of D.buildings) if(b.p.length >= 3) building(b.p, b.h, b.alt);
for(const w of D.water) road(w.p, 8, watermat);

// 차량 모델 (폭 1.5m 설정)
const car = new THREE.Group();
scene.add(car);
const body = new THREE.Mesh(new THREE.BoxGeometry(1.5, .6, 3), material(0xb83b3b));
body.position.y = .55; car.add(body);
const cabin = new THREE.Mesh(new THREE.BoxGeometry(1.1, .5, 1.3), material(0x777f83));
cabin.position.set(0, 1, -.2); car.add(cabin);
for(let x of [-.78, .78]) for(let z of [-.95, .95]) {
    let wheel = new THREE.Mesh(new THREE.BoxGeometry(.22, .45, .5), material(0x222222));
    wheel.position.set(x, .3, z); car.add(wheel);
}

let start = D.roads.find(r => r.p.length > 1)?.p[Math.floor(D.roads.find(r => r.p.length > 1).p.length / 2)] || [0, 0, 0];
car.position.set(start[0], start[1] + 0.5, start[2]);

let yaw = 0, v = 0, keys = {}, touch = {f: false, b: false, l: false, r: false};
window.addEventListener('keydown', e => keys[e.key.toLowerCase()] = true);
window.addEventListener('keyup', e => keys[e.key.toLowerCase()] = false);

function bind(id, k) {
    let el = document.getElementById(id);
    el.onpointerdown = e => { e.preventDefault(); touch[k] = true; };
    ['pointerup', 'pointercancel', 'pointerleave'].forEach(ev => el.addEventListener(ev, () => touch[k] = false));
}
bind('f', 'f'); bind('b', 'b'); bind('l', 'l'); bind('r', 'r');

function getTerrainHeight(x, z) {
    return (Math.sin(x * 0.003) * Math.cos(z * 0.003) * 35.0 + Math.sin(x * 0.01) * 5.0);
}

// 넓어진 도로 폭에 맞춘 도로 영역 감지 함수
function onroad(x, z) {
    for(let r of D.roads) {
        for(let i = 0; i < r.p.length - 1; i++) {
            let a = r.p[i], b = r.p[i+1];
            let vx = b[0] - a[0], vz = b[2] - a[2];
            let l2 = vx*vx + vz*vz;
            let t = l2 ? Math.max(0, Math.min(1, ((x - a[0]) * vx + (z - a[2]) * vz) / l2)) : 0;
            let dist = Math.hypot(x - (a[0] + t * vx), z - (a[2] + t * vz));
            if(dist < r.w / 2 + 0.2) return true;
        }
    }
    return false;
}

let freeCamMode = false;
let camAngleX = 0.5, camAngleY = 0, camDist = 20;
let isDragging = false, prevMousePos = {x: 0, y: 0};

const camBtn = document.getElementById('camBtn');
camBtn.onclick = () => {
    freeCamMode = !freeCamMode;
    camBtn.textContent = freeCamMode ? "시점: 마우스 자유 시점 (ON)" : "시점: 차량 추적 모드";
    camBtn.style.background = freeCamMode ? "#2f855a" : "#2a4365";
};

window.addEventListener('mousedown', e => {
    if(freeCamMode) { isDragging = true; prevMousePos = {x: e.clientX, y: e.clientY}; }
});
window.addEventListener('mouseup', () => { isDragging = false; });
window.addEventListener('mousemove', e => {
    if(freeCamMode && isDragging) {
        let dx = e.clientX - prevMousePos.x;
        let dy = e.clientY - prevMousePos.y;
        camAngleY -= dx * 0.005;
        camAngleX = Math.max(0.1, Math.min(1.5, camAngleX - dy * 0.005));
        prevMousePos = {x: e.clientX, y: e.clientY};
    }
});
window.addEventListener('wheel', e => {
    if(freeCamMode) {
        camDist = Math.max(5, Math.min(100, camDist + e.deltaY * 0.05));
    }
});

const target = new THREE.Vector3();
let last = performance.now();

function animate(now) {
    requestAnimationFrame(animate);
    let dt = Math.min((now - last) / 1000, .04);
    last = now;
    
    let f = keys.w || keys.arrowup || touch.f, b = keys.s || keys.arrowdown || touch.b;
    let L = keys.a || keys.arrowleft || touch.l, R = keys.d || keys.arrowright || touch.r;
    
    if(f) v = Math.min(15, v + 6 * dt);
    else if(b) v = Math.max(-4, v - 8 * dt);
    else v *= Math.pow(.98, dt * 60);
    
    let steering = (R ? 1 : 0) - (L ? 1 : 0);
    yaw += steering * v * .05 * dt;
    car.rotation.y = yaw;
    
    let nx = car.position.x + Math.sin(yaw) * v * dt;
    let nz = car.position.z + Math.cos(yaw) * v * dt;
    
    if(Math.abs(v) < 0.1 || onroad(nx, nz)) {
        car.position.x = nx;
        car.position.z = nz;
        car.position.y = getTerrainHeight(nx, nz) + 0.3;
        msg.textContent = '광폭 도로 위에서 주행 중';
    } else {
        v = 0;
        msg.textContent = '⚠️ 도로 밖으로 나갈 수 없습니다!';
    }
    
    if(!freeCamMode) {
        camera.position.lerp(new THREE.Vector3(car.position.x - Math.sin(yaw) * 9, car.position.y + 4.5, car.position.z - Math.cos(yaw) * 9), .1);
        target.set(car.position.x, car.position.y + 1, car.position.z);
        camera.lookAt(target);
    } else {
        let cx = car.position.x + Math.sin(camAngleY) * camDist * Math.sin(camAngleX);
        let cy = car.position.y + Math.cos(camAngleX) * camDist;
        let cz = car.position.z + Math.cos(camAngleY) * camDist * Math.sin(camAngleX);
        camera.position.set(cx, cy, cz);
        camera.lookAt(car.position);
    }
    
    document.getElementById('spd').textContent = Math.round(Math.abs(v) * 3.6);
    renderer.render(scene, camera);
}

requestAnimationFrame(animate);
window.addEventListener('resize', () => {
    camera.aspect = game.clientWidth / game.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(game.clientWidth, game.clientHeight);
});
</script></body></html>'''

    html = html.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    components.html(html, height=720, scrolling=False)
else:
    st.info("왼쪽 사이드바에서 도시와 주소를 입력하고 **'도시 불러오기'** 버튼을 누르세요.")
