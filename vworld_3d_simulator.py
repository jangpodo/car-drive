import streamlit as st
import streamlit.components.v1 as components
import requests
import math
import json

st.set_page_config(page_title="3D 도시 운전 시뮬레이터", layout="wide")
st.title("🚗 3D 도시 운전 시뮬레이터")
st.caption("실제 지도 도로·건물 데이터를 바탕으로 구현된 3D 운전 시뮬레이터입니다.")

with st.sidebar:
    place = st.text_input("도시 / 주소 입력", "서울특별시 강남구")
    
    st.markdown("---")
    st.markdown("📌 **추천 도시 입력 예시**")
    st.markdown("- **특별시/광역시:** 서울 강남구, 부산 해운대구")
    st.markdown("- **경기도:** 수원시 팔달구, 성남시 분당구")
    st.markdown("- **강원도:** 강릉시 중앙동, 춘천시")
    st.markdown("- **충청도:** 천안시 서북구, 청주시 흥덕구")
    st.markdown("- **전라도:** 전주시 완산구, 여수시")
    st.markdown("- **경상도:** 경주시, 포항시 북구")
    st.markdown("---")

    radius = st.select_slider(
        "지도 범위 반경",
        options=[400, 600, 800, 1000, 1500],
        value=800,
        format_func=lambda x: f"{x} m"
    )
    load = st.button("도시 불러오기", type="primary")
    st.caption("차량 크기: 약 4.5m × 1.8m (실제 승용차 비율)")

@st.cache_data(ttl=3600, show_spinner=False)
def geocode(q):
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": q, "format": "json", "limit": 1},
        headers={"User-Agent": "Student3DDrivingSimulator/20.0"},
        timeout=25
    )
    response.raise_for_status()
    items = response.json()
    if not items:
        raise ValueError("위치를 찾지 못했습니다. 도시명이나 주소를 더 구체적으로 입력해 주세요.")
    item = items[0]
    return float(item["lat"]), float(item["lon"]), item.get("display_name", q)

@st.cache_data(ttl=3600, show_spinner=False)
def get_osm(lat, lon, radius_m):
    dlat = radius_m / 111320
    dlon = radius_m / (111320 * max(math.cos(math.radians(lat)), 0.2))
    south, west, north, east = lat-dlat, lon-dlon, lat+dlat, lon+dlon

    query = f"""
    [out:json][timeout:90];
    (
      way["highway"~"motorway|trunk|primary|secondary|tertiary|residential|unclassified|living_street|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link"]({south},{west},{north},{east});
      way["building"]({south},{west},{north},{east});
      way["waterway"~"river|canal"]({south},{west},{north},{east});
      way["natural"="water"]({south},{west},{north},{east});
    );
    out body geom;
    """
    last_error = None
    for endpoint in [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter"
    ]:
        try:
            response = requests.post(
                endpoint, data=query,
                headers={"User-Agent": "Student3DDrivingSimulator/20.0"},
                timeout=110
            )
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"OSM 지도 요청 실패: {last_error}")

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

def convert_osm(osm, center_lat, center_lon):
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
            points.append([x, z])

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
                "lanes": tags.get("lanes", "")
            })

        elif "building" in tags and len(points) >= 3:
            try:
                height = float(str(tags.get("height", "")).replace("m", "").strip())
            except (ValueError, TypeError):
                try:
                    levels = float(str(tags.get("building:levels", "3")).split(";")[0])
                    height = levels * 3.2
                except (ValueError, TypeError):
                    height = 10.0
            result["buildings"].append({
                "points": points,
                "height": min(max(height, 3.0), 180.0),
                "levels": tags.get("building:levels", "")
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
            st.session_state.city_data = convert_osm(raw, lat, lon)
            st.session_state.city_label = label
    except Exception as error:
        st.error(f"도시를 불러오지 못했습니다: {error}")

if st.session_state.city_data:
    data = st.session_state.city_data
    st.success(f"📍 {st.session_state.city_label}")
    st.caption(f"도로 {len(data['roads'])}개 · 건물 {len(data['buildings'])}개 · 물길 {len(data['water'])}개")
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
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.min.js"></script>
</head><body><div id="game">
<div id="hud">속도: <span id="speed">0</span> km/h<br><span id="status">준비 중</span><br><span id="cameraLabel">카메라: 3인칭 추적</span></div>
<div id="help">W/S 또는 ↑/↓: 가속·후진<br>A/D 또는 ←/→: 조향<br>마우스 드래그: 카메라 회전<br>휠: 확대·축소<br>C: 추적/자유 카메라</div>
<div id="buttons"><button id="left">◀</button><button id="forward">▲</button><button id="back">▼</button><button id="right">▶</button></div>
<button id="camBtn">카메라 전환 (C)</button>
</div>
<script>
const DATA=__DATA__;
const game=document.getElementById("game");
const statusEl=document.getElementById("status");
const speedEl=document.getElementById("speed");
if(!window.THREE){statusEl.textContent="Three.js 로딩 실패: CDN/인터넷 연결을 확인하세요.";throw new Error("Three.js missing");}

const scene=new THREE.Scene();
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
const riverBedMat=material(0x4a3b2c); 
const riverBankMat=material(0x5a7a55); 
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

// 특정 지점 (x, z)와 가장 가까운 물길 중심선까지의 거리 계산
function getDistanceToWater(x, z){
  let minDist = 9999;
  for(let w of DATA.water){
    let pts = w.points;
    for(let i=0; i<pts.length-1; i++){
      let a = pts[i], b = pts[i+1];
      let vx = b[0]-a[0], vz = b[1]-a[1], l2 = vx*vx + vz*vz;
      let t = l2 ? Math.max(0, Math.min(1, ((x-a[0])*vx + (z-a[1])*vz)/l2)) : 0;
      let cx = a[0] + t*vx, cz = a[1] + t*vz;
      let d = Math.hypot(x-cx, z-cz);
      if(d < minDist) minDist = d;
    }
  }
  return minDist;
}

// [핵심 1] 적응형 타일 분할 (강으로 갈수록 50m -> 25m -> 12.5m -> 6.25m -> 3.125m로 초록 타일이 미세해짐)
function addAdaptiveGroundTile(cx, cz, size){
  const dist = getDistanceToWater(cx, cz);
  const riverBoundary = 8.0; // 강 물길 반지름

  // 강 내부(수역 범위 안)이면 바닥을 생성하지 않고 구멍을 냄
  if(dist < riverBoundary){
    return;
  }

  // 강 경계선근처(거리 25m 이내)인데 타일 크기가 크면 4개의 더 작은 서브 타일로 분할 쪼개기
  if(dist < riverBoundary + 20.0 && size > 3.125){
    const half = size / 2;
    const quarter = size / 4;
    addAdaptiveGroundTile(cx - quarter, cz - quarter, half);
    addAdaptiveGroundTile(cx + quarter, cz - quarter, half);
    addAdaptiveGroundTile(cx - quarter, cz + quarter, half);
    addAdaptiveGroundTile(cx + quarter, cz + quarter, half);
    return;
  }

  // 최종 잘라진 초록색 땅 타일 생성
  const tile = new THREE.Mesh(new THREE.PlaneGeometry(size, size), groundMat);
  tile.rotation.x = -Math.PI/2;
  tile.position.set(cx, -0.01, cz);
  scene.add(tile);
}

function createAdaptiveGround(){
  const baseSize = 50; 
  const range = 1000;
  for(let x = -range; x < range; x += baseSize){
    for(let z = -range; z < range; z += baseSize){
      addAdaptiveGroundTile(x + baseSize/2, z + baseSize/2, baseSize);
    }
  }
}
createAdaptiveGround();

function addSceneryDetails(){
  for(let i=0; i<180; i++){
    let rx = (Math.random() - 0.5) * 1200;
    let rz = (Math.random() - 0.5) * 1200;
    if(getDistanceToWater(rx, rz) > 12.0){
      const grass = new THREE.Mesh(new THREE.DodecahedronGeometry(0.8), grassMat);
      grass.position.set(rx, 0, rz);
      scene.add(grass);
    }
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
  scene.add(new THREE.Mesh(geo,mat));
}

function bankQuad(a1, b1, a2, b2, y1, y2, mat){
  const vertices=new Float32Array([
    a1[0], y1, a1[1],  a2[0], y2, a2[1],  b2[0], y2, b2[1],
    a1[0], y1, a1[1],  b2[0], y2, b2[1],  b1[0], y1, b1[1]
  ]);
  const geo=new THREE.BufferGeometry();
  geo.setAttribute("position",new THREE.BufferAttribute(vertices,3));
  geo.computeVertexNormals();
  scene.add(new THREE.Mesh(geo,mat));
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
      if(isBridge && totalLen > 0){
        yA = getRoadHeightAtDist(segStartDist + t, totalLen, true);
        yB = getRoadHeightAtDist(segStartDist + end, totalLen, true);
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
}

function addTree(x,z){
  const scale = 2.2;
  const trunk=new THREE.Mesh(new THREE.CylinderGeometry(.3*scale,.4*scale,2.5*scale,6),trunkMat);
  trunk.position.set(x, 1.25*scale, z);scene.add(trunk);
  const crown=new THREE.Mesh(new THREE.ConeGeometry(1.5*scale, 3.5*scale, 6),treeMat);
  crown.position.set(x, 3.2*scale, z);scene.add(crown);
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
      const yA = getRoadHeightAtDist(segStart, totalLen, true);
      const yB = getRoadHeightAtDist(curDist, totalLen, true);
      const rail=new THREE.Mesh(new THREE.BoxGeometry(.18,.8,len),material(0x777b7e));
      rail.position.set((a[0]+b[0])/2+nx*offset, (yA+yB)/2 + 0.4, (a[1]+b[1])/2+nz*offset);
      rail.rotation.y=Math.atan2(dx,dz);
      rail.rotation.x = Math.atan2(yB - yA, len);
      scene.add(rail);
    }
  }
}

function getRoadHeightAtDist(dist, totalLen, isBridge){
  if(!isBridge || totalLen <= 0) return 0.035;
  const rampLen = Math.min(15, totalLen * 0.25);
  if(dist < rampLen){
    return 0.035 + (1.8 - 0.035) * (dist / rampLen);
  } else if(dist > totalLen - rampLen){
    return 0.035 + (1.8 - 0.035) * ((totalLen - dist) / rampLen);
  } else {
    return 1.8;
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
    const yA = getRoadHeightAtDist(dStart, totalLen, r.bridge);
    const yB = getRoadHeightAtDist(accum, totalLen, r.bridge);
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
        if(getDistanceToWater(x+nx*off, z+nz*off) > 10) addTree(x+nx*off, z+nz*off);
        if(getDistanceToWater(x-nx*off, z-nz*off) > 10) addTree(x-nx*off, z-nz*off);
      }
    }
  }
}

for(const b of DATA.buildings) drawBuilding(b.points, b.height||10);

// [핵심 2] 파란 물 오브젝트: 차량 크기(4.5m x 2m)의 세분화 블록으로 촘촘히 엮어 강 밖으로 나가지 않게 조절
for(const w of DATA.water){
  for(let i=0;i<w.points.length-1;i++){
    const a = w.points[i], b = w.points[i+1];
    const dx = b[0]-a[0], dz = b[1]-a[1], len = Math.hypot(dx, dz);
    if(len < 0.05) continue;
    const nx = -dz/len, nz = dx/len;
    
    const riverWidth = 7.0; // 강 너비 (정밀 조절)
    const bankWidth = 3.5;  // 둑 너비

    // 강 길이를 차량 크기(약 4.5m) 단위 세그먼트로 잘게 나눔
    const segStep = 4.5;
    for(let s = 0; s < len; s += segStep){
      const sEnd = Math.min(s + segStep, len);
      const segA = [a[0] + (dx/len)*s, a[1] + (dz/len)*s];
      const segB = [a[0] + (dx/len)*sEnd, a[1] + (dz/len)*sEnd];

      // 1. 강바닥 흙 블록 (y = -0.8m)
      roadQuadSloped(segA, segB, riverWidth, riverBedMat, -0.8, -0.8);
      
      // 2. 승용차 크기의 파란색 강물 수면 블록 (y = -0.35m)
      roadQuadSloped(segA, segB, riverWidth - 0.2, waterMat, -0.35, -0.35);

      // 3. 둑 경사면 세분화 블록 (가장자리 밀착)
      const oa1 = [segA[0] + nx * (riverWidth/2 + bankWidth), segA[1] + nz * (riverWidth/2 + bankWidth)];
      const ob1 = [segB[0] + nx * (riverWidth/2 + bankWidth), segB[1] + nz * (riverWidth/2 + bankWidth)];
      const ia1 = [segA[0] + nx * (riverWidth/2), segA[1] + nz * (riverWidth/2)];
      const ib1 = [segB[0] + nx * (riverWidth/2), segB[1] + nz * (riverWidth/2)];
      bankQuad(oa1, ob1, ia1, ib1, 0.0, -0.8, riverBankMat);

      const oa2 = [segA[0] - nx * (riverWidth/2 + bankWidth), segA[1] - nz * (riverWidth/2 + bankWidth)];
      const ob2 = [segB[0] - nx * (riverWidth/2 + bankWidth), segB[1] - nz * (riverWidth/2 + bankWidth)];
      const ia2 = [segA[0] - nx * (riverWidth/2), segA[1] - nz * (riverWidth/2)];
      const ib2 = [segB[0] - nx * (riverWidth/2), segB[1] - nz * (riverWidth/2)];
      bankQuad(oa2, ob2, ia2, ib2, 0.0, -0.8, riverBankMat);
    }
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
  let bridgeY = null;
  let minBridgeDist = 999;
  for(let r of DATA.roads){
    if(!r.bridge) continue;
    let pts = r.points;
    let totalLen = 0;
    let segs = [];
    for(let i=0; i<pts.length-1; i++){
      let l = Math.hypot(pts[i+1][0]-pts[i][0], pts[i+1][1]-pts[i][1]);
      segs.push(l); totalLen += l;
    }
    let accum = 0;
    for(let i=0; i<pts.length-1; i++){
      let a = pts[i], b = pts[i+1], len = segs[i];
      if(len < 0.05) continue;
      let d = distToSeg(x, z, a, b);
      if(d < r.width/2 && d < minBridgeDist){
        minBridgeDist = d;
        let t = 0;
        let vx = b[0]-a[0], vz = b[1]-a[1];
        let l2 = vx*vx + vz*vz;
        if(l2 > 0) t = Math.max(0, Math.min(1, ((x - a[0])*vx + (z - a[1])*vz)/l2));
        bridgeY = getRoadHeightAtDist(accum + t * len, totalLen, true);
      }
      accum += len;
    }
  }
  if(minBridgeDist < 12 && bridgeY !== null) return bridgeY;

  for(let w of DATA.water){
    let pts = w.points;
    for(let i=0; i<pts.length-1; i++){
      let a = pts[i], b = pts[i+1];
      let d = distToSeg(x, z, a, b);
      if(d < 3.5){
        return -0.8;
      } else if(d < 7.0){
        let ratio = (d - 3.5) / 3.5;
        return -0.8 + ratio * 0.8;
      }
    }
  }

  return 0.035;
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
let lastTime=performance.now();
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
}
camera.position.set(start[0],start[1]+5,start[1]-13);
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
