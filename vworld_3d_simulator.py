import streamlit as st
import streamlit.components.v1 as components
import requests, math, json

st.set_page_config(page_title="실제 도시 3D 운전 시뮬레이터", layout="wide")
st.title("🚗 실제 도시 기반 3D 운전 시뮬레이터 (도로 위 건물 완전 차단)")
st.caption("도로를 침범하는 건물과 거추장스러운 펜스를 완전히 제거하여 오직 도로와 자동차만 남긴 클린 버전입니다.")

place = st.sidebar.text_input("도시/주소 입력", "서울특별시 강남구")
radius = st.sidebar.select_slider("지도 범위 반경 (미터)", options=[500, 1000, 1500, 2000], value=1000)
load = st.sidebar.button("도시 불러오기", type="primary")

@st.cache_data(ttl=3600)
def geocode(q):
    r = requests.get("https://nominatim.openstreetmap.org/search",
        params={"q": q, "format": "json", "limit": 1},
        headers={"User-Agent": "Student3DDrivingSimulator/8.0"}, timeout=25)
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
    way["highway"]({s},{w},{n},{e});
    way["building"]({s},{w},{n},{e});
    way["waterway"~"river|canal"]({s},{w},{n},{e});
    way["natural"="water"]({s},{w},{n},{e});
    );out body geom;'''
    err = None
    for url in ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]:
        try:
            x = requests.post(url, data=q, headers={"User-Agent": "Student3DDrivingSimulator/8.0"}, timeout=110)
            x.raise_for_status()
            return x.json()
        except Exception as ex: err = ex
    raise RuntimeError(f"OSM 요청 실패: {err}")

def convert(data, lat, lon):
    out = {"roads": [], "buildings": [], "water": []}
    fx = 111320 * math.cos(math.radians(lat))
    fz = 111320
    
    road_segments = []
    
    # 1단계: 도로 데이터를 먼저 수집하여 기준 영역 설정 (광폭 도로 적용)
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        g = el.get("geometry", [])
        if len(g) < 2: continue
        pts = [[(p["lon"] - lon) * fx, -(p["lat"] - lat) * fz] for p in g]
        
        if "highway" in tags:
            hw = tags.get("highway", "")
            try: lanes = int(str(tags.get("lanes", "2")).split(";")[0])
            except: lanes = 2
            width = max(18.0, lanes * 9.0)  # 훨씬 넓어진 쾌적한 광폭 도로
                
            road_segments.append({"p": pts, "w": width})
            out["roads"].append({
                "p": pts, 
                "w": width, 
                "bridge": tags.get("bridge") == "yes", 
                "name": tags.get("name", hw)
            })

    # 2단계: 건물의 어떤 꼭짓점이라도 도로 근처에 있으면 무조건 삭제하는 강력한 필터
    def is_too_close_to_road(pts, road_segs):
        for p in pts:
            px, pz = p[0], p[1]
            for r in road_segs:
                # 도로 폭 + 넉넉한 여유 버퍼(10m) 내에 들어오는 건물은 전부 차단
                r_hw = (r["w"] / 2.0) + 10.0 
                rp = r["p"]
                for i in range(len(rp) - 1):
                    ra = rp[i]; rb = rp[i+1]
                    rvx = rb[0] - ra[0]; rvz = rb[1] - ra[1]
                    rl2 = rvx*rvx + rvz*rvz
                    t = 0 if rl2 == 0 else max(0, min(1, ((px - ra[0])*rvx + (pz - ra[1])*rvz) / rl2))
                    cx = ra[0] + t * rvx; cz = ra[1] + t * rvz
                    if math.hypot(px - cx, pz - cz) < r_hw:
                        return True
        return False

    # 3단계: 도로 위나 주변을 침범하는 건물은 100% 완전 삭제
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        g = el.get("geometry", [])
        if len(g) < 2: continue
        pts = [[(p["lon"] - lon) * fx, -(p["lat"] - lat) * fz] for p in g]
        
        if "building" in tags and len(pts) >= 3:
            if is_too_close_to_road(pts, road_segments):
                continue # 도로 위나 침범하는 건물은 완전히 말소!
            
            try: h = float(str(tags.get("height", "")).replace("m", "").strip())
            except: 
                try: levels = float(str(tags.get("building:levels", "4")).split(";")[0]); h = levels * 3.5
                except: h = 14.0
            out["buildings"].append({"p": pts, "h": max(5.0, h)})
        elif "waterway" in tags or "natural" in tags:
            out["water"].append({"p": pts})
            
    return out

if "citydata" not in st.session_state: st.session_state.citydata = None
if load:
    try:
        with st.spinner("도로 위 침범 건물을 완벽히 제거하고 지도를 정돈하는 중..."):
            lat, lon, name = geocode(place)
            raw = get_osm(lat, lon, radius)
            st.session_state.citydata = convert(raw, lat, lon)
            st.session_state.cityname = name
    except Exception as e: st.error(str(e))

if st.session_state.citydata:
    data = st.session_state.citydata
    st.success(f"📍 {st.session_state.cityname}")
    st.write(f"광폭 도로 {len(data['roads'])}개 · 클린 건물 {len(data['buildings'])}개 (펜스 없음)")
    st.caption("조작 방법: W/S 가속·후진, A/D 조향(반전됨) | 🖱️ 마우스 드래그: 시점 회전 | 휠: 확대/축소")
    
    html = r'''<!DOCTYPE html><html><head><meta charset="utf-8">
<style>body{margin:0;overflow:hidden;font-family:Arial}#game{height:750px;position:relative}
#hud,#help{position:absolute;z-index:4;background:#18212ddd;color:white;padding:10px;border-radius:8px}
#hud{top:10px;left:10px}#help{top:10px;right:10px;font-size:12px;text-align:right;}
#buttons{position:absolute;bottom:12px;left:50%;transform:translateX(-50%);z-index:5;display:flex;gap:6px}
button{font-size:18px;padding:12px;background:#18212ddd;color:white;border:0;border-radius:8px;touch-action:none;cursor:pointer;}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.min.js"></script></head><body>
<div id="game">
<div id="hud">속도 <span id="spd">0</span> km/h<br><span id="msg">도로 위 클린 주행 모드</span></div>
<div id="help">W/S: 가속·후진 | A/D: 조향 (반전됨)<br>🖱️ 마우스 드래그로 시점 회전</div>
<div id="buttons"><button id="l">◀</button><button id="f">▲</button><button id="b">▼</button><button id="r">▶</button></div></div>
<script>
const D = __DATA__; 
const game = document.getElementById('game'), msg = document.getElementById('msg');
const scene = new THREE.Scene(); 
scene.background = new THREE.Color(0xb8c6d1); 
scene.fog = new THREE.Fog(0xb8c6d1, 500, 3000);

const camera = new THREE.PerspectiveCamera(60, game.clientWidth / game.clientHeight, 1, 10000);
const renderer = new THREE.WebGLRenderer({antialias: true, powerPreference: 'low-power'});
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5)); 
renderer.setSize(game.clientWidth, game.clientHeight); 
game.insertBefore(renderer.domElement, game.firstChild);

scene.add(new THREE.HemisphereLight(0xffffff, 0x666666, 2.0)); 
const sun = new THREE.DirectionalLight(0xffffff, 1.2); 
sun.position.set(500, 1000, 500); 
scene.add(sun);

const material = c => new THREE.MeshLambertMaterial({color: c});
const gray = material(0x8a95a5), roadmat = material(0x2a2a2a), watermat = material(0x5a829e);

const ground = new THREE.Mesh(new THREE.PlaneGeometry(10000, 10000), material(0x8c9c8c)); 
ground.rotation.x = -Math.PI / 2; 
ground.position.y = -0.2; 
ground.renderOrder = 0;
scene.add(ground);

function building(p, h) {
    const s = new THREE.Shape(); 
    s.moveTo(p[0][0], p[0][1]);
    for(let i = 1; i < p.length; i++) s.lineTo(p[i][0], p[i][1]); 
    s.closePath();
    const g = new THREE.ExtrudeGeometry(s, {depth: h, bevelEnabled: false}); 
    g.rotateX(-Math.PI / 2); 
    let mesh = new THREE.Mesh(g, gray);
    mesh.position.y = 0;
    mesh.renderOrder = 1;
    scene.add(mesh);
}

function road(points, width, mat, y = 0.5) {
    for(let i = 0; i < points.length - 1; i++) {
        let a = points[i], b = points[i+1], dx = b[0] - a[0], dz = b[1] - a[1], len = Math.hypot(dx, dz);
        if(len < 0.5) continue;
        let m = new THREE.Mesh(new THREE.PlaneGeometry(width, len), mat);
        m.rotation.x = -Math.PI / 2; 
        m.rotation.z = Math.atan2(dx, dz);
        m.position.set((a[0] + b[0]) / 2, y, (a[1] + b[1]) / 2); 
        m.renderOrder = 2;
        scene.add(m);
    }
}

// 1. 도로 위 침범 건물이 완전히 제거된 건물 생성
for(const b of D.buildings) {
    if(b.p.length >= 3) building(b.p, b.h);
}

// 2. 광폭 도로 생성
for(const r of D.roads) {
    road(r.p, r.w, roadmat, r.bridge ? 2.0 : 0.6);
}

for(const w of D.water) {
    road(w.p, 25, watermat, 0.3);
}

// 자동차 모델
const car = new THREE.Group(); 
scene.add(car);
const body = new THREE.Mesh(new THREE.BoxGeometry(2.0, 0.8, 4.5), material(0xb83b3b)); 
body.position.y = 0.8; 
car.add(body);
const cabin = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.7, 2.2), material(0x777f83)); 
cabin.position.set(0, 1.5, -0.3); 
car.add(cabin);
for(let x of [-1.0, 1.0]) for(let z of [-1.5, 1.5]) {
    let wheel = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.5, 0.8), material(0x222222)); 
    wheel.position.set(x, 0.45, z); 
    car.add(wheel);
}

let start = D.roads.find(r => r.p.length > 1)?.p[Math.floor((D.roads.find(r => r.p.length > 1).p.length) / 2)] || [0, 0];
car.position.set(start[0], 0.6, start[1]);

let yaw = 0, v = 0, keys = {}, touch = {f: false, b: false, l: false, r: false};

window.addEventListener('keydown', e => keys[e.key.toLowerCase()] = true);
window.addEventListener('keyup', e => keys[e.key.toLowerCase()] = false);
function bind(id, k) {
    let el = document.getElementById(id);
    el.onpointerdown = e => { e.preventDefault(); touch[k] = true; };
    ['pointerup', 'pointercancel', 'pointerleave'].forEach(ev => el.addEventListener(ev, () => touch[k] = false));
}
bind('f', 'f'); bind('b', 'b'); bind('l', 'l'); bind('r', 'r');

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
    camDist = Math.max(5, Math.min(400, camDist + e.deltaY * 0.1));
});

const target = new THREE.Vector3(); 
let last = performance.now();

function animate(now) {
    requestAnimationFrame(animate);
    let dt = Math.min((now - last) / 1000, .04); 
    last = now;
    
    let f = keys.w || keys.arrowup || touch.f, b = keys.s || keys.arrowdown || touch.b;
    let L = keys.a || keys.arrowleft || touch.l, R = keys.d || keys.arrowright || touch.r;
    
    if(f) v = Math.min(30, v + 12 * dt);
    else if(b) v = Math.max(-10, v - 15 * dt);
    else v *= Math.pow(0.98, dt * 60);
    
    let steering = (L ? 1 : 0) - (R ? 1 : 0);
    yaw += steering * v * 0.03 * dt;
    car.rotation.y = yaw;
    
    let nx = car.position.x + Math.sin(yaw) * v * dt;
    let nz = car.position.z + Math.cos(yaw) * v * dt;
    
    car.position.x = nx;
    car.position.z = nz;
    msg.textContent = '클린 도로 주행 중';
    
    if(!isDragging) {
        camAngleY = yaw + Math.PI;
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
window.ensureSize = () => {
    camera.aspect = game.clientWidth / game.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(game.clientWidth, game.clientHeight);
};
window.addEventListener('resize', window.ensureSize);
</script></body></html>'''
    
    html = html.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    components.html(html, height=780, scrolling=False)
else:
    st.info("왼쪽에 도시/주소를 입력하고 **'도시 불러오기'** 버튼을 누르세요. 예: 서울 강남구 테헤란로, 부산 해운대구")
