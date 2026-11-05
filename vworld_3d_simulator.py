import streamlit as st
import streamlit.components.v1 as components
import requests, math, json

st.set_page_config(page_title="실제 도시 3D 운전 시뮬레이터", layout="wide")
st.title("🚗 실제 도시 기반 3D 운전 시뮬레이터 (1/4 축척 & 자유 시점)")
st.caption("vworld_3d_simulator.py 파일용 통합 완성본 코드입니다. 마우스 드래그 시점 조작과 자유 주행이 가능합니다.")

place = st.sidebar.text_input("도시/주소 입력", "서울특별시 강남구")
radius = st.sidebar.select_slider("지도 범위 반경", options=[500, 750, 1000, 1500, 2000], value=1000)
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
    # 모든 도로 데이터와 건물이 확실하게 수집되도록 쿼리 확장
    q = f'''[out:json][timeout:90];(
    way["highway"]({s},{w},{n},{e});
    way["building"]({s},{w},{n},{e});
    way["waterway"~"river|canal"]({s},{w},{n},{e});
    way["natural"="water"]({s},{w},{n},{e});
    );out body geom;'''
    err = None
    for url in ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]:
        try:
            x = requests.post(url, data=q, headers={"User-Agent": "Student3DDrivingSimulator/2.0"}, timeout=110)
            x.raise_for_status()
            return x.json()
        except Exception as ex: err = ex
    raise RuntimeError(f"OSM 요청 실패: {err}")

def convert(data, lat, lon):
    out = {"roads": [], "buildings": [], "water": []}
    fx = 111320 * math.cos(math.radians(lat)); fz = 111320
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        g = el.get("geometry", [])
        if len(g) < 2: continue
        
        # 1/4 축척 적용 (0.25배)
        pts = [[(p["lon"] - lon) * fx * .25, -(p["lat"] - lat) * fz * .25] for p in g]
        
        if "highway" in tags:
            hw = tags.get("highway", "")
            try: lanes = int(str(tags.get("lanes", "0")).split(";")[0])
            except: lanes = 0
            try: width = float(str(tags.get("width", "")).replace("m", "").strip()) * .25
            except: width = max(2.5, (lanes if lanes > 0 else 2) * 2.0 * .25)
            out["roads"].append({"p": pts, "w": max(width, 2.5), "bridge": tags.get("bridge") == "yes", "name": tags.get("name", hw)})
        elif "building" in tags and len(pts) >= 3:
            try: h = float(str(tags.get("height", "25")).replace("m", "").strip()) * .25
            except: h = 5.0
            out["buildings"].append({"p": pts, "h": max(4.0, h)})
        elif "waterway" in tags or "natural" in tags:
            out["water"].append({"p": pts})
    return out

if "citydata" not in st.session_state: st.session_state.citydata = None
if load:
    try:
        with st.spinner("실제 지도 데이터를 분석하는 중..."):
            lat, lon, name = geocode(place)
            raw = get_osm(lat, lon, radius)
            st.session_state.citydata = convert(raw, lat, lon)
            st.session_state.cityname = name
    except Exception as e: st.error(str(e))

if st.session_state.citydata:
    data = st.session_state.citydata
    st.success(st.session_state.cityname)
    st.write(f"도로 {len(data['roads'])}개 · 건물 {len(data['buildings'])}개 · 물길 {len(data['water'])}개")
    st.caption("조작: W/S 가속·후진, A/D 조향 | 🖱️ 마우스 클릭+드래그: 시점 자유 회전 | 휠: 확대/축소 | 지도 어디든 자유 주행")
    
    html = r'''<!DOCTYPE html><html><head><meta charset="utf-8">
<style>body{margin:0;overflow:hidden;font-family:Arial}#game{height:700px;position:relative}
#hud,#help{position:absolute;z-index:4;background:#18212ddd;color:white;padding:10px;border-radius:8px}
#hud{top:10px;left:10px}#help{top:10px;right:10px;font-size:12px}
#buttons{position:absolute;bottom:12px;left:50%;transform:translateX(-50%);z-index:5;display:flex;gap:6px}
button{font-size:18px;padding:12px;background:#18212ddd;color:white;border:0;border-radius:8px;touch-action:none}</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.min.js"></script></head><body>
<div id="game"><div id="hud">속도 <span id="spd">0</span> km/h<br><span id="msg">자유 주행 모드</span></div>
<div id="help">W/S: 가속·후진 | A/D: 조향<br>🖱️ 마우스 드래그로 시점 회전</div>
<div id="buttons"><button id="l">◀</button><button id="f">▲</button><button id="b">▼</button><button id="r">▶</button></div></div>
<script>
const D = __DATA__; const game = document.getElementById('game'), msg = document.getElementById('msg');
const scene = new THREE.Scene(); scene.background = new THREE.Color(0xcbd2d6); scene.fog = new THREE.Fog(0xcbd2d6, 300, 1000);
const camera = new THREE.PerspectiveCamera(65, game.clientWidth / game.clientHeight, .1, 3000);
const renderer = new THREE.WebGLRenderer({antialias: true, powerPreference: 'low-power'});
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.2)); renderer.setSize(game.clientWidth, game.clientHeight); game.insertBefore(renderer.domElement, game.firstChild);

scene.add(new THREE.HemisphereLight(0xffffff, 0x777777, 2)); const sun = new THREE.DirectionalLight(0xffffff, 1.2); sun.position.set(200, 400, 200); scene.add(sun);
const material = c => new THREE.MeshLambertMaterial({color: c});
const gray = material(0x858585), roadmat = material(0x3a3a3a), watermat = material(0x6c8997), green = material(0x687568), trunkmat = material(0x554c43);
const ground = new THREE.Mesh(new THREE.PlaneGeometry(8000, 8000), material(0x9b9f98)); ground.rotation.x = -Math.PI / 2; ground.position.y = -.2; scene.add(ground);

function road(points, width, mat, y = .05) {
    for(let i = 0; i < points.length - 1; i++) {
        let a = points[i], b = points[i+1], dx = b[0] - a[0], dz = b[1] - a[1], len = Math.hypot(dx, dz);
        if(len < .1) continue;
        let m = new THREE.Mesh(new THREE.PlaneGeometry(width, len), mat);
        m.rotation.x = -Math.PI / 2; m.rotation.z = Math.atan2(dx, dz);
        m.position.set((a[0] + b[0]) / 2, y, (a[1] + b[1]) / 2); scene.add(m);
    }
}
function building(p, h) {
    const s = new THREE.Shape(); s.moveTo(p[0][0], p[0][1]);
    for(let i = 1; i < p.length; i++) s.lineTo(p[i][0], p[i][1]); s.closePath();
    const g = new THREE.ExtrudeGeometry(s, {depth: h, bevelEnabled: false}); g.rotateX(-Math.PI / 2); scene.add(new THREE.Mesh(g, gray));
}
function tree(x, z) {
    let t = new THREE.Mesh(new THREE.CylinderGeometry(.1, .15, .8, 5), trunkmat); t.position.set(x, .4, z); scene.add(t);
    let c = new THREE.Mesh(new THREE.ConeGeometry(.6, 1.2, 5), green); c.position.set(x, 1.3, z); scene.add(c);
}

for(const r of D.roads) {
    road(r.p, r.w, roadmat, r.bridge ? .2 : .05);
    for(let i = 0; i < r.p.length - 1; i++) {
        let a = r.p[i], b = r.p[i+1], dx = b[0] - a[0], dz = b[1] - a[1], len = Math.hypot(dx, dz);
        if(len < 12) continue;
        let nx = -dz / len, nz = dx / len;
        for(let t = 15; t < len; t += 30) {
            let x = a[0] + dx * t / len, z = a[1] + dz * t / len;
            tree(x + nx * (r.w / 2 + 1.5), z + nz * (r.w / 2 + 1.5));
            tree(x - nx * (r.w / 2 + 1.5), z - nz * (r.w / 2 + 1.5));
        }
    }
}
for(const b of D.buildings) if(b.p.length >= 3) building(b.p, b.h);
for(const w of D.water) road(w.p, 10, watermat, 0);

const car = new THREE.Group(); scene.add(car);
const body = new THREE.Mesh(new THREE.BoxGeometry(2.0, .8, 4), material(0x9a3535)); body.position.y = .7; car.add(body);
const cabin = new THREE.Mesh(new THREE.BoxGeometry(1.4, .6, 1.8), material(0x777f83)); cabin.position.set(0, 1.3, -.2); car.add(cabin);
for(let x of [-1.0, 1.0]) for(let z of [-1.3, 1.3]) {
    let w = new THREE.Mesh(new THREE.BoxGeometry(.3, .5, .6), material(0x222222)); w.position.set(x, .35, z); car.add(w);
}

let start = D.roads.find(r => r.p.length > 1)?.p[Math.floor((D.roads.find(r => r.p.length > 1).p.length) / 2)] || [0, 0];
car.position.set(start[0], 0, start[1]);
let yaw = 0, v = 0, keys = {}, touch = {f: false, b: false, l: false, r: false};

window.addEventListener('keydown', e => keys[e.key.toLowerCase()] = true);
window.addEventListener('keyup', e => keys[e.key.toLowerCase()] = false);
function bind(id, k) {
    let el = document.getElementById(id);
    el.onpointerdown = e => { e.preventDefault(); touch[k] = true; };
    ['pointerup', 'pointercancel', 'pointerleave'].forEach(ev => el.addEventListener(ev, () => touch[k] = false));
}
bind('f', 'f'); bind('b', 'b'); bind('l', 'l'); bind('r', 'r');

// 마우스 드래그 시점 조작 이벤트
let camAngleX = 0.6, camAngleY = 0, camDist = 35;
let isDragging = false, prevMousePos = {x: 0, y: 0};

window.addEventListener('mousedown', e => { isDragging = true; prevMousePos = {x: e.clientX, y: e.clientY}; });
window.addEventListener('mouseup', () => { isDragging = false; });
window.addEventListener('mousemove', e => {
    if(isDragging) {
        let dx = e.clientX - prevMousePos.x;
        let dy = e.clientY - prevMousePos.y;
        camAngleY -= dx * 0.005;
        camAngleX = Math.max(0.1, Math.min(1.5, camAngleX - dy * 0.005));
        prevMousePos = {x: e.clientX, y: e.clientY};
    }
});
window.addEventListener('wheel', e => {
    camDist = Math.max(10, Math.min(150, camDist + e.deltaY * 0.05));
});

const target = new THREE.Vector3(); let last = performance.now();
function animate(now) {
    requestAnimationFrame(animate);
    let dt = Math.min((now - last) / 1000, .04); last = now;
    let f = keys.w || keys.arrowup || touch.f, b = keys.s || keys.arrowdown || touch.b;
    let L = keys.a || keys.arrowleft || touch.l, R = keys.d || keys.arrowright || touch.r;
    
    if(f) v = Math.min(20, v + 7 * dt);
    else if(b) v = Math.max(-6, v - 9 * dt);
    else v *= Math.pow(.985, dt * 60);
    
    let steering = (R ? 1 : 0) - (L ? 1 : 0);
    yaw += steering * v * .05 * dt;
    car.rotation.y = yaw;
    
    let nx = car.position.x + Math.sin(yaw) * v * dt;
    let nz = car.position.z + Math.cos(yaw) * v * dt;
    
    // 도로 제한 없음 (지도 위 어디든 자유롭게 주행)
    car.position.x = nx;
    car.position.z = nz;
    msg.textContent = '자유 주행 중 (어디든 이동 가능)';
    
    if(!isDragging) {
        camAngleY = yaw + Math.PI; // 드래그 중이 아닐 때는 자동차 뒤쪽을 기본으로 따라감
    }
    
    let cx = car.position.x + Math.sin(camAngleY) * camDist * Math.sin(camAngleX);
    let cy = car.position.y + Math.cos(camAngleX) * camDist;
    let cz = car.position.z + Math.cos(camAngleY) * camDist * Math.sin(camAngleX);
    
    camera.position.set(cx, cy, cz);
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
    st.info("왼쪽에 도시/주소를 입력하고 ‘도시 불러오기’를 누르세요. 예: 서울 강남구 테헤란로, 부산 해운대구, 인천국제공항")
