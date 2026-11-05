import streamlit as st
import streamlit.components.v1 as components
import requests, math, json

st.set_page_config(page_title="실제 도시 3D 입체 운전 시뮬레이터", layout="wide")
st.title("🚗 실제 도시 기반 3D 입체 운전 시뮬레이터 (고도·지형 반영)")
st.caption("OpenStreetMap 데이터와 지형 고도(DEM 시뮬레이션)를 결합하여 입체적인 오르막/내리막, 강, 숲을 표현합니다.")

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
        headers={"User-Agent": "Student3DDrivingSimulator/2.0"}, timeout=25)
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
            x = requests.post(url, data=q, headers={"User-Agent": "Student3DDrivingSimulator/2.0"}, timeout=110)
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
        
        # 지형 고도(오르막/내리막) 연출을 위한 가상 지형 높이 함수 (중심에서 멀어질수록 완만한 기복 생성)
        def get_alt(x, z):
            # 노이즈 형태의 가상 고도 계산 (실제 Vworld DEM 연동 시 이 부분을 API 고도값으로 대체 가능)
            return (math.sin(x * 0.003) * math.cos(z * 0.003) * 35.0 + math.sin(x * 0.01) * 5.0) * t_scale

        if "highway" in tags:
            hw = tags.get("highway", "")
            try: lanes = int(str(tags.get("lanes", "0")).split(";")[0])
            except: lanes = 0
            
            if lanes >= 4 or (lanes == 0 and hw in ("motorway", "trunk", "motorway_link", "trunk_link")):
                try: width = float(str(tags.get("width", "")).replace("m", "").strip()) * .1
                except: width = max(1.4, lanes * 3.5 * .1 if lanes else 1.5)
                
                # 도로 경로상의 각 점에 고도 부여
                road_pts = [[p[0], get_alt(p[0], p[1]), p[1]] for p in pts]
                out["roads"].append({
                    "p": road_pts, 
                    "w": max(width, 1.2), 
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
    st.write(f"도로 {len(data['roads'])}개 · 건물 {len(data['buildings'])}개 · 물길 {len(data['water'])}개 · 숲 구역 {len(data['forests'])}개")
    st.caption("조작 방법: W/S 가속·후진, A/D 자유 조향 (오르막길과 내리막길의 입체 지형을 주행해보세요!)")
    
    html = r'''<!DOCTYPE html><html><head><meta charset="utf-8">
<style>body{margin:0;overflow:hidden;font-family:Arial}#game{height:700px;position:relative}
#hud,#help{position:absolute;z-index:4;background:#18212ddd;color:white;padding:10px;border-radius:8px}
#hud{top:10px;left:10px}#help{top:10px;right:10px;font-size:12px}
#buttons{position:absolute;bottom:12px;left:50%;transform:translateX(-50%);z-index:5;display:flex;gap:6px}
button{font-size:18px;padding:12px;background:#18212ddd;color:white;border:0;border-radius:8px;touch-action:none}</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.min.js"></script></head><body>
<div id="game"><div id="hud">속도 <span id="spd">0</span> km/h<br><span id="msg">입체 지형 도로 위에서 주행하세요.</span></div>
<div id="help">W/S: 가속·후진<br>A/D: 자유 조향<br>지형 고저차 반영됨</div>
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

// 입체 지형 메쉬 생성 (고저차가 있는 Plane)
const terrainGeo = new THREE.PlaneGeometry(4000, 4000, 64, 64);
terrainGeo.rotateX(-Math.PI / 2);
const posAttr = terrainGeo.attributes.position;
for(let i=0; i<posAttr.count; i++) {
    let px = posAttr.getX(i), pz = posAttr.getZ(i);
    // 지형 높이 공식 동기화
    let py = (Math.sin(px * 0.003) * Math.cos(pz * 0.003) * 35.0 + Math.sin(px * 0.01) * 5.0);
    posAttr.setY(i, py);
}
terrainGeo.computeVertexNormals();
const ground = new THREE.Mesh(terrainGeo, material(0x7a8c7a));
scene.add(ground);

// 3D 입체 도로 렌더링 (점과 점 사이를 연결하는 기울어진 세그먼트)
function road(points, width, mat) {
    for(let i = 0; i < points.length - 1; i++) {
        let a = points[i], b = points[i+1];
        let dx = b[0] - a[0], dz = b[2] - a[2], len = Math.hypot(dx, dz);
        if(len < .1) continue;
        
        let geo = new THREE.PlaneGeometry(width, len);
        geo.rotateX(-Math.PI / 2);
        let m = new THREE.Mesh(geo, mat);
        
        // 위치 및 경사각(오르막/내리막) 적용
        let mx = (a[0] + b[0]) / 2;
        let mz = (a[2] + b[2]) / 2;
        let my = (a[1] + b[1]) / 2 + 0.05;
        m.position.set(mx, my, mz);
        
        // 회전 설정 (Yaw 및 Pitch 경사 반영)
        m.rotation.y = Math.atan2(dx, dz);
        let dy = b[1] - a[1];
        let pitch = Math.atan2(dy, len);
        m.rotation.x = -Math.PI / 2 + pitch;
        
        scene.add(m);
    }
}

// 건물 렌더링 (고도 반영)
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

// 나무 및 숲 생성
function tree(x, y, z) {
    let t = new THREE.Mesh(new THREE.CylinderGeometry(.08, .12, .6, 5), trunkmat);
    t.position.set(x, y + 0.3, z);
    scene.add(t);
    let c = new THREE.Mesh(new THREE.ConeGeometry(.45, 1.0, 5), green);
    c.position.set(x, y + 1.0, z);
    scene.add(c);
}

// 데이터 반영 실행
for(const r of D.roads) {
    road(r.p, r.w, roadmat);
    // 도로 주변 가로수 및 숲 생성
    for(let i = 0; i < r.p.length - 1; i++) {
        let a = r.p[i], b = r.p[i+1];
        let dx = b[0] - a[0], dz = b[2] - a[2], len = Math.hypot(dx, dz);
        if(len < 12) continue;
        let nx = -dz / len, nz = dx / len;
        for(let t_step = 10; t_step < len; t_step += 25) {
            let cx = a[0] + dx * t_step / len, cz = a[2] + dz * t_step / len;
            let cy = (a[1] + b[1]) / 2;
            tree(cx + nx * (r.w/2 + 1.5), cy, cz + nz * (r.w/2 + 1.5));
        }
    }
}

for(const b of D.buildings) if(b.p.length >= 3) building(b.p, b.h, b.alt);
for(const w of D.water) road(w.p, 5, watermat);

// 차량 모델 생성
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

// 초기 위치 설정 (첫 번째 도로 위)
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

const target = new THREE.Vector3();
let last = performance.now();

// 지형 고도 함수와 동일한 계산을 자바스크립트 내에서도 수행
function getTerrainHeight(x, z) {
    return (Math.sin(x * 0.003) * Math.cos(z * 0.003) * 35.0 + Math.sin(x * 0.01) * 5.0);
}

function animate(now) {
    requestAnimationFrame(animate);
    let dt = Math.min((now - last) / 1000, .04);
    last = now;
    
    let f = keys.w || keys.arrowup || touch.f, b = keys.s || keys.arrowdown || touch.b;
    let L = keys.a || keys.arrowleft || touch.l, R = keys.d || keys.arrowright || touch.r;
    
    if(f) v = Math.min(18, v + 7 * dt);
    else if(b) v = Math.max(-5, v - 9 * dt);
    else v *= Math.pow(.985, dt * 60);
    
    let steering = (R ? 1 : 0) - (L ? 1 : 0);
    yaw += steering * v * .055 * dt;
    car.rotation.y = yaw;
    
    let nx = car.position.x + Math.sin(yaw) * v * dt;
    let nz = car.position.z + Math.cos(yaw) * v * dt;
    
    // 이동 위치의 고도를 실시간 반영하여 오르막/내리막 구현
    let ny = getTerrainHeight(nx, nz) + 0.3;
    
    car.position.x = nx;
    car.position.z = nz;
    car.position.y = ny;
    
    msg.textContent = '입체 지형 주행 중 (오르막/내리막 반영)';
    
    // 카메라 추적
    camera.position.lerp(new THREE.Vector3(car.position.x - Math.sin(yaw) * 10, car.position.y + 5, car.position.z - Math.cos(yaw) * 10), .1);
    target.set(car.position.x, car.position.y + 1, car.position.z);
    camera.lookAt(target);
    
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
    st.info("왼쪽 사이드바에서 도시와 주소를 입력하고 **'도시 불러오기'** 버튼을 누르세요. (예: 서울특별시 종로구, 부산광역시 해운대구)")
