import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="3D 운전 교실", page_icon="🚗", layout="wide")
st.title("🚗 3D 운전 교실")
st.caption("가상 도로에서 자동차를 운전해 보세요.")
st.markdown("**W/S:** 전진·후진　 **A/D:** 좌회전·우회전　 **마우스 드래그:** 시점 회전　 **마우스 휠:** 줌　 **스페이스:** 정지")

html = r"""
<!doctype html><html lang="ko"><head><meta charset="utf-8">
<style>
html,body{margin:0;overflow:hidden;background:#b9d9ef;font-family:Arial}
#game{width:100%;height:690px}
#hud{position:absolute;top:12px;left:12px;padding:10px 14px;background:#172638d9;color:white;border-radius:9px;line-height:1.6;pointer-events:none}
#help{position:absolute;bottom:12px;right:12px;padding:8px 12px;background:#172638c9;color:white;border-radius:8px;font-size:12px;pointer-events:none}
#error{display:none;color:white;background:#263442;padding:20px}
</style></head><body>
<div id="game"></div><div id="hud">속도 <span id="speed">0</span> km/h<br>방향 <span id="dir">북쪽</span></div>
<div id="help">WASD 운전 · 마우스 드래그 시점 회전 · 휠 줌 · 스페이스 정지</div><div id="error"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
(()=>{
const err=document.getElementById('error');
if(!window.THREE){err.style.display='block';err.textContent='3D 라이브러리를 불러오지 못했습니다. 인터넷 연결을 확인해 주세요.';return;}
const T=THREE, root=document.getElementById('game'), scene=new T.Scene();
scene.background=new T.Color(0xb9d9ef);scene.fog=new T.Fog(0xb9d9ef,70,220);
const camera=new T.PerspectiveCamera(62,root.clientWidth/690,.1,500);
const renderer=new T.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio||1,2));renderer.setSize(root.clientWidth,690);renderer.shadowMap.enabled=true;root.appendChild(renderer.domElement);
scene.add(new T.HemisphereLight(0xffffff,0x687b62,1.25));
const sun=new T.DirectionalLight(0xffffff,1.2);sun.position.set(-35,65,25);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);scene.add(sun);
const material=(c,r=.85)=>new T.MeshStandardMaterial({color:c,roughness:r});
function block(parent,w,h,d,m,x,y,z){const o=new T.Mesh(new T.BoxGeometry(w,h,d),m);o.position.set(x,y,z);o.castShadow=true;o.receiveShadow=true;parent.add(o);return o;}
const grass=material(0x6d9d61),road=material(0x343b43),side=material(0xb9b9b2),white=material(0xf4f1df),yellow=material(0xf5df8a);
const floor=new T.Mesh(new T.PlaneGeometry(500,500),grass);floor.rotation.x=-Math.PI/2;floor.position.y=-.12;floor.receiveShadow=true;scene.add(floor);
block(scene,15,.08,230,road,0,-.035,0);block(scene,230,.08,15,road,0,-.034,0);
block(scene,2,.18,230,side,-9,.02,0);block(scene,2,.18,230,side,9,.02,0);
block(scene,230,.18,2,side,0,.02,-9);block(scene,230,.18,2,side,0,.02,9);
for(let n=-105;n<=105;n+=12){block(scene,.16,.025,5,yellow,0,.025,n);block(scene,5,.025,.16,yellow,n,.025,0);}
for(let n=-5;n<=5;n++){block(scene,1,.025,5.5,white,n*1.25,.03,-10.5);block(scene,5.5,.025,1,white,10.5,.03,n*1.25);}
const colors=[0xd9c7ad,0xc4d4dc,0xe0b9a8,0xd4d0bd,0xb9c8b2,0xd2c1dc];
for(let x=-5;x<=5;x++)for(let z=-5;z<=5;z++){
 if(Math.abs(x)<=1||Math.abs(z)<=1)continue;
 const bx=x*27+(Math.random()-.5)*4,bz=z*27+(Math.random()-.5)*4,w=10+Math.random()*5,d=10+Math.random()*5,h=8+Math.random()*23;
 block(scene,w,h,d,material(colors[Math.floor(Math.random()*colors.length)]),bx,h/2,bz);
 const win=material(0x8eb6c7,.35);
 for(let yy=3;yy<h-1;yy+=4)for(let xx=-w/2+1.5;xx<w/2-1;xx+=3)block(scene,.9,1,.07,win,bx+xx,yy,bz-d/2-.04);
}
const trunk=material(0x765034),leaves=material(0x397c45);
for(let z=-95;z<=95;z+=19)for(const x of [-13,13]){
 const t=new T.Mesh(new T.CylinderGeometry(.22,.3,2.4,8),trunk);t.position.set(x,1.1,z);scene.add(t);
 const c=new T.Mesh(new T.SphereGeometry(1.4,10,8),leaves);c.position.set(x,3,z);scene.add(c);
}
// 단순한 자동차 모델
const car=new T.Group();scene.add(car);
const paint=material(0xd93636,.38),dark=material(0x20252b,.45),glass=material(0x8fc5d8,.2),lamp=new T.MeshStandardMaterial({color:0xfff2c4,emissive:0x554422});
block(car,2.25,.62,4.25,paint,0,.85,0);block(car,1.82,.9,2.05,paint,0,1.55,-.35);
block(car,1.68,.68,1.85,glass,0,1.62,-.35);block(car,2.05,.16,1.05,dark,0,1.13,1.25);
block(car,.42,.18,.12,lamp,-.72,.95,2.14);block(car,.42,.18,.12,lamp,.72,.95,2.14);
const wheelGeo=new T.CylinderGeometry(.48,.48,.32,20);
for(const x of [-1.12,1.12])for(const z of [-1.35,1.35]){const w=new T.Mesh(wheelGeo,dark);w.rotation.z=Math.PI/2;w.position.set(x,.52,z);car.add(w);}
car.position.set(0,0,0);
const keys={};let speed=0,yaw=0,orbit=0,pitch=.22,distance=10,drag=false,lx=0,ly=0;
addEventListener('keydown',e=>{if(['KeyW','KeyA','KeyS','KeyD','Space','ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.code))e.preventDefault();keys[e.code]=true;if(e.code==='Space')speed=0;});
addEventListener('keyup',e=>keys[e.code]=false);
renderer.domElement.addEventListener('pointerdown',e=>{drag=true;lx=e.clientX;ly=e.clientY;renderer.domElement.setPointerCapture(e.pointerId);});
renderer.domElement.addEventListener('pointerup',()=>drag=false);
renderer.domElement.addEventListener('pointermove',e=>{if(!drag)return;orbit-=(e.clientX-lx)*.006;pitch=Math.max(-.05,Math.min(.85,pitch+(e.clientY-ly)*.004));lx=e.clientX;ly=e.clientY;});
renderer.domElement.addEventListener('wheel',e=>distance=Math.max(5,Math.min(22,distance+e.deltaY*.012)),{passive:true});
const clock=new T.Clock(),speedText=document.getElementById('speed'),dirText=document.getElementById('dir');
function animate(){requestAnimationFrame(animate);const dt=Math.min(clock.getDelta()*60,2.2);
 if(keys.KeyW||keys.ArrowUp)speed=Math.min(.34,speed+.012*dt);else if(keys.KeyS||keys.ArrowDown)speed=Math.max(-.19,speed-.012*dt);else speed*=Math.pow(.985,dt);
 if(keys.KeyA||keys.ArrowLeft)yaw+=.035*dt*(speed<-.01?-1:1);if(keys.KeyD||keys.ArrowRight)yaw-=.035*dt*(speed<-.01?-1:1);
 car.rotation.y=yaw;car.position.x=Math.max(-105,Math.min(105,car.position.x+Math.sin(yaw)*speed*dt));car.position.z=Math.max(-105,Math.min(105,car.position.z+Math.cos(yaw)*speed*dt));
 const a=yaw+orbit,h=distance*Math.cos(pitch);camera.position.set(car.position.x-Math.sin(a)*h,2.2+distance*Math.sin(pitch),car.position.z-Math.cos(a)*h);camera.lookAt(car.position.x,1,car.position.z);
 speedText.textContent=Math.round(Math.abs(speed)*120);const dirs=['북쪽','북동쪽','동쪽','남동쪽','남쪽','남서쪽','서쪽','북서쪽'];dirText.textContent=dirs[Math.round((((yaw*180/Math.PI)%360+360)%360)/45)%8];renderer.render(scene,camera);
}animate();
addEventListener('resize',()=>{camera.aspect=root.clientWidth/690;camera.updateProjectionMatrix();renderer.setSize(root.clientWidth,690);});
})();
</script></body></html>
"""
components.html(html, height=710, scrolling=False)
