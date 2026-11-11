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
        options=[300, 400, 600, 800],
        value=400,
        format_func=lambda x: f"{x} m"
    )
    use_elevation = st.checkbox("SRTM 실제 지형 고도 적용 (3D 언덕)", value=True)
    lod_distance = st.select_slider("거리 기반 상세 렌더링", options=[250, 400, 600], value=400,
                                   format_func=lambda x: f"상세 표시 {x}m 이내")
    load = st.button("도시 불러오기", type="primary")
    st.caption("차량 크기: 약 4.5m × 1.8m (실제 승용차 비율)")

@st.cache_data(ttl=2592000, show_spinner=False)
def geocode(q):
    """
    주소 검색:
    1) 자주 사용하는 지역은 저장된 좌표 사용
    2) Photon 검색
    3) Photon 실패 시 Nominatim으로 한 번 대체 시도
    결과는 30일간 캐시한다.
    """
    import re
    query = re.sub(r"\\s+", " ", str(q)).strip()
    if not query:
        raise ValueError("도시나 주소를 입력해 주세요.")

    # 추천 입력 예시와 자주 쓰는 지역은 외부 주소 검색 요청 없이 처리
    known_places = {
        "서울특별시 종로구": (37.5730, 126.9794),
        "서울 종로구": (37.5730, 126.9794),
        "서울특별시 강남구": (37.5172, 127.0473),
        "서울 강남구": (37.5172, 127.0473),
        "부산 해운대구": (35.1631, 129.1635),
        "부산광역시 해운대구": (35.1631, 129.1635),
        "수원시 팔달구": (37.2809, 127.0090),
        "경기도 수원시 팔달구": (37.2809, 127.0090),
        "성남시 분당구": (37.3825, 127.1189),
        "강릉시 중앙동": (37.7520, 128.8759),
        "춘천시": (37.8813, 127.7298),
        "천안시 서북구": (36.8320, 127.1130),
        "청주시 흥덕구": (36.6424, 127.4890),
        "전주시 완산구": (35.8118, 127.1470),
        "여수시": (34.7604, 127.6622),
        "포항시 북구": (36.0389, 129.3650),
        "경주시": (35.8562, 129.2247),
    }
    if query in known_places:
        lat, lon = known_places[query]
        return lat, lon, query + " (저장된 대표 위치)"

    headers = {
        "User-Agent": "Student3DDrivingSimulator/1.0 (educational mapping project)",
        "Accept": "application/json",
    }
    errors = []

    # Photon을 우선 사용해 Nominatim 요청이 한 곳에 몰리지 않도록 한다.
    try:
        response = requests.get(
            "https://photon.komoot.io/api/",
            params={"q": query, "limit": 1, "lang": "en"},
            headers=headers,
            timeout=(4, 9),
        )
        response.raise_for_status()
        features = response.json().get("features", [])
        if features:
            feature = features[0]
            coords = feature.get("geometry", {}).get("coordinates", [])
            if len(coords) >= 2:
                props = feature.get("properties", {})
                label = ", ".join(
                    str(props[k]) for k in ("name", "city", "state", "country")
                    if props.get(k)
                ) or query
                return float(coords[1]), float(coords[0]), label
        errors.append("Photon에서 검색 결과를 찾지 못함")
    except requests.exceptions.RequestException as exc:
        errors.append(f"Photon 검색 실패({type(exc).__name__})")
    except (ValueError, TypeError, KeyError):
        errors.append("Photon 응답을 읽을 수 없음")

    # 대체 검색은 한 번만 시도한다. 429이면 재시도하지 않아 차단을 악화시키지 않는다.
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "jsonv2", "limit": 1},
            headers=headers,
            timeout=(4, 9),
        )
        if response.status_code == 429:
            raise RuntimeError("Nominatim 검색 요청이 일시적으로 제한됨(HTTP 429)")
        response.raise_for_status()
        items = response.json()
        if items:
            item = items[0]
            return float(item["lat"]), float(item["lon"]), item.get("display_name", query)
        errors.append("Nominatim에서 검색 결과를 찾지 못함")
    except requests.exceptions.RequestException as exc:
        errors.append(f"Nominatim 검색 실패({type(exc).__name__})")
    except (ValueError, TypeError, KeyError) as exc:
        errors.append(f"Nominatim 응답 처리 실패({type(exc).__name__})")
    except RuntimeError as exc:
        errors.append(str(exc))

    raise RuntimeError(
        "주소를 찾지 못했습니다. 잠시 후 다시 시도하거나 "
        "예시 지역 이름(예: 서울특별시 종로구, 수원시 팔달구)을 입력해 주세요. "
        + " / ".join(errors)
    )

@st.cache_data(ttl=21600, show_spinner=False)
def get_osm(lat, lon, radius_m):
    dlat = radius_m / 111320
    dlon = radius_m / (111320 * max(math.cos(math.radians(lat)), 0.2))
    south, west, north, east = lat-dlat, lon-dlon, lat+dlat, lon+dlon

    query = f"""
    [out:json][timeout:20][maxsize:268435456];
    (
      way["highway"~"primary|secondary|tertiary|residential|unclassified"]({south},{west},{north},{east});
      way["building"]({south},{west},{north},{east});
      way["amenity"~"restaurant|cafe|library|courthouse|town_hall|marketplace|convenience"]({south},{west},{north},{east});
      way["shop"~"mall|department_store|supermarket|convenience"]({south},{west},{north},{east});
      way["tourism"~"museum|attraction|gallery"]({south},{west},{north},{east});
      way["leisure"="park"]({south},{west},{north},{east});
      way["historic"]({south},{west},{north},{east});
    );
    out body geom;
    """

    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    ]
    errors = []
    headers = {
        "User-Agent": "Student3DDrivingSimulator/45.0",
        "Accept": "application/json",
    }

    for endpoint in endpoints:
        try:
            response = requests.post(
                endpoint,
                data={"data": query},
                headers=headers,
                timeout=(5, 20),
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
        "OSM 서버 응답 시간이 초과되었습니다. 지도 범위 반경을 작게 설정 후 다시 시도해 주세요. "
        f"시도 결과: {detail}"
    )

@st.cache_data(ttl=86400, show_spinner=False)
def query_elevation_batch(locations):
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
            headers={"User-Agent": "Student3DDrivingSimulator/45.0"},
            timeout=20
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "OK":
            raise RuntimeError(payload.get("error", "고도 API 응답 오류"))
        results.extend([item.get("elevation") for item in payload.get("results", [])])
        if start + 100 < len(locations):
            import time
            time.sleep(1.0)
    return results

def add_terrain_elevation(osm, center_lat, center_lon, max_samples=120):
    elements = osm.get("elements", [])
    road_elements = [
        el for el in elements
        if "highway" in el.get("tags", {})
        and len(el.get("geometry", [])) >= 2
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
        return osm, 0.0, [], "도로 길이 계산 실패"

    interval = max(60.0, total_length / max_samples)
    sample_records = []
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
        sample_records.append((road_idx, cum, g[-1]["lat"], g[-1]["lon"]))

    if len(sample_records) > max_samples:
        stride = max(1, math.ceil(len(sample_records) / max_samples))
        sample_records = sample_records[::stride]

    coords = [(rec[2], rec[3]) for rec in sample_records]
    elevations = query_elevation_batch(coords)
    by_road = {}
    terrain_samples = []
    
    for rec, elev in zip(sample_records, elevations):
        if elev is not None:
            by_road.setdefault(rec[0], []).append((rec[1], float(elev)))
            terrain_samples.append((rec[2], rec[3], float(elev)))

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

    valid = [e for _, _, e in terrain_samples]
    min_elev = min(valid) if valid else 0.0

    meters_lon = 111320 * math.cos(math.radians(center_lat))
    meters_lat = 111320
    formatted_terrain_points = [
        [
            (slon - center_lon) * meters_lon,
            -(slat - center_lat) * meters_lat,
            float(selev) - float(min_elev)
        ]
        for slat, slon, selev in terrain_samples
    ]

    return osm, float(min_elev), formatted_terrain_points, f"SRTM 30m 표본 {len(coords)}개 (3D 지형 적용)"

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
        "residential": 6.0, "unclassified": 6.0
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

    if amenity in ["restaurant", "cafe", "fast_food", "pub", "bar"] or any(k in name for k in ["음식점", "식당", "카페", "커피", "맛집"]):
        return name, "#ff9800"

    if shop in ["convenience"] or amenity in ["convenience"] or "편의점" in name:
        return name, "#2196f3"

    if shop in ["mall", "department_store", "supermarket"] or amenity in ["marketplace"] or any(k in name for k in ["백화점", "쇼핑몰", "시장", "마트"]):
        return name, "#e53935"

    if leisure in ["park", "garden"] or historic != "" or tourism in ["attraction", "viewpoint"] or any(k in name for k in ["공원", "산", "문화재", "유적", "궁", "왕릉"]):
        return name, "#4caf50"

    valid_others = ["library", "courthouse", "town_hall", "museum", "university", "college"]
    if amenity in valid_others or tourism in ["museum", "gallery"] or any(k in name for k in ["박물관", "시청", "법원", "도서관", "구청", "주민센터"]):
        return name, "#9c27b0"

    return None, None

def convert_osm(osm, center_lat, center_lon, base_elevation=0.0, terrain_points=None):
    result = {"roads": [], "buildings": [], "terrain_points": terrain_points if terrain_points else []}
    meters_lon = 111320 * math.cos(math.radians(center_lat))
    meters_lat = 111320

    def get_terrain_height_at(x, z):
        pts = result["terrain_points"]
        if not pts:
            return 0.0
        total_w = 0.0
        sum_h = 0.0
        for px, pz, pelev in pts:
            d2 = (x - px)**2 + (z - pz)**2
            if d2 < 0.01:
                return pelev
            w = 1.0 / (d2 + 5.0)
            sum_h += pelev * w
            total_w += w
        return sum_h / total_w if total_w > 0 else 0.0

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
            if raw_elev is not None:
                local_y = float(raw_elev) - float(base_elevation)
            else:
                local_y = get_terrain_height_at(x, z)
            points.append([x, z, local_y])

        if "highway" in tags:
            highway = tags.get("highway", "")
            if highway in ("footway", "path", "steps", "cycleway", "pedestrian", "track"):
                continue
            result["roads"].append({
                "points": points,
                "width": road_width_m(tags),
                "highway": highway,
                "bridge": tags.get("bridge") == "yes",
                "tunnel": tags.get("tunnel") == "yes",
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
            cy = get_terrain_height_at(cx, cz)
            
            landmark_name, pin_color = get_category_and_color(tags)

            result["buildings"].append({
                "points": points,
                "height": min(max(height, 3.0), 150.0),
                "name": landmark_name if landmark_name else "",
                "color": pin_color if pin_color else "",
                "cx": cx,
                "cz": cz,
                "cy": cy
            })

    return result

if "city_data" not in st.session_state:
    st.session_state.city_data = None
if "city_label" not in st.session_state:
    st.session_state.city_label = ""

if load:
    try:
        with st.spinner("실제 지형 고도와 도로/건물 데이터를 3D로 구축하는 중입니다..."):
            lat, lon, label = geocode(place.strip())
            raw = get_osm(lat, lon, radius)
            elevation_note = "고도 데이터 사용 안 함"
            base_elev = 0.0
            terrain_points = []
            if use_elevation:
                try:
                    raw, base_elev, terrain_points, elevation_note = add_terrain_elevation(raw, lat, lon)
                except Exception as elev_error:
                    base_elev = 0.0
                    elevation_note = f"고도 API 실패(평지 대체): {elev_error}"
            else:
                base_elev = 0.0
            st.session_state.city_data = convert_osm(raw, lat, lon, base_elev or 0.0, terrain_points)
            st.session_state.city_data["base_elevation"] = base_elev or 0.0
            st.session_state.city_data["elevation_note"] = elevation_note
            st.session_state.city_data["lod_distance"] = lod_distance
            st.session_state.city_label = label
    except Exception as error:
        st.error(f"도시를 불러오지 못했습니다: {error}")

if st.session_state.city_data:
    data = st.session_state.city_data
    st.success(f"📍 {st.session_state.city_label}")
    st.caption(f"도로 {len(data['roads'])}개 · 건물 {len(data['buildings'])}개")
    st.caption(f"⛰️ {data.get('elevation_note', '고도 데이터 상태 확인 필요')} | 상세 렌더링 거리: {data.get('lod_distance', 400)}m")
    st.info("W/S 또는 ↑/↓: 가속·후진 | A/D 또는 ←/→: 조향 | 마우스 드래그: 카메라 회전 | 휠: 확대·축소 | C: 카메라 추적/자유 모드")

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
<div id="help">W/S 또는 ↑/↓: 가속·후진<br>A/D 또는 ←/→: 조향<br><br>마우스 드래그: 카메라 회전<br>휠: 확대·축소<br>C: 추적/자유 카메라</div>
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

const renderer=new THREE.WebGLRenderer({antialias:true, powerPreference:"high-performance"});
renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.5));
renderer.setSize(game.clientWidth,game.clientHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.domElement.style.position="absolute";
renderer.domElement.style.inset="0";
renderer.domElement.style.touchAction="none";
game.insertBefore(renderer.domElement,game.firstChild);

scene.add(new THREE.HemisphereLight(0xffffff,0x555555,1.5));
const sun=new THREE.DirectionalLight(0xffffff,1.35);
sun.position.set(300,600,300);
sun.castShadow = true;
sun.shadow.mapSize.width = 2048;
sun.shadow.mapSize.height = 2048;
sun.shadow.camera.near = 0.5;
sun.shadow.camera.far = 3000;
const d = 600;
sun.shadow.camera.left = -d;
sun.shadow.camera.right = d;
sun.shadow.camera.top = d;
sun.shadow.camera.bottom = -d;
sun.shadow.bias = -0.0005;
scene.add(sun);

const material=(color)=>new THREE.MeshStandardMaterial({
  color,
  roughness: 0.85,
  metalness: 0.05,
  side: THREE.DoubleSide
});

const groundMat=material(0x7fa27f); 
const roadMat=material(0x343638);
const bridgeMat=material(0x42464a);
const pierMat=material(0x808588);
const tunnelPortalMat=material(0x1a1a1a);
const markingMat=material(0xd8d6c9);
const treeMat=material(0x3e5e3b); 
const trunkMat=material(0x5c4938);
const buildingMat=material(0x9098a0);

function getTerrainHeightAt(x, z){
  const pts = DATA.terrain_points;
  if(!pts || pts.length === 0) return 0.0;
  let totalW = 0.0;
  let sumH = 0.0;
  for(const pt of pts){
    const dx = x - pt[0];
    const dz = z - pt[1];
    const d2 = dx*dx + dz*dz;
    if(d2 < 0.01) return pt[2];
    const w = 1.0 / (d2 + 5.0);
    sumH += pt[2] * w;
    totalW += w;
  }
  return totalW > 0 ? sumH / totalW : 0.0;
}

// 지형 바닥 높이 (단일 고도 시스템 적용)
const groundGeo = new THREE.PlaneGeometry(3500, 3500, 70, 70);
groundGeo.rotateX(-Math.PI / 2);
const posAttr = groundGeo.attributes.position;
for(let i=0; i<posAttr.count; i++){
  const vx = posAttr.getX(i);
  const vz = posAttr.getZ(i);
  posAttr.setY(i, getTerrainHeightAt(vx, vz));
}
groundGeo.computeVertexNormals();
const ground = new THREE.Mesh(groundGeo, groundMat);
ground.receiveShadow = true;
scene.add(ground);

function addSceneryDetails(){
  for(let i=0; i<80; i++){
    let rx = (Math.random() - 0.5) * 1000;
    let rz = (Math.random() - 0.5) * 1000;
    const y = getTerrainHeightAt(rx, rz);
    const grass = new THREE.Mesh(new THREE.DodecahedronGeometry(0.8), groundMat);
    grass.position.set(rx, y, rz);
    grass.castShadow = true;
    grass.receiveShadow = true;
    scene.add(grass);
  }
}
addSceneryDetails();

function isNearOtherRoad(x, z, currentRoadIndex) {
  for (let rIdx = 0; rIdx < DATA.roads.length; rIdx++) {
    if (rIdx === currentRoadIndex) continue;
    const pts = DATA.roads[rIdx].points;
    for (let i = 0; i < pts.length - 1; i++) {
      if (distToSeg(x, z, pts[i], pts[i+1]) < 2.0) {
        return true;
      }
    }
  }
  return false;
}

function addBridgeSupports(a, b, width, yA, yB) {
  const dx = b[0] - a[0], dz = b[1] - a[1], len = Math.hypot(dx, dz);
  if (len < 4.0) return;

  const midX = (a[0] + b[0]) / 2;
  const midZ = (a[1] + b[1]) / 2;
  const roadY = (yA + yB) / 2;
  const terrainY = getTerrainHeightAt(midX, midZ);

  if (roadY - terrainY > 1.2) {
    const capGeo = new THREE.BoxGeometry(width + 0.4, 0.4, 1.2);
    const cap = new THREE.Mesh(capGeo, pierMat);
    cap.position.set(midX, roadY - 0.25, midZ);
    cap.rotation.y = Math.atan2(dx, dz);
    cap.castShadow = true;
    cap.receiveShadow = true;
    scene.add(cap);

    const pillarHeight = roadY - terrainY;
    const pillarGeo = new THREE.CylinderGeometry(0.5, 0.6, pillarHeight, 8);
    const pillar = new THREE.Mesh(pillarGeo, pierMat);
    pillar.position.set(midX, terrainY + pillarHeight / 2, midZ);
    pillar.castShadow = true;
    pillar.receiveShadow = true;
    scene.add(pillar);
  }
}

function addRoadBarriers(a, b, width, yA, yB, rIdx, isBridge, isTunnel) {
  if (isTunnel || isBridge) return;
  const dx=b[0]-a[0], dz=b[1]-a[1], len=Math.hypot(dx,dz);
  if(len<.05)return;
  const nx=-dz/len, nz=dx/len, half=width/2;

  const leftMid = [(a[0]+b[0])/2 - nx*half, (a[1]+b[1])/2 - nz*half];
  if (!isNearOtherRoad(leftMid[0], leftMid[1], rIdx)) {
    const barrier = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.4, len), material(0x777b7e));
    barrier.position.set(leftMid[0], (yA+yB)/2 + 0.2, leftMid[1]);
    barrier.rotation.y = Math.atan2(dx, dz);
    barrier.rotation.x = Math.atan2(yB - yA, len);
    barrier.castShadow = true;
    barrier.receiveShadow = true;
    scene.add(barrier);
  }

  const rightMid = [(a[0]+b[0])/2 + nx*half, (a[1]+b[1])/2 + nz*half];
  if (!isNearOtherRoad(rightMid[0], rightMid[1], rIdx)) {
    const barrier = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.4, len), material(0x777b7e));
    barrier.position.set(rightMid[0], (yA+yB)/2 + 0.2, rightMid[1]);
    barrier.rotation.y = Math.atan2(dx, dz);
    barrier.rotation.x = Math.atan2(yB - yA, len);
    barrier.castShadow = true;
    barrier.receiveShadow = true;
    scene.add(barrier);
  }
}

function addTunnelPortal(x, z, y, width, dx, dz) {
  const portalGroup = new THREE.Group();
  const archGeo = new THREE.BoxGeometry(width + 1.2, 3.2, 0.8);
  const portalMesh = new THREE.Mesh(archGeo, tunnelPortalMat);
  portalMesh.position.set(0, 1.6, 0);
  portalMesh.castShadow = true;
  portalGroup.add(portalMesh);

  const holeGeo = new THREE.BoxGeometry(width, 2.8, 0.9);
  const holeMat = new THREE.MeshBasicMaterial({color: 0x0a0a0a});
  const holeMesh = new THREE.Mesh(holeGeo, holeMat);
  holeMesh.position.set(0, 1.4, 0);
  portalGroup.add(holeMesh);

  portalGroup.position.set(x, y, z);
  portalGroup.rotation.y = Math.atan2(dx, dz);
  scene.add(portalGroup);
}

function roadQuadSloped(a, b, width, mat, yA, yB, rIdx, isBridge, isTunnel){
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
  const mesh=new THREE.Mesh(geo, isTunnel ? tunnelPortalMat : mat);
  mesh.receiveShadow = true;
  scene.add(mesh);

  if (isBridge) {
    addBridgeSupports(a, b, width, yA, yB);
  }
  addRoadBarriers(a, b, width, yA, yB, rIdx, isBridge, isTunnel);

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
  const g=new THREE.BufferGeometry();
  g.setAttribute("position",new THREE.BufferAttribute(v,3));
  g.computeVertexNormals();
  const mesh = new THREE.Mesh(g, color);
  scene.add(mesh);
}

function addRoadMarkings(points, width, highway, isBridge, isTunnel, totalLen){
  if(width<7 || highway==="residential" || isTunnel)return;
  const dashLen=5.5, gap=5.5;
  let curDist=0;
  for(let i=0; i<points.length-1; i++){
    const a=points[i], b=points[i+1], dx=b[0]-a[0], dz=b[1]-a[1], len=Math.hypot(dx,dz);
    const segStartDist = curDist;
    curDist += len;
    if(len<12)continue;
    const ux=dx/len, uz=dz/len;
    for(let t=2; t<len-1; t+=dashLen+gap){
      const end=Math.min(t+dashLen, len-1);
      const terrainA = a.length > 2 ? a[2] : getTerrainHeightAt(a[0], a[1]);
      const terrainB = b.length > 2 ? b[2] : getTerrainHeightAt(b[0], b[1]);
      const yA = getRoadHeightAtDist(segStartDist + t, totalLen, isBridge, isTunnel, terrainA, terrainB, t/len) + 0.02;
      const yB = getRoadHeightAtDist(segStartDist + end, totalLen, isBridge, isTunnel, terrainA, terrainB, end/len) + 0.02;
      lineSegmentSloped([a[0]+ux*t, a[1]+uz*t], [a[0]+ux*end, a[1]+uz*end], 0.15, markingMat, yA, yB);
    }
  }
}

function drawBuilding(points, height, cy){
  if(points.length<3)return;
  const shape=new THREE.Shape();
  shape.moveTo(points[0][0],-points[0][1]);
  for(let i=1;i<points.length;i++)shape.lineTo(points[i][0],-points[i][1]);
  shape.closePath();
  
  const geometry=new THREE.ExtrudeGeometry(shape,{depth:height,bevelEnabled:false});
  geometry.rotateX(-Math.PI/2);
  const mesh=new THREE.Mesh(geometry, buildingMat);
  mesh.position.y = cy !== undefined ? cy : 0;
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  scene.add(mesh);

  const cx=points.reduce((s,p)=>s+p[0],0)/points.length;
  const cz=points.reduce((s,p)=>s+p[1],0)/points.length;
  lodObjects.push({mesh, x:cx, z:cz, type:"building"});
}

function addTree(x, z, y){
  const scale = 2.2;
  const trunk=new THREE.Mesh(new THREE.CylinderGeometry(.3*scale,.4*scale,2.5*scale,6),trunkMat);
  trunk.position.set(x, y + 1.25*scale, z); trunk.castShadow=true; scene.add(trunk);
  const crown=new THREE.Mesh(new THREE.ConeGeometry(1.5*scale, 3.5*scale, 6),treeMat);
  crown.position.set(x, y + 3.2*scale, z); crown.castShadow=true; scene.add(crown);
  lodObjects.push({mesh:trunk,x,z,type:"tree"},{mesh:crown,x,z,type:"tree"});
}

// 도로 높이: 지형 표면보다 정확히 0.05m 높여 묻힘 방지 및 밀착
function getRoadHeightAtDist(dist, totalLen, isBridge, isTunnel, terrainA=0, terrainB=0, segmentT=null){
  const tTerrain = segmentT===null ? (totalLen>0?Math.max(0,Math.min(1,dist/totalLen)):0) : Math.max(0,Math.min(1,segmentT));
  const terrainY = terrainA + (terrainB-terrainA) * tTerrain;
  if(isTunnel) return terrainY - 0.5;
  if(!isBridge || totalLen <= 0) return terrainY + 0.05;
  const rampLen = Math.min(15, totalLen * 0.25);
  if(dist < rampLen){
    return terrainY + 0.05 + (1.8 * (dist / rampLen));
  } else if(dist > totalLen - rampLen){
    return terrainY + 0.05 + (1.8 * ((totalLen - dist) / rampLen));
  } else {
    return terrainY + 0.05 + 1.8;
  }
}

for(let rIdx = 0; rIdx < DATA.roads.length; rIdx++){
  const r = DATA.roads[rIdx];
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
    const terrainA = a.length > 2 ? a[2] : getTerrainHeightAt(a[0], a[1]);
    const terrainB = b.length > 2 ? b[2] : getTerrainHeightAt(b[0], b[1]);
    const yA = getRoadHeightAtDist(dStart, totalLen, r.bridge, r.tunnel, terrainA, terrainB, 0);
    const yB = getRoadHeightAtDist(accum, totalLen, r.bridge, r.tunnel, terrainA, terrainB, 1);
    roadQuadSloped(a, b, r.width, r.bridge?bridgeMat:roadMat, yA, yB, rIdx, r.bridge, r.tunnel);

    if(r.tunnel) {
      if(i === 0) addTunnelPortal(a[0], a[1], terrainA, r.width, b[0]-a[0], b[1]-a[1]);
      if(i === pts.length - 2) addTunnelPortal(b[0], b[1], terrainB, r.width, a[0]-b[0], a[1]-b[1]);
    }
  }
  addRoadMarkings(pts, r.width, r.highway, r.bridge, r.tunnel, totalLen);

  if(["primary","secondary","tertiary","residential"].includes(r.highway) && !r.tunnel){
    for(let i=0;i<pts.length-1;i++){
      const a=pts[i],b=pts[i+1],dx=b[0]-a[0],dz=b[1]-a[1],len=Math.hypot(dx,dz);
      if(len<35)continue;
      const nx=-dz/len,nz=dx/len;
      for(let t=35;t<len;t+=90){
        const x=a[0]+dx*t/len,z=a[1]+dz*t/len,off=r.width/2+5.0;
        const treeY = getTerrainHeightAt(x+nx*off, z+nz*off);
        addTree(x+nx*off, z+nz*off, treeY);
      }
    }
  }
}

const landmarkMarkers = [];
for(const b of DATA.buildings) {
  drawBuilding(b.points, b.height||10, b.cy || 0);
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
      position: new THREE.Vector3(b.cx, (b.cy || 0) + (b.height || 10) + 1.5, b.cz)
    });
  }
}

const car=new THREE.Group();scene.add(car);
const carPaint=material(0xb83b3b),glass=material(0x5e747e),tireMat=material(0x202020),rimMat=material(0x96999b);
const body=new THREE.Mesh(new THREE.BoxGeometry(1.82,.62,4.45),carPaint);
body.position.y=.68; body.castShadow=true; car.add(body);
const hood=new THREE.Mesh(new THREE.BoxGeometry(1.72,.22,1.0),carPaint);
hood.position.set(0,.98,1.35); hood.castShadow=true; car.add(hood);
const cabin=new THREE.Mesh(new THREE.BoxGeometry(1.48,.62,1.85),glass);
cabin.position.set(0,1.22,-.35); cabin.castShadow=true; car.add(cabin);
const roof=new THREE.Mesh(new THREE.BoxGeometry(1.35,.12,1.25),carPaint);
roof.position.set(0,1.57,-.35); roof.castShadow=true; car.add(roof);
const wheels=[];
for(const x of [-.94,.94])for(const z of [-1.42,1.42]){
  const wheel=new THREE.Mesh(new THREE.CylinderGeometry(.34,.34,.22,12),tireMat);
  wheel.rotation.z=Math.PI/2; wheel.position.set(x,.34,z); wheel.castShadow=true; car.add(wheel); wheels.push(wheel);
  const rim=new THREE.Mesh(new THREE.CylinderGeometry(.19,.19,.235,10),rimMat);
  rim.rotation.z=Math.PI/2; rim.position.set(x,.34,z); car.add(rim);
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
  let bestDist=Infinity, bestHeight=getTerrainHeightAt(x, z) + 0.34;
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
        const terrainA=a.length>2?a[2]:getTerrainHeightAt(a[0],a[1]), terrainB=b.length>2?b[2]:getTerrainHeightAt(b[0],b[1]);
        const roadY = getRoadHeightAtDist(accum+t*len, totalLen, r.bridge, r.tunnel, terrainA, terrainB, t);
        bestHeight = roadY + 0.34;
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
car.position.set(start[0], getCarHeight(start[0], start[1]), start[1]); car.rotation.y=yaw;

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

    # 3D 지도 화면 바깥쪽 아래에 표시되는 색상 범례
    st.markdown(
        """
        <div style="
            margin-top: 12px;
            padding: 14px 16px;
            border: 1px solid #d9dee5;
            border-radius: 10px;
            background: #f8fafc;
            color: #263238;
        ">
          <div style="font-weight: 700; font-size: 15px; margin-bottom: 10px;">
            지도 색상 안내
          </div>
          <div style="display: flex; flex-wrap: wrap; gap: 10px 20px; font-size: 13px;">
            <span style="display:inline-flex;align-items:center;gap:7px;">
              <i style="width:13px;height:13px;border-radius:50%;background:#ff9800;display:inline-block;"></i>
              음식점·카페
            </span>
            <span style="display:inline-flex;align-items:center;gap:7px;">
              <i style="width:13px;height:13px;border-radius:50%;background:#2196f3;display:inline-block;"></i>
              편의점
            </span>
            <span style="display:inline-flex;align-items:center;gap:7px;">
              <i style="width:13px;height:13px;border-radius:50%;background:#e53935;display:inline-block;"></i>
              시장·마트·쇼핑시설
            </span>
            <span style="display:inline-flex;align-items:center;gap:7px;">
              <i style="width:13px;height:13px;border-radius:50%;background:#4caf50;display:inline-block;"></i>
              공원·문화유산·관광지
            </span>
            <span style="display:inline-flex;align-items:center;gap:7px;">
              <i style="width:13px;height:13px;border-radius:50%;background:#9c27b0;display:inline-block;"></i>
              관공서·도서관·박물관 등 주요시설
            </span>
            <span style="display:inline-flex;align-items:center;gap:7px;">
              <i style="width:13px;height:13px;border-radius:3px;background:#343638;display:inline-block;"></i>
              도로
            </span>
            <span style="display:inline-flex;align-items:center;gap:7px;">
              <i style="width:13px;height:13px;border-radius:3px;background:#9098a0;display:inline-block;"></i>
              건물
            </span>
            <span style="display:inline-flex;align-items:center;gap:7px;">
              <i style="width:13px;height:13px;border-radius:3px;background:#3e5e3b;display:inline-block;"></i>
              가로수
            </span>
          </div>
          <div style="font-size:11px;color:#687782;margin-top:9px;">
            ※ 색깔이 있는 핀은 지도 데이터에 이름과 분류 정보가 등록된 장소만 표시됩니다.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.info("왼쪽 사이드바에서 도시/주소를 입력하고 ‘도시 불러오기’ 버튼을 눌러 주세요.")
