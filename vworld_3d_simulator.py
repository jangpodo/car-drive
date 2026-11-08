import streamlit as st
import streamlit.components.v1 as components
import requests
import math
import json

st.set_page_config(page_title="3D 도시 운전 시뮬레이터", layout="wide")
st.title("🚗 3D 도시 운전 시뮬레이터")
st.caption("실제 지도 도로·건물 데이터를 바탕으로 구현된 3D 운전 시뮬레이터입니다.")

with st.sidebar:
    place = st.text_input("도시 / 주소 입력", "서울특별시 종로구")
    
    st.markdown("---")
    st.markdown("📌 **추천 도시 입력 예시**")
    st.markdown("- **유적지/문화재 중심:** 서울 종로구, 경주시")
    st.markdown("- **특별시/광역시:** 서울 강남구, 부산 해운대구")
    st.markdown("- **경기도:** 수원시 팔달구, 성남시 분당구")
    st.markdown("- **강원도:** 강릉시 중앙동, 춘천시")
    st.markdown("- **충청도:** 천안시 서북구, 청주시 흥덕구")
    st.markdown("- **전라도:** 전주시 완산구, 여수시")
    st.markdown("- **경상도:** 포항시 북구")
    st.markdown("---")

    radius = st.select_slider(
        "지도 범위 반경",
        options=[300, 400, 600, 800, 1000, 1500],
        value=600,
        format_func=lambda x: f"{x} m"
    )
    use_elevation = st.checkbox("SRTM 실제 지형 고도 적용 (30m급)", value=True)
    lod_distance = st.select_slider("거리 기반 상세 렌더링", options=[250, 400, 600, 900], value=400,
                                   format_func=lambda x: f"상세 표시 {x}m 이내")
    load = st.button("도시 불러오기", type="primary")
    st.caption("차량 크기: 약 4.5m × 1.8m (실제 승용차 비율)")

@st.cache_data(ttl=3600, show_spinner=False)
def geocode(q):
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": q, "format": "json", "limit": 1},
        headers={"User-Agent": "Student3DDrivingSimulator/29.0 (educational project)"},
        timeout=(5, 15)
    )
    response.raise_for_status()
    items = response.json()
    if not items:
        raise ValueError("위치를 찾지 못했습니다. 도시명이나 주소를 더 구체적으로 입력해 주세요.")
    item = items[0]
    return float(item["lat"]), float(item["lon"]), item.get("display_name", q)

@st.cache_data(ttl=21600, show_spinner=False)
def get_osm(lat, lon, radius_m):
    """
    OSM 데이터를 가져온다.
    - 위도/경도 경계 계산을 분리해 동서 범위 오류를 방지
    - 공개 Overpass 서버 여러 곳을 순차적으로 시도
    - 각 서버 응답 대기 시간을 제한해 2분 이상 멈추는 현상을 줄임
    """
    dlat = radius_m / 111320
    dlon = radius_m / (111320 * max(math.cos(math.radians(lat)), 0.2))
    south, west, north, east = lat-dlat, lon-dlon, lat+dlat, lon+dlon

    # [timeout]은 Overpass 서버 내부 쿼리 제한, requests timeout은 HTTP 응답 대기 제한이다.
    query = f"""
    [out:json][timeout:25][maxsize:536870912];
    (
      way["highway"~"motorway|trunk|primary|secondary|tertiary|residential|unclassified|living_street|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link"]({south},{west},{north},{east});
      way["building"]({south},{west},{north},{east});
      way["amenity"]({south},{west},{north},{east});
      way["shop"]({south},{west},{north},{east});
      way["tourism"]({south},{west},{north},{east});
      way["leisure"]({south},{west},{north},{east});
      way["historic"]({south},{west},{north},{east});
      way["waterway"~"river|canal"]({south},{west},{north},{east});
      way["natural"="water"]({south},{west},{north},{east});
    );
    out body geom;
    """

    # Kumi는 Private.coffee가 운영하는 인스턴스로 이전되었으므로 새 주소를 사용한다.
    endpoints = [
        "https://overpass.private.coffee/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        "https://overpass-api.de/api/interpreter",
    ]
    errors = []
    headers = {
        "User-Agent": "Student3DDrivingSimulator/29.0 (educational project)",
        "Accept": "application/json",
    }

    for endpoint in endpoints:
        try:
            response = requests.post(
                endpoint,
                data={"data": query},
                headers=headers,
                timeout=(6, 28),  # 연결 6초, 응답 대기 28초
            )
            if response.status_code in (429, 502, 503, 504):
                errors.append(f"{endpoint.split('/')[2]}: HTTP {response.status_code}")
                continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or "elements" not in payload:
                errors.append(f"{endpoint.split('/')[2]}: 응답 데이터 형식 오류")
                continue
            return payload
        except requests.exceptions.Timeout:
            errors.append(f"{endpoint.split('/')[2]}: 응답 시간 초과")
        except requests.exceptions.RequestException as exc:
            errors.append(f"{endpoint.split('/')[2]}: {type(exc).__name__}")
        except ValueError:
            errors.append(f"{endpoint.split('/')[2]}: JSON 응답 오류")

    detail = " / ".join(errors[-3:])
    raise RuntimeError(
        "OSM 서버들이 응답하지 않았습니다. 잠시 후 반경을 줄여 다시 시도해 주세요. "
        f"시도 결과: {detail}"
    )



@st.cache_data(ttl=86400, show_spinner=False)
def query_elevation_batch(locations):
    """OpenTopoData SRTM 30m elevation API. Public endpoint: max 100 points/request."""
    if not locations:
        return []
    url = "https://api.opentopodata.org/v1/srtm30m"
    results = []
    for start in range(0, len(locations), 100):
        chunk = locations[start:start+100]
        location_string = "|".join(f"{lat:.6f},{lon:.6f}" for lat, lon in chunk)
        response = requests.get(
            url,
            params={"locations": location_string, "interpolation": "bilinear"},
            headers={"User-Agent": "Student3DDrivingSimulator/28.0"},
            timeout=30
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "OK":
            raise RuntimeError(payload.get("error", "고도 API 응답 오류"))
        results.extend([item.get("elevation") for item in payload.get("results", [])])
        if start + 100 < len(locations):
            import time
            time.sleep(1.1)  # 공개 API의 요청 빈도 제한을 고려
    return results


def add_terrain_elevation(osm, center_lat, center_lon, max_samples=200):
    """
    도로를 따라 고도 표본을 최대 max_samples개 추출하고 SRTM 30m 고도를
    도로 노드에 보간한다. DEM은 약 30m 격자이므로 작은 언덕/도로 경사로는
    정확히 표현되지 않을 수 있다.
    """
    elements = osm.get("elements", [])
    road_elements = [
        el for el in elements
        if "highway" in el.get("tags", {})
        and len(el.get("geometry", [])) >= 2
        and el.get("tags", {}).get("highway") not in
        ("footway", "path", "steps", "cycleway", "pedestrian", "track", "bridleway")
    ]
    total_length = 0.0
    for el in road_elements:
        g = el["geometry"]
        for a, b in zip(g[:-1], g[1:]):
            total_length += math.hypot(
                (b["lon"]-a["lon"])*111320*math.cos(math.radians(center_lat)),
                (b["lat"]-a["lat"])*111320
            )
    if total_length <= 0:
        return osm, None, "도로 길이 계산 실패"

    # 도로 전체에서 일정한 간격으로 표본을 선택. API 요청을 과도하게 늘리지 않는다.
    interval = max(45.0, total_length / max_samples)
    sample_records = []  # (road element index, distance along road, lat, lon)
    for road_idx, el in enumerate(road_elements):
        g = el["geometry"]
        cum = 0.0
        next_sample = 0.0
        for a, b in zip(g[:-1], g[1:]):
            seg_len = math.hypot(
                (b["lon"]-a["lon"])*111320*math.cos(math.radians(center_lat)),
                (b["lat"]-a["lat"])*111320
            )
            if seg_len < 0.01:
                continue
            while next_sample <= cum + seg_len:
                t = max(0.0, min(1.0, (next_sample-cum)/seg_len))
                sample_records.append((
                    road_idx, next_sample,
                    a["lat"] + (b["lat"]-a["lat"])*t,
                    a["lon"] + (b["lon"]-a["lon"])*t
                ))
                next_sample += interval
            cum += seg_len
        # include road endpoint to avoid extrapolation at the end
        sample_records.append((road_idx, cum, g[-1]["lat"], g[-1]["lon"]))

    # Hard cap safeguards against huge maps
    if len(sample_records) > max_samples:
        stride = max(1, math.ceil(len(sample_records) / max_samples))
        sample_records = sample_records[::stride]

    coords = [(rec[2], rec[3]) for rec in sample_records]
    elevations = query_elevation_batch(coords)
    by_road = {}
    for rec, elev in zip(sample_records, elevations):
        if elev is not None:
            by_road.setdefault(rec[0], []).append((rec[1], float(elev)))

    # Interpolate elevation along each OSM road, then attach it as tags for conversion.
    for road_idx, el in enumerate(road_elements):
        samples = sorted(by_road.get(road_idx, []))
        g = el["geometry"]
        if not samples:
            for p in g:
                p["_elevation"] = None
            continue
        cum = 0.0
        for p_idx, p in enumerate(g):
            if p_idx > 0:
                prev = g[p_idx-1]
                cum += math.hypot(
                    (p["lon"]-prev["lon"])*111320*math.cos(math.radians(center_lat)),
                    (p["lat"]-prev["lat"])*111320
                )
            left = samples[0]
            right = samples[-1]
            for s in range(len(samples)-1):
                if samples[s][0] <= cum <= samples[s+1][0]:
                    left, right = samples[s], samples[s+1]
                    break
            if right[0] == left[0]:
                p["_elevation"] = left[1]
            else:
                t = max(0.0, min(1.0, (cum-left[0])/(right[0]-left[0])))
                p["_elevation"] = left[1] + (right[1]-left[1])*t

    # Center elevation for local vertical origin
    # Use sampled road elevations as local vertical datum (avoids one extra API call).
    valid = [e for vals in by_road.values() for _, e in vals]
    center_elev = sum(valid)/len(valid) if valid else 0.0

    return osm, float(center_elev), f"SRTM 30m 표본 {len(coords)}개"


def road_width_m(tags):
    highway = tags.get("highway", "")
    try:
        lanes = int(str(tags.get("lanes", "")).split(";")[0])
    except (ValueError, TypeError):
        lanes = 0

    try:
        width = float(str(tags.get("width", "")).replace("m", "").strip())
        if width > 0:
            return min(max(width, 3.0), 45.0)
    except (ValueError, TypeError):
        pass

    if lanes > 0:
        return min(max(lanes * 3.5 + 1.0, 5.0), 45.0)

    widths = {
        "motorway": 26.0, "trunk": 20.0, "primary": 14.0,
        "secondary": 11.0, "tertiary": 9.0,
        "motorway_link": 10.0, "trunk_link": 9.0,
        "primary_link": 8.5, "secondary_link": 7.5,
        "tertiary_link": 7.0, "residential": 6.0,
        "unclassified": 6.0, "living_street": 5.5
    }
    return widths.get(highway, 6.0)

def get_category_and_color(tags):
    name = tags.get("name", "").strip()
    if not name or name.isdigit():
        return None, None

    if "주차장" in name or "parking" in tags.get("amenity", ""):
        return None, None
    if "아파트" in name or "교회" in name or "빌딩" in name or "동" in name:
        if not ("백화점" in name or "쇼핑몰" in name or "시청" in name or "문화재" in name):
            return None, None

    amenity = tags.get("amenity", "")
    shop = tags.get("shop", "")
    tourism = tags.get("tourism", "")
    leisure = tags.get("leisure", "")
    historic = tags.get("historic", "")

    # 1. 음식점·카페 (주황색 #ff9800)
    if amenity in ["restaurant", "cafe", "fast_food", "pub", "bar"] or any(k in name for k in ["음식점", "식당", "카페", "커피", "맛집"]):
        return name, "#ff9800"

    # 2. 편의점 (푸른색 #2196f3)
    if shop in ["convenience"] or amenity in ["convenience"] or "편의점" in name:
        return name, "#2196f3"

    # 3. 백화점·쇼핑몰·시장 (빨간색 #e53935)
    if shop in ["mall", "department_store", "supermarket"] or amenity in ["marketplace"] or any(k in name for k in ["백화점", "쇼핑몰", "시장", "마트"]):
        return name, "#e53935"

    # 4. 공원·산·문화재/유적지 (초록색 #4caf50)
    if leisure in ["park", "garden"] or historic != "" or tourism in ["attraction", "viewpoint"] or any(k in name for k in ["공원", "산", "문화재", "유적", "궁", "왕릉"]):
        return name, "#4caf50"

    # 5. 나머지 주요 시설 (박물관, 시청, 법원, 도서관 등) -> 보라색 #9c27b0
    valid_others = ["library", "courthouse", "town_hall", "museum", "university", "college", "police", "fire_station"]
    if amenity in valid_others or tourism in ["museum", "gallery"] or any(k in name for k in ["박물관", "시청", "법원", "도서관", "구청", "주민센터"]):
        return name, "#9c27b0"

    return None, None

def convert_osm(osm, center_lat, center_lon, center_elevation=0.0):
    result = {"roads": [], "buildings": [], "water": []}
    meters_lon = 111320 * math.cos(math.radians(center_lat))
    meters_lat = 111320

    for element in osm.get("elements", []):
        tags = element.get("tags", {})
        geometry = element.get("geometry", [])
        if len(geometry) < 2:
            continue

        points = []
        for point in geometry:
            x = (float(point["lon"]) - center_lon) * meters_lon
            z = -(float(point["lat"]) - center_lat) * meters_lat
            raw_elev = point.get("_elevation")
            local_y = (float(raw_elev) - float(center_elevation)) if raw_elev is not None else 0.0
            points.append([x, z, local_y])

        elevations = [p.get("_elevation") for p in geometry]
        if "highway" in tags:
            highway = tags.get("highway", "")
            if highway in ("footway", "path", "steps", "cycleway", "pedestrian", "track", "bridleway"):
                continue
            result["roads"].append({
                "points": points,
                "width": road_width_m(tags),
                "highway": highway,
                "name": tags.get("name", highway),
                "bridge": tags.get("bridge") == "yes",
                "lanes": tags.get("lanes", ""),
                "elevations": elevations
            })

        elif len(points) >= 3 and any(k in tags for k in ["building", "amenity", "shop", "tourism", "leisure", "historic"]):
            try:
                height = float(str(tags.get("height", "")).replace("m", "").strip())
            except (ValueError, TypeError):
                try:
                    levels = float(str(tags.get("building:levels", "3")).split(";")[0])
                    height = levels * 3.2
                except (ValueError, TypeError):
                    height = 10.0
            
            cx = sum(p[0] for p in points) / len(points)
            cz = sum(p[1] for p in points) / len(points)
            
            landmark_name, pin_color = get_category_and_color(tags)

            result["buildings"].append({
                "points": points,
                "height": min(max(height, 3.0), 180.0),
                "name": landmark_name if landmark_name else "",
                "color": pin_color if pin_color else "",
                "cx": cx,
                "cz": cz
            })

        elif "waterway" in tags or "natural" in tags:
            result["water"].append({"points": points, "name": tags.get("name", "물길")})

    return result

if "city_data" not in st.session_state:
    st.session_state.city_data = None
if "city_label" not in st.session_state:
    st.session_state.city_label = ""

if load:
    try:
        with st.spinner("실제 도로와 건물 데이터를 가져오는 중입니다..."):
            lat, lon, label = geocode(place.strip())
            raw = get_osm(lat, lon, radius)
            elevation_note = "고도 데이터 사용 안 함"
            if use_elevation:
                try:
                    raw, center_elev, elevation_note = add_terrain_elevation(raw, lat, lon)
                except Exception as elev_error:
                    center_elev = 0.0
                    elevation_note = f"고도 API 실패(평지 대체): {elev_error}"
            else:
                center_elev = 0.0
            st.session_state.city_data = convert_osm(raw, lat, lon, center_elev or 0.0)
            st.session_state.city_data["center_elevation"] = center_elev or 0.0
            st.session_state.city_data["elevation_note"] = elevation_note
            st.session_state.city_data["lod_distance"] = lod_distance
            st.session_state.city_label = label
    except Exception as error:
        st.error(f"도시를 불러오지 못했습니다: {error}")

if st.session_state.city_data:
    data = st.session_state.city_data
    st.success(f"📍 {st.session_state.city_label}")
    st.caption(f"도로 {len(data['roads'])}개 · 건물 {len(data['buildings'])}개 · 물길 {len(data['water'])}개")
    st.caption(f"⛰️ {data.get('elevation_note', '고도 데이터 상태 확인 필요')} | 상세 렌더링 거리: {data.get('lod_distance', 400)}m")
    st.info("W/S 또는 ↑/↓: 가속·후진 | A/D 또는 ←/→: 조향 | 마우스 드래그: 카메라 회전 | 휠: 줌 | C: 카메라 추적/자유 모드")

    html = r"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
html,body{margin:0;padding:0;overflow:hidden;background:#bfc8ce;font-family:Arial,sans-serif}
#game{height:760px;width:100%;position:relative;overflow:hidden}
#hud,#help{position:absolute;z-index:10;background:rgba(20,28,36,.88);color:#fff;padding:10px 13px;border-radius:8px;line-height:1.55}
#hud{top:10px;left:10px;font-size:14px}
#help{top:10px;right:10px;font-size:12px;text-align:right;pointer-events:none}
#buttons{position:absolute;bottom:12px;left:50%;transform:translateX(-50%);z-index:10;display:flex;gap:6px}
button{font-size:18px;padding:12px 16px;background:#26313b;color:white;border:0;border-radius:8px;touch-action:none;cursor:pointer}
#camBtn{position:absolute;right:12px;bottom:12px;z-index:10;font-size:13px;padding:10px}
#game canvas{display:block;touch-action:none}

#markers-container {
  position: absolute;
  top: 0; left: 0; width: 100%; height: 100%;
  pointer-events: none;
  z-index: 15;
  overflow: hidden;
}
.map-pin {
  position: absolute;
  transform: translate(-50%, -100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  transition: transform 0.15s ease;
  pointer-events: auto;
  cursor: pointer;
}
.map-pin:hover {
  transform: translate(-50%, -100%) scale(1.15);
}
.pin-body {
  width: 32px;
  height: 42px;
  border-radius: 50% 50% 50% 0;
  transform: rotate(-45deg);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 8px rgba(0,0,0,0.35);
}
.pin-circle-hole {
  width: 14px;
  height: 14px;
  background: #ffffff;
  border-radius: 50%;
  transform: rotate(45deg);
}
.pin-label {
  margin-top: 5px;
  background: rgba(20, 28, 36, 0.9);
  color: #fff;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: bold;
  border-radius: 4px;
  white-space: nowrap;
  box-shadow: 0 2px 5px rgba(0,0,0,0.3);
  border: 1px solid rgba(255,255,255,0.2);
}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.min.js"></script>
</head><body><div id="game">
<div id="hud">속도: <span id="speed">0</span> km/h<br><span id="status">준비 중</span><br><span id="cameraLabel">카메라: 3인칭 추적</span></div>
<div id="help">W/S 또는 ↑/↓: 가속·후진<br>A/D 또는 ←/→: 조향<br>마우스 드래그: 카메라 회전<br>휠: 확대·축소<br>C: 추적/자유 카메라</div>
<div id="buttons"><button id="left">◀</button><button id="forward">▲</button><button id="back">▼</button><button id="right">▶</button></div>
<button id="camBtn">카메라 전환 (C)</button>
<div id="markers-container"></div>
</div>
<script>
const DATA=__DATA__;
const game=document.getElementById("game");
const statusEl=document.getElementById("status");
const speedEl=document.getElementById("speed");
const markersContainer=document.getElementById("markers-container");

if(!window.THREE){statusEl.textContent="Three.js 로딩 실패: CDN/인터넷 연결을 확인하세요.";throw new Error("Three.js missing");}

const scene=new THREE.Scene();
const lodObjects=[];
const LOD_DISTANCE=Number(DATA.lod_distance||400);
scene.background=new THREE.Color(0xb8c6d1);
scene.fog=new THREE.Fog(0xb8c6d1,450,2600);
const camera=new THREE.PerspectiveCamera(65,game.clientWidth/game.clientHeight,.1,12000);
const renderer=new THREE.WebGLRenderer({antialias:false,powerPreference:"low-power"});
renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.35));
renderer.setSize(game.clientWidth,game.clientHeight);
renderer.domElement.style.position="absolute";
renderer.domElement.style.inset="0";
renderer.domElement.style.touchAction="none";
game.insertBefore(renderer.domElement,game.firstChild);

scene.add(new THREE.HemisphereLight(0xffffff,0x777777,2.0));
const sun=new THREE.DirectionalLight(0xffffff,1.25);
sun.position.set(300,500,250);scene.add(sun);

const material=(color)=>new THREE.MeshLambertMaterial({color,side:THREE.DoubleSide});
const groundMat=material(0x7fa27f); 
const roadMat=material(0x343638);
const bridgeMat=material(0x42464a);
const waterMat=material(0x3a75c4); 
const markingMat=material(0xd8d6c9);
const treeMat=material(0x3e5e3b); 
const trunkMat=material(0x5c4938);
const grassMat=material(0x668f63);

const textureLoader = new THREE.TextureLoader();
const buildingTexture = textureLoader.load('https://threejs.org/examples/textures/brick_diffuse.jpg');
buildingTexture.wrapS = THREE.RepeatWrapping;
buildingTexture.wrapT = THREE.RepeatWrapping;
buildingTexture.repeat.set(1, 3);
const buildingMat = new THREE.MeshLambertMaterial({ map: buildingTexture });

const ground=new THREE.Mesh(new THREE.PlaneGeometry(20000,20000),groundMat);
ground.rotation.x=-Math.PI/2;
ground.position.y=-0.15;
scene.add(ground);

function addSceneryDetails(){
  for(let i=0; i<150; i++){
    let rx = (Math.random() - 0.5) * 1200;
    let rz = (Math.random() - 0.5) * 1200;
    const grass = new THREE.Mesh(new THREE.DodecahedronGeometry(0.8), grassMat);
    grass.position.set(rx, 0, rz);
    scene.add(grass);
  }
}
addSceneryDetails();

function roadQuadSloped(a, b, width, mat, yA, yB){
  const dx=b[0]-a[0], dz=b[1]-a[1], len=Math.hypot(dx,dz);
  if(len<.05)return;
  const nx=-dz/len, nz=dx/len, half=width/2;
  const p1=[a[0]+nx*half, a[1]+nz*half];
  const p2=[a[0]-nx*half, a[1]-nz*half];
  const p3=[b[0]-nx*half, b[1]-nz*half];
  const p4=[b[0]+nx*half, b[1]+nz*half];
  const vertices=new Float32Array([
    p1[0], yA, p1[1],  p2[0], yA, p2[1],  p3[0], yB, p3[1],
    p1[0], yA, p1[1],  p3[0], yB, p3[1],  p4[0], yB, p4[1]
  ]);
  const geo=new THREE.BufferGeometry();
  geo.setAttribute("position",new THREE.BufferAttribute(vertices,3));
  geo.computeVertexNormals();
  const mesh=new THREE.Mesh(geo,mat);
  scene.add(mesh);
  const cx=(a[0]+b[0])/2, cz=(a[1]+b[1])/2;
  lodObjects.push({mesh,x:cx,z:cz,type:"road"});
}

function lineSegmentSloped(a, b, width, color, yA, yB){
  const dx=b[0]-a[0], dz=b[1]-a[1], len=Math.hypot(dx,dz);
  if(len<.05)return;
  const nx=-dz/len, nz=dx/len, half=width/2;
  const v=new Float32Array([
    a[0]+nx*half, yA, a[1]+nz*half,
    a[0]-nx*half, yA, a[1]-nz*half,
    b[0]-nx*half, yB, b[1]-nz*half,
    a[0]+nx*half, yA, a[1]+nz*half,
    b[0]-nx*half, yB, b[1]-nz*half,
    b[0]+nx*half, yB, b[1]+nz*half
  ]);
  const g=new THREE.BufferGeometry();g.setAttribute("position",new THREE.BufferAttribute(v,3));g.computeVertexNormals();
  scene.add(new THREE.Mesh(g,color));
}

function addRoadMarkings(points, width, highway, isBridge, totalLen){
  if(width<7 || highway==="residential" || highway==="living_street")return;
  const dashLen=5.5,gap=5.5;
  let curDist=0;
  for(let i=0;i<points.length-1;i++){
    const a=points[i],b=points[i+1],dx=b[0]-a[0],dz=b[1]-a[1],len=Math.hypot(dx,dz);
    const segStartDist = curDist;
    curDist += len;
    if(len<12)continue;
    const ux=dx/len,uz=dz/len;
    for(let t=2;t<len-1;t+=dashLen+gap){
      const end=Math.min(t+dashLen,len-1);
      let yA = 0.065, yB = 0.065;
      if(totalLen > 0){
        const terrainA = a.length > 2 ? a[2] : 0;
        const terrainB = b.length > 2 ? b[2] : 0;
        yA = getRoadHeightAtDist(segStartDist + t, totalLen, isBridge, terrainA, terrainB, t/len);
        yB = getRoadHeightAtDist(segStartDist + end, totalLen, isBridge, terrainA, terrainB, end/len);
      }
      lineSegmentSloped([a[0]+ux*t,a[1]+uz*t],[a[0]+ux*end,a[1]+uz*end],.12,markingMat,yA,yB);
    }
  }
}

function drawBuilding(points,height){
  if(points.length<3)return;
  const shape=new THREE.Shape();
  shape.moveTo(points[0][0],-points[0][1]);
  for(let i=1;i<points.length;i++)shape.lineTo(points[i][0],-points[i][1]);
  shape.closePath();
  const geometry=new THREE.ExtrudeGeometry(shape,{depth:height,bevelEnabled:false});
  geometry.rotateX(-Math.PI/2);
  const mesh=new THREE.Mesh(geometry,buildingMat);
  mesh.position.y=0;
  scene.add(mesh);
  const cx=points.reduce((s,p)=>s+p[0],0)/points.length;
  const cz=points.reduce((s,p)=>s+p[1],0)/points.length;
  lodObjects.push({mesh, x:cx, z:cz, type:"building"});
}

function addTree(x,z){
  const scale = 2.2;
  const trunk=new THREE.Mesh(new THREE.CylinderGeometry(.3*scale,.4*scale,2.5*scale,6),trunkMat);
  trunk.position.set(x, 1.25*scale, z);scene.add(trunk);
  const crown=new THREE.Mesh(new THREE.ConeGeometry(1.5*scale, 3.5*scale, 6),treeMat);
  crown.position.set(x, 3.2*scale, z);scene.add(crown);
  lodObjects.push({mesh:trunk,x,z,type:"tree"},{mesh:crown,x,z,type:"tree"});
}

function addBridgeRails(points,width,totalLen){
  let curDist=0;
  for(let i=0;i<points.length-1;i++){
    const a=points[i],b=points[i+1],dx=b[0]-a[0],dz=b[1]-a[1],len=Math.hypot(dx,dz);
    if(len<.1)continue;
    const nx=-dz/len,nz=dx/len;
    const segStart = curDist;
    curDist += len;
    for(const side of [-1,1]){
      const offset=width/2+.3;
      const yA = getRoadHeightAtDist(segStart, totalLen, true, a[2]||0, b[2]||0, 0);
      const yB = getRoadHeightAtDist(curDist, totalLen, true, a[2]||0, b[2]||0, 1);
      const rail=new THREE.Mesh(new THREE.BoxGeometry(.18,.8,len),material(0x777b7e));
      rail.position.set((a[0]+b[0])/2+nx*offset, (yA+yB)/2 + 0.4, (a[1]+b[1])/2+nz*offset);
      rail.rotation.y=Math.atan2(dx,dz);
      rail.rotation.x = Math.atan2(yB - yA, len);
      scene.add(rail);
    }
  }
}

function getRoadHeightAtDist(dist, totalLen, isBridge, terrainA=0, terrainB=0, segmentT=null){
  const tTerrain = segmentT===null ? (totalLen>0?Math.max(0,Math.min(1,dist/totalLen)):0) : Math.max(0,Math.min(1,segmentT));
  const terrainY = terrainA + (terrainB-terrainA) * tTerrain;
  if(!isBridge || totalLen <= 0) return terrainY + 0.035;
  const rampLen = Math.min(15, totalLen * 0.25);
  if(dist < rampLen){
    return terrainY + 0.035 + (1.8 - 0.035) * (dist / rampLen);
  } else if(dist > totalLen - rampLen){
    return terrainY + 0.035 + (1.8 - 0.035) * ((totalLen - dist) / rampLen);
  } else {
    return terrainY + 1.8;
  }
}

for(const r of DATA.roads){
  const pts=r.points;
  let totalLen = 0;
  let segLens = [];
  for(let i=0; i<pts.length-1; i++){
    let l = Math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1]);
    segLens.push(l); totalLen += l;
  }

  let accum = 0;
  for(let i=0;i<pts.length-1;i++){
    const a=pts[i], b=pts[i+1], len=segLens[i];
    if(len < 0.05) continue;
    const dStart = accum;
    accum += len;
    const terrainA = a.length > 2 ? a[2] : 0;
    const terrainB = b.length > 2 ? b[2] : 0;
    const yA = getRoadHeightAtDist(dStart, totalLen, r.bridge, terrainA, terrainB, 0);
    const yB = getRoadHeightAtDist(accum, totalLen, r.bridge, terrainA, terrainB, 1);
    roadQuadSloped(a, b, r.width, r.bridge?bridgeMat:roadMat, yA, yB);
  }
  addRoadMarkings(pts, r.width, r.highway, r.bridge, totalLen);
  if(r.bridge) addBridgeRails(pts, r.width, totalLen);

  if(["primary","secondary","tertiary","trunk","residential"].includes(r.highway)){
    for(let i=0;i<pts.length-1;i++){
      const a=pts[i],b=pts[i+1],dx=b[0]-a[0],dz=b[1]-a[1],len=Math.hypot(dx,dz);
      if(len<25)continue;
      const nx=-dz/len,nz=dx/len;
      for(let t=25;t<len;t+=70){
        const x=a[0]+dx*t/len,z=a[1]+dz*t/len,off=r.width/2+5.0;
        addTree(x+nx*off, z+nz*off);
        addTree(x-nx*off, z-nz*off);
      }
    }
  }
}

const landmarkMarkers = [];
for(const b of DATA.buildings) {
  drawBuilding(b.points, b.height||10);
  if(b.name && b.name.trim() !== "") {
    const el = document.createElement('div');
    el.className = 'map-pin';
    el.innerHTML = `
      <div class="pin-body" style="background: ${b.color || '#9c27b0'};"><div class="pin-circle-hole"></div></div>
      <div class="pin-label">${b.name}</div>
    `;
    el.onclick = () => {
      alert(`📍 주요 시설 안내: ${b.name}`);
    };
    markersContainer.appendChild(el);
    landmarkMarkers.push({
      element: el,
      position: new THREE.Vector3(b.cx, (b.height || 10) + 1.5, b.cz)
    });
  }
}

for(const w of DATA.water){
  for(let i=0;i<w.points.length-1;i++){
    roadQuadSloped(w.points[i], w.points[i+1], 12, waterMat, 0.02, 0.02);
  }
}

const car=new THREE.Group();scene.add(car);
const carPaint=material(0xb83b3b),glass=material(0x5e747e),tireMat=material(0x202020),rimMat=material(0x96999b);
const body=new THREE.Mesh(new THREE.BoxGeometry(1.82,.62,4.45),carPaint);
body.position.y=.68;car.add(body);
const hood=new THREE.Mesh(new THREE.BoxGeometry(1.72,.22,1.0),carPaint);
hood.position.set(0,.98,1.35);car.add(hood);
const cabin=new THREE.Mesh(new THREE.BoxGeometry(1.48,.62,1.85),glass);
cabin.position.set(0,1.22,-.35);car.add(cabin);
const roof=new THREE.Mesh(new THREE.BoxGeometry(1.35,.12,1.25),carPaint);
roof.position.set(0,1.57,-.35);car.add(roof);
const wheels=[];
for(const x of [-.94,.94])for(const z of [-1.42,1.42]){
  const wheel=new THREE.Mesh(new THREE.CylinderGeometry(.34,.34,.22,12),tireMat);
  wheel.rotation.z=Math.PI/2;wheel.position.set(x,.36,z);car.add(wheel);wheels.push(wheel);
  const rim=new THREE.Mesh(new THREE.CylinderGeometry(.19,.19,.235,10),rimMat);
  rim.rotation.z=Math.PI/2;rim.position.set(x,.36,z);car.add(rim);
}

function pointInPolygon(x,z,poly){
  let inside=false;
  for(let i=0,j=poly.length-1;i<poly.length;j=i++){
    const xi=poly[i][0],zi=poly[i][1],xj=poly[j][0],zj=poly[j][1];
    const hit=((zi>z)!=(zj>z))&&(x<(xj-xi)*(z-zi)/(zj-zi+1e-12)+xi);
    if(hit)inside=!inside;
  }
  return inside;
}
function distToSeg(px,pz,a,b){
  const vx=b[0]-a[0],vz=b[1]-a[1],wx=px-a[0],wz=pz-a[1],l2=vx*vx+vz*vz;
  const t=l2?Math.max(0,Math.min(1,(wx*vx+wz*vz)/l2)):0;
  return Math.hypot(px-(a[0]+t*vx),pz-(a[1]+t*vz));
}
function buildingCollision(x,z,yaw){
  const halfL=2.15,halfW=.95;
  const corners=[
    [ halfW, halfL],[ -halfW, halfL],
    [ halfW,-halfL],[ -halfW,-halfL],
    [0,halfL],[0,-halfL],[halfW,0],[-halfW,0]
  ];
  for(const b of DATA.buildings){
    const poly=b.points;
    if(pointInPolygon(x,z,poly))return true;
    for(const c of corners){
      const wx=x+c[0]*Math.cos(yaw)+c[1]*Math.sin(yaw);
      const wz=z-c[0]*Math.sin(yaw)+c[1]*Math.cos(yaw);
      if(pointInPolygon(wx,wz,poly))return true;
      for(let i=0;i<poly.length;i++){
        if(distToSeg(wx,wz,poly[i],poly[(i+1)%poly.length])<.25)return true;
      }
    }
  }
  return false;
}

function getCarHeight(x, z){
  let bestDist=Infinity, bestHeight=0.035;
  for(const r of DATA.roads){
    const pts=r.points;
    let totalLen=0, segLengths=[];
    for(let i=0;i<pts.length-1;i++){
      const l=Math.hypot(pts[i+1][0]-pts[i][0],pts[i+1][1]-pts[i][1]);
      segLengths.push(l); totalLen+=l;
    }
    let accum=0;
    for(let i=0;i<pts.length-1;i++){
      const a=pts[i], b=pts[i+1], len=segLengths[i];
      if(len<.05)continue;
      const d=distToSeg(x,z,a,b);
      if(d<=r.width/2+2 && d<bestDist){
        const vx=b[0]-a[0], vz=b[1]-a[1], l2=vx*vx+vz*vz;
        const t=l2?Math.max(0,Math.min(1,((x-a[0])*vx+(z-a[1])*vz)/l2)):0;
        const terrainA=a.length>2?a[2]:0, terrainB=b.length>2?b[2]:0;
        const terrain=terrainA+(terrainB-terrainA)*t;
        const bridgeExtra=r.bridge?getRoadHeightAtDist(accum+t*len,totalLen,true,terrainA,terrainB,t)-terrain:0;
        bestHeight=terrain+bridgeExtra+.035;
        bestDist=d;
      }
      accum+=len;
    }
  }
  return bestHeight;
}

let startRoad=DATA.roads.find(r=>r.points.length>=2);
let start=[0,0],yaw=0;
if(startRoad){
  const mid=Math.floor((startRoad.points.length-2)/2);
  const a=startRoad.points[Math.max(0,mid)],b=startRoad.points[Math.max(0,mid)+1];
  start=[(a[0]+b[0])/2,(a[1]+b[1])/2];
  yaw=Math.atan2(b[0]-a[0],b[1]-a[1]);
}
car.position.set(start[0], 0.035, start[1]); car.rotation.y=yaw;

let velocity=0,steer=0;
const keys={};
window.addEventListener("keydown",e=>{
  const k=e.key.toLowerCase();keys[k]=true;
  if(k==="c")toggleCamera();
  if(["arrowup","arrowdown","arrowleft","arrowright"," "].includes(k))e.preventDefault();
});
window.addEventListener("keyup",e=>keys[e.key.toLowerCase()]=false);
const touch={f:false,b:false,l:false,r:false};
function bindButton(id,key){
  const el=document.getElementById(id);
  el.addEventListener("pointerdown",e=>{e.preventDefault();touch[key]=true;});
  ["pointerup","pointercancel","pointerleave"].forEach(ev=>el.addEventListener(ev,()=>touch[key]=false));
}
bindButton("forward","f");bindButton("back","b");bindButton("left","l");bindButton("right","r");

let follow=true,orbitYaw=yaw+Math.PI,orbitPitch=.28,camDist=13;
let dragging=false,lastX=0,lastY=0;
renderer.domElement.addEventListener("pointerdown",e=>{
  dragging=true;lastX=e.clientX;lastY=e.clientY;
  renderer.domElement.setPointerCapture(e.pointerId);
});
renderer.domElement.addEventListener("pointermove",e=>{
  if(!dragging)return;
  const dx=e.clientX-lastX,dy=e.clientY-lastY;lastX=e.clientX;lastY=e.clientY;
  orbitYaw-=dx*.005;
  orbitPitch=Math.max(.08,Math.min(1.25,orbitPitch+dy*.004));
});
function endDrag(){dragging=false;}
renderer.domElement.addEventListener("pointerup",endDrag);
renderer.domElement.addEventListener("pointercancel",endDrag);
renderer.domElement.addEventListener("wheel",e=>{
  e.preventDefault();camDist=Math.max(5,Math.min(100,camDist+e.deltaY*.025));
},{passive:false});
function toggleCamera(){
  follow=!follow;
  document.getElementById("cameraLabel").textContent=follow?"카메라: 3인칭 추적":"카메라: 자유 시점";
  if(follow)orbitYaw=yaw+Math.PI;
}
document.getElementById("camBtn").onclick=toggleCamera;

const target=new THREE.Vector3();
const tempVector=new THREE.Vector3();
let lastTime=performance.now();
let lastLodUpdate=0;

function animate(now){
  requestAnimationFrame(animate);
  const dt=Math.min((now-lastTime)/1000,.04);lastTime=now;

  const forward=keys.w||keys.arrowup||touch.f;
  const backward=keys.s||keys.arrowdown||touch.b;
  const left=keys.a||keys.arrowleft||touch.l;
  const right=keys.d||keys.arrowright||touch.r;

  if(forward)velocity=Math.min(30,velocity+5.5*dt);
  else if(backward)velocity=Math.max(-5,velocity-7.5*dt);
  else velocity*=Math.pow(.985,dt*60);

  const steerInput=(left?1:0)-(right?1:0);
  steer=THREE.MathUtils.damp(steer,steerInput,4.5,dt);
  const steerAngle=steer*.22;
  const wheelbase=2.7;
  if(Math.abs(velocity)>.05)yaw+=velocity/wheelbase*Math.tan(steerAngle)*dt;
  car.rotation.y=yaw;
  wheels[0].rotation.y=steerAngle;wheels[1].rotation.y=steerAngle;

  const nx=car.position.x+Math.sin(yaw)*velocity*dt;
  const nz=car.position.z+Math.cos(yaw)*velocity*dt;
  
  if(!buildingCollision(nx,nz,yaw)){
    car.position.x=nx;car.position.z=nz;
    car.position.y = getCarHeight(nx, nz);
    statusEl.textContent="주행 중";
  }else{
    velocity = -velocity * 0.35; 
    car.position.x -= Math.sin(yaw) * Math.abs(velocity) * dt * 2.5;
    car.position.z -= Math.cos(yaw) * Math.abs(velocity) * dt * 2.5;
    car.position.y = getCarHeight(car.position.x, car.position.z);
    statusEl.textContent="💥 쾅! 건물에 부딪혀 뒤로 튕겨 나갑니다!";
  }
  speedEl.textContent=Math.round(Math.abs(velocity)*3.6);

  if(now-lastLodUpdate>500){
    lastLodUpdate=now;
    for(const item of lodObjects){
      const d=Math.hypot(item.x-car.position.x,item.z-car.position.z);
      // Road meshes visible farther away than detailed buildings/trees.
      const limit=item.type==="road" ? LOD_DISTANCE*1.8 : LOD_DISTANCE;
      item.mesh.visible=d<limit;
    }
  }

  if(follow){
    const desiredYaw=orbitYaw;
    const horizontal=camDist*Math.cos(orbitPitch);
    const desired=new THREE.Vector3(
      car.position.x+Math.sin(desiredYaw)*horizontal,
      car.position.y+1.8+camDist*Math.sin(orbitPitch),
      car.position.z+Math.cos(desiredYaw)*horizontal
    );
    camera.position.lerp(desired,.13);
    target.set(car.position.x,car.position.y+1.0,car.position.z);
  }else{
    const horizontal=camDist*Math.cos(orbitPitch);
    const desired=new THREE.Vector3(
      car.position.x+Math.sin(orbitYaw)*horizontal,
      car.position.y+2+camDist*Math.sin(orbitPitch),
      car.position.z+Math.cos(orbitYaw)*horizontal
    );
    camera.position.lerp(desired,.12);
    target.set(car.position.x,car.position.y+.5,car.position.z);
  }
  camera.lookAt(target);
  renderer.render(scene,camera);

  const widthHalf = game.clientWidth / 2;
  const heightHalf = game.clientHeight / 2;

  for(const m of landmarkMarkers){
    tempVector.copy(m.position);
    tempVector.project(camera);
    if(tempVector.z < 1.0){
      const x = (tempVector.x * widthHalf) + widthHalf;
      const y = -(tempVector.y * heightHalf) + heightHalf;
      m.element.style.display = 'flex';
      m.element.style.transform = `translate(-50%, -100%) translate(${x}px, ${y}px)`;
    } else {
      m.element.style.display = 'none';
    }
  }
}
camera.position.set(start[0],car.position.y+5,start[1]-13);
requestAnimationFrame(animate);
window.addEventListener("resize",()=>{
  camera.aspect=game.clientWidth/game.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(game.clientWidth,game.clientHeight);
});
</script></body></html>"""
    html = html.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    components.html(html, height=780, scrolling=False)
else:
    st.info("왼쪽 사이드바에서 도시/주소를 입력하고 ‘도시 불러오기’ 버튼을 눌러 주세요.")
