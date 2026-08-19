import * as THREE from "/static/js/vendor/three.module.min.js";
import { OrbitControls } from "/static/js/vendor/OrbitControls.js";

let renderer, scene, camera, controls, root, viewEl, current = null;

const FACADE = {
  涂料: "#d8d2c6",
  石材: "#b9b0a3",
  玻璃幕墙: "#7ea4c4",
  铝板: "#c5ccd3",
  砖墙: "#a45a3a",
};

const STYLE = {
  现代: { wall: "#f4f1ea", floor: "#c4a574", accent: "#3a3f45", sofa: "#6b7280" },
  新中式: { wall: "#f3ead6", floor: "#6b3f24", accent: "#7f1d1d", sofa: "#4b2e2a" },
  简欧: { wall: "#f7f1e4", floor: "#d9c7a2", accent: "#c2a36b", sofa: "#ead9c2" },
};

export function mount(el) {
  viewEl = el;
  renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  el.appendChild(renderer.domElement);
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(45, 1, 0.1, 2000);
  camera.position.set(40, 20, 50);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.target.set(0, 8, 0);
  window.addEventListener("resize", resize);
  resize();
  loop();
}

function resize() {
  if (!viewEl || !renderer) return;
  const w = viewEl.clientWidth || 800;
  const h = viewEl.clientHeight || 600;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}

function loop() {
  requestAnimationFrame(loop);
  controls?.update();
  renderer?.render(scene, camera);
}

export function apply(doc) {
  current = doc;
  clear();
  root = new THREE.Group();
  scene.add(root);
  const night = doc.mode.id === "night" || doc.sun.time === "夜晚";
  scene.background = new THREE.Color(doc.sun.sky);
  scene.fog = new THREE.Fog(doc.sun.sky, night ? 80 : 120, night ? 280 : 420);
  renderer.toneMappingExposure = doc.camera.exposure * (night ? 1.15 : 1);
  lights(doc, night);
  ground(doc);
  if (doc.mode.id === "interior") interior(doc);
  else building(doc, night);
  if (doc.entourage && doc.mode.id !== "interior") entourage(doc);
  placeCamera(doc);
}

function clear() {
  if (root) {
    scene.remove(root);
    root.traverse((o) => {
      if (o.geometry) o.geometry.dispose();
      if (o.material) {
        const ms = Array.isArray(o.material) ? o.material : [o.material];
        ms.forEach((m) => {
          if (m.map) m.map.dispose();
          m.dispose();
        });
      }
    });
  }
  const keep = new Set();
  scene.children.slice().forEach((c) => {
    if (c.isLight) scene.remove(c);
  });
}

function lights(doc, night) {
  const hemi = new THREE.HemisphereLight(night ? "#1a2740" : "#cfe6ff", night ? "#0a0c10" : "#6b5a45", night ? 0.25 : 0.55);
  scene.add(hemi);
  const sun = new THREE.DirectionalLight(kelvin(doc.sun.kelvin), night ? 0.08 : doc.sun.intensity);
  const r = 160;
  const alt = (doc.sun.altitude * Math.PI) / 180;
  const az = (doc.sun.azimuth * Math.PI) / 180;
  sun.position.set(Math.sin(az) * Math.cos(alt) * r, Math.max(2, Math.sin(alt) * r), Math.cos(az) * Math.cos(alt) * r);
  sun.castShadow = !night;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.left = -80;
  sun.shadow.camera.right = 80;
  sun.shadow.camera.top = 80;
  sun.shadow.camera.bottom = -80;
  sun.shadow.camera.far = 400;
  scene.add(sun);
  if (night) {
    const amb = new THREE.AmbientLight("#334466", 0.35);
    scene.add(amb);
  }
}

function kelvin(k) {
  if (k < 4000) return "#ffb070";
  if (k < 5000) return "#ffd5a8";
  return "#fff4e6";
}

function ground(doc) {
  const g = new THREE.Mesh(
    new THREE.CircleGeometry(220, 64),
    new THREE.MeshStandardMaterial({ color: doc.mode.id === "interior" ? "#1a1a1a" : "#4d6b45", roughness: 0.95 })
  );
  g.rotation.x = -Math.PI / 2;
  g.receiveShadow = true;
  root.add(g);
  if (doc.mode.id !== "interior") {
    const road = new THREE.Mesh(
      new THREE.PlaneGeometry(220, 14),
      new THREE.MeshStandardMaterial({ color: "#4b4f55", roughness: 0.85 })
    );
    road.rotation.x = -Math.PI / 2;
    road.position.set(0, 0.03, doc.building.width / 2 + 16);
    road.receiveShadow = true;
    root.add(road);
  }
}

function facadeTex(doc, night) {
  const c = document.createElement("canvas");
  c.width = 512;
  c.height = 1024;
  const g = c.getContext("2d");
  const base = FACADE[doc.building.facade] || "#cfc8bb";
  g.fillStyle = base;
  g.fillRect(0, 0, 512, 1024);
  const curtain = doc.building.facade === "玻璃幕墙";
  const cols = 8;
  const rows = Math.max(6, doc.building.floors);
  const mw = curtain ? 6 : 10;
  g.fillStyle = curtain ? "#1c3148" : "#2a241c";
  if (curtain) {
    g.fillStyle = night ? "#1a2430" : "#5f87a6";
    g.fillRect(0, 0, 512, 1024);
    g.strokeStyle = "#d9e2ea";
    g.lineWidth = 3;
    for (let i = 0; i <= cols; i++) {
      const x = (i / cols) * 512;
      g.beginPath();
      g.moveTo(x, 0);
      g.lineTo(x, 1024);
      g.stroke();
    }
    for (let j = 0; j <= rows; j++) {
      const y = (j / rows) * 1024;
      g.beginPath();
      g.moveTo(0, y);
      g.lineTo(512, y);
      g.stroke();
    }
    if (night) {
      for (let j = 1; j < rows; j++) {
        for (let i = 0; i < cols; i++) {
          if (Math.random() > 0.45) {
            g.fillStyle = Math.random() > 0.2 ? "#f4e2a8" : "#9ad4ff";
            g.fillRect((i / cols) * 512 + 4, (j / rows) * 1024 + 4, 512 / cols - 8, 1024 / rows - 8);
          }
        }
      }
    }
  } else {
    for (let j = 1; j < rows; j++) {
      for (let i = 0; i < cols; i++) {
        const x = (i + 0.18) * (512 / cols);
        const y = (j + 0.22) * (1024 / rows);
        const ww = 512 / cols - mw * 2;
        const hh = 1024 / rows - mw * 2.4;
        if (night && Math.random() > 0.5) g.fillStyle = "#f2d98a";
        else g.fillStyle = "#7ea7c9";
        g.fillRect(x, y, ww, hh);
      }
    }
  }
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 8;
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  return tex;
}

function building(doc, night) {
  const L = doc.building.length;
  const W = doc.building.width;
  const H = doc.building.height;
  const pod = doc.building.podium_h || 0;
  const tex = facadeTex(doc, night);
  const mat = new THREE.MeshStandardMaterial({
    map: tex,
    roughness: doc.building.facade === "玻璃幕墙" ? 0.12 : 0.7,
    metalness: doc.building.facade === "玻璃幕墙" ? 0.35 : 0.05,
    emissive: night ? new THREE.Color("#221800") : new THREE.Color("#000"),
    emissiveIntensity: night ? 0.25 : 0,
  });
  if (pod) {
    const p = new THREE.Mesh(new THREE.BoxGeometry(L + 10, pod, W + 8), new THREE.MeshStandardMaterial({ color: "#d9d3c7", roughness: 0.8 }));
    p.position.y = pod / 2;
    p.castShadow = p.receiveShadow = true;
    root.add(p);
  }
  const box = new THREE.Mesh(new THREE.BoxGeometry(L, H - pod, W), mat);
  box.position.y = pod + (H - pod) / 2;
  box.castShadow = box.receiveShadow = true;
  root.add(box);
  const roof = new THREE.Mesh(new THREE.BoxGeometry(L + 0.6, 1.2, W + 0.6), new THREE.MeshStandardMaterial({ color: "#8a9098", roughness: 0.85 }));
  roof.position.y = H + 0.4;
  roof.castShadow = true;
  root.add(roof);
  if (doc.mode.id === "siteplan" || doc.mode.id === "aerial") {
    const wing = new THREE.Mesh(new THREE.BoxGeometry(L * 0.45, H * 0.55, W * 0.7), mat);
    wing.position.set(L * 0.7, H * 0.28, W * 0.8);
    wing.castShadow = true;
    root.add(wing);
  }
}

function interior(doc) {
  const st = STYLE[doc.interior.style] || STYLE.现代;
  const room = 10, depth = 7, h = 3.1;
  const wall = new THREE.MeshStandardMaterial({ color: st.wall, roughness: 0.85 });
  const floor = new THREE.Mesh(new THREE.BoxGeometry(room, 0.08, depth), new THREE.MeshStandardMaterial({ color: st.floor, roughness: 0.45 }));
  floor.position.y = 0.04;
  floor.receiveShadow = true;
  root.add(floor);
  const ceil = new THREE.Mesh(new THREE.BoxGeometry(room, 0.08, depth), new THREE.MeshStandardMaterial({ color: "#f7f7f5", roughness: 0.9 }));
  ceil.position.y = h;
  root.add(ceil);
  const walls = [
    [new THREE.BoxGeometry(room, h, 0.12), 0, h / 2, -depth / 2],
    [new THREE.BoxGeometry(0.12, h, depth), -room / 2, h / 2, 0],
    [new THREE.BoxGeometry(0.12, h, depth), room / 2, h / 2, 0],
  ];
  walls.forEach(([geo, x, y, z]) => {
    const m = new THREE.Mesh(geo, wall);
    m.position.set(x, y, z);
    m.castShadow = m.receiveShadow = true;
    root.add(m);
  });
  const glass = new THREE.Mesh(
    new THREE.PlaneGeometry(4.8, 2.2),
    new THREE.MeshPhysicalMaterial({ color: "#9ec9e8", roughness: 0.05, transmission: 0.55, thickness: 0.2, opacity: 0.85, transparent: true })
  );
  glass.position.set(0, 1.45, depth / 2 - 0.08);
  root.add(glass);
  const frame = new THREE.Mesh(new THREE.BoxGeometry(5.2, 2.5, 0.16), new THREE.MeshStandardMaterial({ color: st.accent, roughness: 0.4 }));
  frame.position.set(0, 1.45, depth / 2 - 0.12);
  root.add(frame);
  sofa(0, 0.4, -0.6, st.sofa);
  table(0, 0.35, 1.1, st.accent);
  plant(-3.6, 0, 1.8, st.accent);
  const lamp = new THREE.PointLight("#ffd9a8", 18, 12);
  lamp.position.set(0, 2.7, 0);
  lamp.castShadow = true;
  root.add(lamp);
  const sunIn = new THREE.PointLight("#fff1d6", 8, 16);
  sunIn.position.set(0, 1.6, depth / 2 - 0.4);
  root.add(sunIn);
  const kind = doc.interior.room;
  if (kind === "办公室" || kind === "教室") {
    for (let i = -1; i <= 1; i++) desk(i * 2.4, 0, 0.6, st);
  }
  if (kind === "大堂" || kind === "门厅") {
    const rec = new THREE.Mesh(new THREE.BoxGeometry(3.2, 1.1, 0.8), new THREE.MeshStandardMaterial({ color: st.accent, roughness: 0.35 }));
    rec.position.set(0, 0.55, -2.2);
    rec.castShadow = true;
    root.add(rec);
  }
}

function sofa(x, y, z, color) {
  const m = new THREE.MeshStandardMaterial({ color, roughness: 0.7 });
  const base = new THREE.Mesh(new THREE.BoxGeometry(2.6, 0.45, 1.0), m);
  base.position.set(x, y, z);
  base.castShadow = true;
  root.add(base);
  const back = new THREE.Mesh(new THREE.BoxGeometry(2.6, 0.7, 0.22), m);
  back.position.set(x, y + 0.5, z - 0.4);
  back.castShadow = true;
  root.add(back);
}

function table(x, y, z, color) {
  const top = new THREE.Mesh(new THREE.BoxGeometry(1.3, 0.08, 0.7), new THREE.MeshStandardMaterial({ color, roughness: 0.35 }));
  top.position.set(x, y, z);
  top.castShadow = true;
  root.add(top);
}

function plant(x, y, z) {
  const pot = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.22, 0.3, 12), new THREE.MeshStandardMaterial({ color: "#6b3f24" }));
  pot.position.set(x, y + 0.15, z);
  root.add(pot);
  const leaf = new THREE.Mesh(new THREE.SphereGeometry(0.45, 16, 12), new THREE.MeshStandardMaterial({ color: "#2f6b3a", roughness: 0.8 }));
  leaf.position.set(x, y + 0.7, z);
  leaf.castShadow = true;
  root.add(leaf);
}

function desk(x, y, z, st) {
  const t = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.06, 0.7), new THREE.MeshStandardMaterial({ color: st.floor, roughness: 0.4 }));
  t.position.set(x, 0.75, z);
  t.castShadow = true;
  root.add(t);
  const seat = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.45, 0.45), new THREE.MeshStandardMaterial({ color: st.sofa }));
  seat.position.set(x, 0.35, z + 0.7);
  root.add(seat);
}

function entourage(doc) {
  const L = doc.building.length;
  const W = doc.building.width;
  for (let i = -5; i <= 5; i++) {
    tree(L / 2 + 8, 0, i * 6);
    tree(-L / 2 - 8, 0, i * 6);
  }
  for (let i = -3; i <= 3; i++) {
    car(i * 6, 0.4, W / 2 + 16);
  }
}

function tree(x, y, z) {
  const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.25, 1.6, 8), new THREE.MeshStandardMaterial({ color: "#5a3a22" }));
  trunk.position.set(x, y + 0.8, z);
  trunk.castShadow = true;
  root.add(trunk);
  const crown = new THREE.Mesh(new THREE.SphereGeometry(1.3, 12, 10), new THREE.MeshStandardMaterial({ color: "#2e6b38", roughness: 0.9 }));
  crown.position.set(x, y + 2.3, z);
  crown.castShadow = true;
  root.add(crown);
}

function car(x, y, z) {
  const body = new THREE.Mesh(new THREE.BoxGeometry(4.2, 1.2, 1.8), new THREE.MeshStandardMaterial({ color: "#334155", metalness: 0.4, roughness: 0.35 }));
  body.position.set(x, y, z);
  body.castShadow = true;
  root.add(body);
}

function placeCamera(doc) {
  const L = doc.building.length;
  const W = doc.building.width;
  const H = doc.building.height;
  const id = doc.mode.id;
  const fov = doc.camera.fov_deg;
  if (id === "siteplan") {
    const aspect = (viewEl.clientWidth || 16) / (viewEl.clientHeight || 9);
    const fr = Math.max(L, W) * 1.4;
    camera = new THREE.OrthographicCamera(-fr * aspect, fr * aspect, fr, -fr, 0.1, 2000);
    camera.position.set(L * 0.9, H * 2.2, W * 1.1);
    camera.lookAt(0, 0, 0);
  } else {
    camera = new THREE.PerspectiveCamera(fov, (viewEl.clientWidth || 16) / (viewEl.clientHeight || 9), 0.1, 2000);
    let from, to;
    if (id === "interior") {
      from = new THREE.Vector3(0, doc.camera.height_m, 2.8);
      to = new THREE.Vector3(0, 1.45, -1.2);
    } else if (id === "aerial") {
      from = new THREE.Vector3(L * 1.4, Math.max(doc.camera.height_m, H * 1.6), W * 1.6);
      to = new THREE.Vector3(0, H * 0.2, 0);
    } else {
      from = new THREE.Vector3(L * 0.85, doc.camera.height_m, W * 1.35 + 18);
      to = new THREE.Vector3(0, doc.camera.two_point ? doc.camera.height_m : H * 0.45, 0);
    }
    camera.position.copy(from);
    camera.lookAt(to);
    if (doc.camera.two_point && (id === "exterior" || id === "night" || id === "interior")) {
      camera.rotation.z = 0;
    }
  }
  if (controls) {
    controls.dispose();
  }
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.target.set(0, id === "interior" ? 1.4 : H * 0.35, id === "interior" ? -0.5 : 0);
  controls.update();
  resize();
}

export function capturePng(width, height, filename) {
  const vw = viewEl.clientWidth;
  const vh = viewEl.clientHeight;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  if (camera.isOrthographicCamera) {
    const fr = Math.max(current.building.length, current.building.width) * 1.4;
    camera.left = -fr * camera.aspect;
    camera.right = fr * camera.aspect;
    camera.top = fr;
    camera.bottom = -fr;
  }
  camera.updateProjectionMatrix();
  renderer.render(scene, camera);
  const url = renderer.domElement.toDataURL("image/png");
  renderer.setSize(vw, vh, false);
  camera.aspect = vw / vh;
  camera.updateProjectionMatrix();
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "效果图.png";
  a.click();
}
