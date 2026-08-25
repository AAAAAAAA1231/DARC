(() => {
  "use strict";

  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");
  const W = 1280;
  const H = 720;
  const FLOOR = 590;
  const SAVE_KEY = "qianlong-web3-unlock";
  const MAX_HP = 5;
  const MAX_LIVES = 3;
  const WEAPON_NAME = { fire: "龙息", spread: "散弹", laser: "ZK束" };

  const LEVELS = [
    { id: "ETH", name: "ETH · 创世主网", desc: "教学关。跑跳射击，打掉关底 Gas 巨像。", hint: "A D 跑  空格跳  J/鼠标开火  W向上打", accent: "#627eea", bgTop: "#0a1024", bgBot: "#05070f", pits: 2, walkers: 8, flyers: 4, turrets: 2, capsules: 2, movers: 0, lasers: 0, pads: 0, proofs: 0, boss: "golem", bossHp: 16 },
    { id: "ARB", name: "ARB · Nitro 工厂", desc: "移动平台与更快的 Sequencer 火力。", hint: "踩住移动平台，别掉进 Inbox 深坑", accent: "#12aaff", bgTop: "#07141c", bgBot: "#03080c", pits: 4, walkers: 10, flyers: 6, turrets: 4, capsules: 3, movers: 4, lasers: 0, pads: 0, proofs: 0, boss: "sequencer", bossHp: 22 },
    { id: "ZK", name: "ZK · 零知识电路", desc: "收集 5 枚证明，才能打开 Boss 闸门。", hint: "先捡齐发光证明，闸门才会打开", accent: "#8b5cf6", bgTop: "#140a22", bgBot: "#07040e", pits: 3, walkers: 9, flyers: 5, turrets: 4, capsules: 2, movers: 1, lasers: 0, pads: 0, proofs: 5, boss: "circuit", bossHp: 24 },
    { id: "STARK", name: "STARK · 多项式风暴", desc: "间歇激光扫过航线，找空隙突击。", hint: "红色激光会周期性开关，看准了再冲", accent: "#ec796b", bgTop: "#1a0d0a", bgBot: "#0b0605", pits: 3, walkers: 11, flyers: 7, turrets: 3, capsules: 3, movers: 2, lasers: 6, pads: 0, proofs: 0, boss: "serpent", bossHp: 26 },
    { id: "L0", name: "L0 · 跨链之桥", desc: "踩上传送垫可换航道，小心报文炮。", hint: "青色垫子会把你弹到另一段桥", accent: "#b4ff4d", bgTop: "#0b140c", bgBot: "#050805", pits: 5, walkers: 10, flyers: 6, turrets: 4, capsules: 3, movers: 3, lasers: 1, pads: 4, proofs: 0, boss: "warden", bossHp: 28 },
    { id: "BASE", name: "BASE · 链上盛夏", desc: "终章火力最密，用散弹清场打蓝鲸。", hint: "终章 · 打掉胶囊换武器，留足跳跃", accent: "#4d8bff", bgTop: "#071028", bgBot: "#040814", pits: 4, walkers: 12, flyers: 8, turrets: 5, capsules: 4, movers: 3, lasers: 2, pads: 2, proofs: 0, boss: "whale", bossHp: 32 },
  ];

  const $ = (id) => document.getElementById(id);
  const screens = {
    menu: $("screen-menu"),
    select: $("screen-select"),
    help: $("screen-help"),
    pause: $("screen-pause"),
    dead: $("screen-dead"),
    clear: $("screen-clear"),
  };

  const input = {
    left: false, right: false, up: false, down: false,
    jump: false, jumpHeld: false, fire: false,
    stickX: 0, touching: false,
  };

  const rand = (a, b) => a + Math.random() * (b - a);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const aabb = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;

  function rng(seed) {
    let s = (seed + 11) | 0;
    return () => {
      s = (s * 16807) % 2147483647;
      return (s - 1) / 2147483646;
    };
  }

  function loadUnlock() {
    return clamp(Number(localStorage.getItem(SAVE_KEY) || "1"), 1, LEVELS.length);
  }
  function saveUnlock(n) {
    if (n > loadUnlock()) localStorage.setItem(SAVE_KEY, String(n));
  }

  let audio, audioReady = false;
  function ensureAudio() {
    if (audioReady) return;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    audio = new AC();
    audioReady = true;
  }
  function beep(freq, dur, type, vol, slide) {
    if (!audioReady || !audio) return;
    const o = audio.createOscillator();
    const g = audio.createGain();
    o.type = type || "square";
    o.frequency.value = freq;
    if (slide) o.frequency.exponentialRampToValueAtTime(Math.max(40, slide), audio.currentTime + dur);
    g.gain.value = vol || 0.04;
    g.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + dur);
    o.connect(g).connect(audio.destination);
    o.start();
    o.stop(audio.currentTime + dur);
  }
  const sfx = {
    shoot: () => beep(480, 0.07, "sawtooth", 0.03, 190),
    hit: () => beep(200, 0.09, "square", 0.04, 80),
    collect: () => beep(700, 0.1, "sine", 0.05, 1100),
    jump: () => beep(300, 0.08, "triangle", 0.03, 180),
    hurt: () => beep(130, 0.2, "sawtooth", 0.07, 50),
    win: () => { beep(523, 0.1, "sine", 0.05); setTimeout(() => beep(784, 0.2, "sine", 0.06), 140); },
    lose: () => beep(180, 0.4, "triangle", 0.06, 70),
  };

  let state = "menu";
  let levelIndex = 0;
  let level = LEVELS[0];
  let t = 0;
  let camX = 0;
  let shake = 0;
  let score = 0;
  let tokens = 0;
  let proofs = 0;
  let hintTimer = 0;
  let lockCam = false;
  let worldW = 5200;
  let plats = [];
  let enemies = [];
  let items = [];
  let hazards = [];
  let bullets = [];
  let ebullets = [];
  let particles = [];
  let stars = [];
  let boss = null;
  let gate = null;
  let exitDoor = null;
  let checkpoint = { x: 90, y: FLOOR };
  let checkXs = [];

  const player = {
    x: 90, y: FLOOR, vx: 0, vy: 0,
    hp: MAX_HP, lives: MAX_LIVES, inv: 0,
    face: 1, onGround: false, duck: false,
    fireCd: 0, jumpBuf: 0, coyote: 0, wing: true,
    weapon: "fire", runT: 0,
  };

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function hideAllScreens() {
    Object.values(screens).forEach((el) => el.classList.add("hidden"));
  }
  function syncHud() {
    $("hud").classList.toggle("hidden", state !== "play" && state !== "pause");
    const isTouch = window.matchMedia("(pointer: coarse)").matches || window.innerWidth <= 900;
    $("touch").classList.toggle("hidden", !(isTouch && state === "play"));
  }

  function burst(x, y, color, n, spd) {
    for (let i = 0; i < n; i++) {
      const a = rand(0, Math.PI * 2);
      const s = rand(30, spd || 220);
      particles.push({ x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s, life: rand(0.2, 0.6), max: 0.6, r: rand(1.4, 3.2), color });
    }
  }

  function pRect() {
    const duck = player.duck && player.onGround;
    const h = duck ? 26 : 44;
    const w = 26;
    return { x: player.x - w / 2, y: player.y - h, w, h };
  }

  function makeStars() {
    stars = Array.from({ length: 90 }, () => ({ x: Math.random() * W, y: Math.random() * H, z: rand(0.2, 1.3), r: rand(0.6, 2) }));
  }

  function generateWorld(lv, index) {
    const R = rng(index * 131 + 17);
    worldW = 5400;
    plats = [];
    enemies = [];
    items = [];
    hazards = [];
    bullets = [];
    ebullets = [];
    particles = [];
    boss = null;
    gate = null;
    exitDoor = null;
    lockCam = false;

    const arena = worldW - 780;
    let x = 0;
    let pitsMade = 0;
    while (x < arena) {
      const startSafe = x < 760;
      const wantPit = !startSafe && pitsMade < lv.pits && R() < 0.2;
      if (wantPit) {
        const pitW = 90 + R() * 70;
        plats.push({ x: x + pitW * 0.15, y: FLOOR - 100 - R() * 50, w: 86 + R() * 40, h: 18, kind: "plat" });
        x += pitW;
        pitsMade += 1;
      } else {
        const w = Math.min(260 + R() * 300, arena - x);
        plats.push({ x, y: FLOOR, w, h: H - FLOOR, kind: "ground" });
        if (!startSafe && R() < 0.5) {
          plats.push({ x: x + 30 + R() * 80, y: FLOOR - 108 - R() * 55, w: 70 + R() * 80, h: 16, kind: "plat" });
        }
        x += w;
      }
    }
    plats.push({ x: arena - 20, y: FLOOR, w: worldW - arena + 40, h: H - FLOOR, kind: "ground" });

    for (let i = 0; i < lv.movers; i++) {
      const mx = 900 + (i + 1) * ((arena - 1200) / (lv.movers + 1));
      plats.push({
        x: mx, y: FLOOR - 150 - (i % 2) * 40, w: 110, h: 16, kind: "move",
        bx: mx, range: 80 + R() * 50, phase: R() * 6, dx: 0,
      });
    }

    const easy = lv.id === "ETH";
    const grounds = plats.filter((p) => p.kind === "ground" && p.w > 180 && p.x > 820 && p.x < arena - 200);
    if (!grounds.length) {
      plats.push({ x: 900, y: FLOOR, w: 600, h: H - FLOOR, kind: "ground" });
      grounds.push(plats[plats.length - 1]);
    }
    for (let i = 0; i < lv.walkers; i++) {
      const g = grounds[i % grounds.length];
      enemies.push({
        type: "walker", x: g.x + 60 + (i * 47) % Math.max(40, g.w - 80), y: g.y,
        hp: 2, dir: R() < 0.5 ? -1 : 1, shootCd: easy ? 99 : 0.8 + R(), r: 16, w: 28, h: 34, silent: easy,
      });
    }
    const airs = plats.filter((p) => p.kind !== "ground" && p.x > 900);
    for (let i = 0; i < lv.turrets; i++) {
      const p = airs.length ? airs[i % airs.length] : plats[0];
      enemies.push({
        type: "turret", x: p.x + p.w * 0.5, y: p.y, hp: 4, shootCd: easy ? 2.4 + R() : 0.4 + R(), r: 16, w: 30, h: 24,
      });
    }
    for (let i = 0; i < lv.flyers; i++) {
      enemies.push({
        type: "flyer", x: 1100 + i * 380 + R() * 80, y: 160 + R() * 180,
        hp: 1, phase: R() * 6, homeY: 180 + R() * 160, shootCd: easy ? 99 : 1 + R(), r: 14, w: 24, h: 18, silent: easy,
      });
    }
    for (let i = 0; i < lv.capsules; i++) {
      enemies.push({
        type: "capsule", x: 800 + i * 900, y: 150 + (i % 2) * 70,
        hp: 1, phase: i, r: 14, w: 28, h: 16, drop: i % 2 ? "spread" : "laser",
      });
    }
    for (let i = 0; i < lv.proofs; i++) {
      const g = grounds[(i + 2) % grounds.length];
      items.push({ type: "proof", x: g.x + g.w * 0.55, y: g.y - 28, r: 14 });
    }
    for (let i = 0; i < 12; i++) {
      const g = grounds[i % grounds.length];
      items.push({ type: "token", x: g.x + 40 + (i * 90) % Math.max(30, g.w - 60), y: g.y - 24, r: 10 });
    }
    items.push({ type: "heart", x: 1800, y: FLOOR - 26, r: 12 });
    items.push({ type: "heart", x: 3200, y: FLOOR - 26, r: 12 });

    for (let i = 0; i < lv.lasers; i++) {
      const lx = 1000 + i * ((arena - 1400) / Math.max(1, lv.lasers));
      hazards.push({ type: "laser", x: lx, y0: 80, y1: FLOOR, period: 1.6 + R() * 0.6, phase: R() * 2, on: false });
    }
    for (let i = 0; i < lv.pads; i += 2) {
      const a = 1100 + i * 700;
      const b = a + 420;
      hazards.push({ type: "pad", x: a, y: FLOOR - 10, w: 54, h: 12, tx: b + 27, ty: FLOOR, cool: 0 });
      hazards.push({ type: "pad", x: b, y: FLOOR - 10, w: 54, h: 12, tx: a + 27, ty: FLOOR, cool: 0 });
    }

    if (lv.proofs) {
      gate = { x: arena - 30, y: 120, w: 28, h: FLOOR - 120, closed: true };
    }

    boss = {
      type: lv.boss, x: worldW - 280, y: FLOOR, hp: lv.bossHp, max: lv.bossHp,
      w: 90, h: 90, face: -1, shootCd: 1, phase: 0, active: false, alive: true, hurtT: 0,
    };
    checkXs = [90, worldW * 0.28, worldW * 0.52, worldW * 0.74];
  }

  function startLevel(index) {
    levelIndex = index;
    level = LEVELS[index];
    generateWorld(level, index);
    state = "play";
    t = 0;
    camX = 0;
    shake = 0;
    score = 0;
    tokens = 0;
    proofs = 0;
    hintTimer = 6;
    player.x = 90;
    player.y = FLOOR;
    player.vx = 0;
    player.vy = 0;
    player.hp = MAX_HP;
    player.lives = MAX_LIVES;
    player.inv = 2.2;
    player.face = 1;
    player.weapon = "fire";
    player.wing = true;
    player.fireCd = 0;
    checkpoint = { x: 90, y: FLOOR };
    hideAllScreens();
    syncHud();
    $("hud-level-name").textContent = level.name;
    $("hud-hint").textContent = level.hint;
    $("hud-hint").classList.remove("hidden");
    updateHud();
    ensureAudio();
  }

  function respawn() {
    player.x = checkpoint.x;
    player.y = checkpoint.y;
    player.vx = 0;
    player.vy = 0;
    player.hp = MAX_HP;
    player.inv = 2;
    player.wing = true;
    burst(player.x, player.y - 20, "#4de2c8", 16, 200);
  }

  function die() {
    player.lives -= 1;
    if (player.lives <= 0) {
      player.lives = 0;
      state = "dead";
      sfx.lose();
      $("dead-text").textContent = `${level.name} 失败。分数 ${score}`;
      screens.dead.classList.remove("hidden");
      syncHud();
      return;
    }
    respawn();
    updateHud();
  }

  function winLevel() {
    state = "clear";
    sfx.win();
    saveUnlock(levelIndex + 2);
    const next = LEVELS[levelIndex + 1];
    $("clear-eyebrow").textContent = level.id + " CLEAR";
    $("clear-title").textContent = level.name + " 通关";
    $("clear-text").textContent = next
      ? `分数 ${score} · 代币 ${tokens}。下一关 ${next.name}`
      : `全链通关！分数 ${score}。潜龙已经打穿 Web3。`;
    $("btn-next").style.display = next ? "" : "none";
    screens.clear.classList.remove("hidden");
    syncHud();
    renderLevelGrid();
  }

  function updateHud() {
    const hearts = $("hud-hearts");
    hearts.innerHTML = "";
    for (let i = 0; i < MAX_HP; i++) {
      const d = document.createElement("i");
      d.className = "heart" + (i < player.hp ? "" : " empty");
      hearts.appendChild(d);
    }
    $("hud-tokens").textContent = String(tokens);
    $("hud-score").textContent = String(score);
    $("hud-lives").textContent = String(Math.max(0, player.lives));
    $("hud-weapon").textContent = WEAPON_NAME[player.weapon] || "龙息";
    const p = clamp(player.x / worldW, 0, 1);
    $("hud-bar").style.width = (p * 100).toFixed(1) + "%";
    if (level.proofs) $("hud-special").textContent = `证明 ${proofs}/${level.proofs}`;
    else if (boss && boss.active) $("hud-special").textContent = `BOSS ${Math.max(0, boss.hp)}/${boss.max}`;
    else $("hud-special").textContent = "";
  }

  function groundedAt(px, py) {
    const probe = { x: px - 6, y: py, w: 12, h: 8 };
    return plats.some((p) => aabb(probe, p));
  }

  function aimVector() {
    let dx = 0;
    let dy = 0;
    if (input.left || input.stickX < -0.35) dx -= 1;
    if (input.right || input.stickX > 0.35) dx += 1;
    if (input.up) dy -= 1;
    if (input.down && !player.onGround) dy += 1;
    if (dx === 0 && dy === 0) dx = player.face;
    if (dx === 0 && input.up) dy = -1;
    if (dx !== 0) player.face = dx;
    const len = Math.hypot(dx, dy) || 1;
    return { x: dx / len, y: dy / len };
  }

  function shoot() {
    if (player.fireCd > 0) return;
    const aim = aimVector();
    const duck = player.duck && player.onGround;
    const mx = player.x + aim.x * 24;
    const my = player.y - (duck ? 14 : 30) + aim.y * 8;
    const base = Math.atan2(aim.y, aim.x);
    const add = (ang, spd, pierce, r, life) => {
      bullets.push({ x: mx, y: my, vx: Math.cos(ang) * spd, vy: Math.sin(ang) * spd, r, life: life || 0.9, pierce, hit: new Set() });
    };
    if (player.weapon === "spread") {
      player.fireCd = 0.2;
      add(base - 0.34, 620, 0, 5);
      add(base, 660, 0, 5);
      add(base + 0.34, 620, 0, 5);
    } else if (player.weapon === "laser") {
      player.fireCd = 0.08;
      add(base, 920, 5, 3.5, 0.7);
    } else {
      player.fireCd = 0.14;
      add(base, 700, 0, 6);
    }
    burst(mx, my, "#ffb15a", 3, 70);
    sfx.shoot();
  }

  function hurt() {
    if (player.inv > 0) return;
    player.hp -= 1;
    player.inv = 1.05;
    shake = 8;
    burst(player.x, player.y - 20, "#ff6b7a", 14, 240);
    sfx.hurt();
    if (player.hp <= 0) die();
  }

  function updatePlats(dt) {
    for (const p of plats) {
      if (p.kind !== "move") continue;
      const old = p.x;
      p.phase += dt;
      p.x = p.bx + Math.sin(p.phase) * p.range;
      p.dx = p.x - old;
    }
  }

  function movePlayer(dt) {
    let mx = 0;
    if (input.left) mx -= 1;
    if (input.right) mx += 1;
    if (input.touching) mx += input.stickX;
    mx = clamp(mx, -1, 1);
    player.duck = input.down && player.onGround && Math.abs(mx) < 0.2;
    const spd = player.duck ? 0 : 270;
    player.vx = mx * spd;
    if (mx) player.face = Math.sign(mx);
    player.runT += Math.abs(mx) * dt * 10;

    player.jumpBuf = input.jump ? 0.12 : Math.max(0, player.jumpBuf - dt);
    if (player.onGround) {
      player.coyote = 0.1;
      player.wing = true;
    } else player.coyote = Math.max(0, player.coyote - dt);

    if (player.jumpBuf > 0 && player.coyote > 0) {
      player.vy = -640;
      player.onGround = false;
      player.jumpBuf = 0;
      player.coyote = 0;
      sfx.jump();
    } else if (player.jumpBuf > 0 && player.wing && !player.onGround) {
      player.vy = -480;
      player.wing = false;
      player.jumpBuf = 0;
      burst(player.x, player.y, "#4de2c8", 8, 120);
      sfx.jump();
    }
    if (!input.jumpHeld && player.vy < 0) player.vy += 2400 * dt;

    player.vy += 1750 * dt;
    player.vy = Math.min(player.vy, 980);

    const prev = pRect();
    player.x += player.vx * dt;
    let r = pRect();
    for (const p of plats) {
      if (!aabb(r, p)) continue;
      if (player.vx > 0) player.x = p.x - r.w / 2 - 0.1;
      else if (player.vx < 0) player.x = p.x + p.w + r.w / 2 + 0.1;
      r = pRect();
    }

    player.y += player.vy * dt;
    r = pRect();
    player.onGround = false;
    let ride = null;
    for (const p of plats) {
      if (!aabb(r, p)) continue;
      if (player.vy >= 0 && prev.y + prev.h <= p.y + 10) {
        player.y = p.y;
        player.vy = 0;
        player.onGround = true;
        ride = p;
        r = pRect();
      } else if (player.vy < 0 && prev.y >= p.y + p.h - 10) {
        player.y = p.y + p.h + r.h + 0.1;
        player.vy = 0;
        r = pRect();
      }
    }
    if (ride && ride.kind === "move") player.x += ride.dx;
    player.x = clamp(player.x, 16, worldW - 16);
    if (player.y > H + 40) die();

    for (const cx of checkXs) {
      if (player.onGround && player.x > cx && checkpoint.x < cx - 10) {
        checkpoint = { x: player.x, y: player.y };
      }
    }
  }

  function enemyRect(e) {
    if (e.type === "walker") return { x: e.x - e.w / 2, y: e.y - e.h, w: e.w, h: e.h };
    if (e.type === "turret") return { x: e.x - e.w / 2, y: e.y - e.h, w: e.w, h: e.h };
    return { x: e.x - e.w / 2, y: e.y - e.h / 2, w: e.w, h: e.h };
  }

  function fireAt(x, y, tx, ty, spd) {
    const a = Math.atan2(ty - y, tx - x);
    ebullets.push({ x, y, vx: Math.cos(a) * spd, vy: Math.sin(a) * spd, r: 6, life: 3 });
  }

  function updateEnemies(dt) {
    for (const e of enemies) {
      if (e.type === "walker") {
        e.x += e.dir * 80 * dt;
        if (!groundedAt(e.x + e.dir * 18, e.y) || e.x < 40) e.dir *= -1;
        e.shootCd -= dt;
        if (!e.silent && e.shootCd <= 0 && Math.abs(player.x - e.x) < 460) {
          e.shootCd = 1.6;
          fireAt(e.x, e.y - 22, player.x, player.y - 24, 280);
        }
      } else if (e.type === "turret") {
        e.shootCd -= dt;
        if (e.shootCd <= 0 && Math.abs(player.x - e.x) < 560) {
          e.shootCd = 1.25;
          fireAt(e.x, e.y - 18, player.x, player.y - 28, 320);
        }
      } else if (e.type === "flyer") {
        e.phase += dt;
        e.x -= 70 * dt;
        e.y = e.homeY + Math.sin(e.phase * 2.2) * 36;
        e.shootCd -= dt;
        if (!e.silent && e.shootCd <= 0 && Math.abs(player.x - e.x) < 500) {
          e.shootCd = 2;
          fireAt(e.x, e.y, player.x, player.y - 20, 260);
        }
      } else if (e.type === "capsule") {
        e.phase += dt;
        e.x += Math.sin(e.phase) * 20 * dt;
        e.y += Math.cos(e.phase * 1.3) * 18 * dt;
      }
    }

    for (const b of ebullets) {
      b.x += b.vx * dt;
      b.y += b.vy * dt;
      b.life -= dt;
    }
    ebullets = ebullets.filter((b) => b.life > 0 && b.x > camX - 40 && b.x < camX + W + 40);

    for (const b of bullets) {
      b.x += b.vx * dt;
      b.y += b.vy * dt;
      b.life -= dt;
    }
    bullets = bullets.filter((b) => b.life > 0);

    for (const b of bullets) {
      for (const e of enemies) {
        if (e.hp <= 0) continue;
        const r = enemyRect(e);
        if (b.x > r.x && b.x < r.x + r.w && b.y > r.y && b.y < r.y + r.h) {
          if (b.hit.has(e)) continue;
          b.hit.add(e);
          e.hp -= 1;
          burst(b.x, b.y, level.accent, 6, 140);
          sfx.hit();
          if (b.pierce <= 0) b.life = 0;
          else b.pierce -= 1;
          if (e.hp <= 0) {
            score += e.type === "capsule" ? 10 : 40;
            burst(e.x, e.y - 10, "#fff3c4", 14, 220);
            if (e.type === "capsule") {
              items.push({ type: "weapon", x: e.x, y: e.y, r: 12, weapon: e.drop });
            }
          }
        }
      }
      if (boss && boss.alive && boss.active) {
        const r = { x: boss.x - boss.w / 2, y: boss.y - boss.h, w: boss.w, h: boss.h };
        if (b.x > r.x && b.x < r.x + r.w && b.y > r.y && b.y < r.y + r.h) {
          if (!b.hit.has(boss)) {
            b.hit.add(boss);
            boss.hp -= 1;
            boss.hurtT = 0.12;
            b.life = b.pierce > 0 ? b.life : 0;
            score += 15;
            burst(b.x, b.y, "#fff", 8, 160);
            sfx.hit();
            if (boss.hp <= 0) {
              boss.alive = false;
              score += 400;
              burst(boss.x, boss.y - 40, level.accent, 40, 360);
              exitDoor = { x: worldW - 90, y: FLOOR - 80, r: 48 };
            }
          }
        }
      }
    }
    enemies = enemies.filter((e) => e.hp > 0 && e.x > camX - 120);

    const pr = pRect();
    for (const e of enemies) {
      if (aabb(pr, enemyRect(e)) && e.type !== "capsule") hurt();
    }
    for (const b of ebullets) {
      if (b.x > pr.x && b.x < pr.x + pr.w && b.y > pr.y && b.y < pr.y + pr.h) {
        b.life = 0;
        hurt();
      }
    }
  }

  function updateBoss(dt) {
    if (!boss || !boss.alive) return;
    if (!boss.active && player.x > worldW - 760) boss.active = true;
    if (!boss.active) return;
    lockCam = true;
    boss.phase += dt;
    boss.shootCd -= dt;
    boss.hurtT = Math.max(0, boss.hurtT - dt);
    const targetX = worldW - 260 + Math.sin(boss.phase) * 40;
    boss.x = lerp(boss.x, targetX, 0.03);
    if (boss.type === "golem" || boss.type === "whale") {
      boss.y = FLOOR - Math.max(0, Math.sin(boss.phase * 2) * 18);
    } else if (boss.type === "serpent") {
      boss.y = FLOOR - 40 - Math.abs(Math.sin(boss.phase * 1.4)) * 90;
    } else if (boss.type === "warden" && Math.floor(boss.phase * 0.5) !== Math.floor((boss.phase - dt) * 0.5)) {
      boss.x = worldW - 200 - Math.random() * 220;
    }
    if (boss.shootCd <= 0) {
      boss.shootCd = boss.type === "sequencer" ? 0.7 : 1.05;
      const n = boss.type === "whale" || boss.type === "sequencer" ? 5 : 3;
      for (let i = 0; i < n; i++) {
        const a = Math.PI + (i - (n - 1) / 2) * 0.28;
        ebullets.push({
          x: boss.x - 20, y: boss.y - 50,
          vx: Math.cos(a) * 300, vy: Math.sin(a) * 300,
          r: 7, life: 4,
        });
      }
    }
    const r = { x: boss.x - boss.w / 2, y: boss.y - boss.h, w: boss.w, h: boss.h };
    if (aabb(pRect(), r)) hurt();
  }

  function updateHazards(dt) {
    if (gate) {
      gate.closed = proofs < level.proofs;
      if (gate.closed) {
        const r = { x: gate.x, y: gate.y, w: gate.w, h: gate.h };
        const pr = pRect();
        if (aabb(pr, r) && player.x > gate.x) player.x = gate.x - pr.w / 2 - 1;
      }
    }
    for (const h of hazards) {
      if (h.type === "laser") {
        h.phase += dt;
        h.on = (h.phase % h.period) < h.period * 0.45;
        if (h.on && player.x > h.x - 10 && player.x < h.x + 10 && player.y > h.y0) hurt();
      } else if (h.type === "pad") {
        h.cool = Math.max(0, h.cool - dt);
        const r = { x: h.x, y: h.y, w: h.w, h: h.h + 8 };
        if (h.cool <= 0 && aabb(pRect(), r)) {
          player.x = h.tx;
          player.y = h.ty - 20;
          player.vy = -220;
          for (const p of hazards) if (p.type === "pad") p.cool = 1;
          burst(player.x, player.y - 20, "#b4ff4d", 16, 180);
          sfx.collect();
        }
      }
    }
    for (const it of items) {
      if (Math.hypot(player.x - it.x, player.y - 20 - it.y) < 28) {
        it.dead = true;
        if (it.type === "token") { tokens += 1; score += 15; }
        if (it.type === "proof") {
          proofs += 1;
          score += 60;
          if (proofs >= level.proofs) {
            $("hud-hint").textContent = "证明已齐 · 闸门打开，去打 Boss";
            $("hud-hint").classList.remove("hidden");
            hintTimer = 3.5;
          }
        }
        if (it.type === "heart") player.hp = clamp(player.hp + 1, 0, MAX_HP);
        if (it.type === "weapon") player.weapon = it.weapon;
        sfx.collect();
        burst(it.x, it.y, "#f0c36a", 8, 120);
      }
    }
    items = items.filter((it) => !it.dead);

    if (exitDoor && Math.hypot(player.x - exitDoor.x, player.y - 40 - exitDoor.y) < 50) winLevel();
  }

  function update(dt) {
    t += dt;
    if (state !== "play") return;
    if (hintTimer > 0) {
      hintTimer -= dt;
      if (hintTimer <= 0) $("hud-hint").classList.add("hidden");
    }
    player.inv = Math.max(0, player.inv - dt);
    player.fireCd = Math.max(0, player.fireCd - dt);
    shake = Math.max(0, shake - dt * 18);
    if (input.fire) shoot();

    updatePlats(dt);
    movePlayer(dt);
    if (state !== "play") return;
    updateEnemies(dt);
    if (state !== "play") return;
    updateBoss(dt);
    updateHazards(dt);
    if (state !== "play") return;

    for (const p of particles) {
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.life -= dt;
    }
    particles = particles.filter((p) => p.life > 0);

    const target = lockCam ? worldW - W : player.x - 300;
    camX = lerp(camX, clamp(target, 0, Math.max(0, worldW - W)), 0.12);

    input.jump = false;
    updateHud();
  }

  function roundRect(x, y, w, h, r) {
    const rr = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + rr, y);
    ctx.arcTo(x + w, y, x + w, y + h, rr);
    ctx.arcTo(x + w, y + h, x, y + h, rr);
    ctx.arcTo(x, y + h, x, y, rr);
    ctx.arcTo(x, y, x + w, y, rr);
    ctx.closePath();
  }

  function drawBg() {
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, level.bgTop);
    g.addColorStop(1, level.bgBot);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = "#d7e7ff";
    for (const s of stars) {
      s.x -= s.z * 12 * 0.016;
      if (s.x < 0) s.x += W;
      ctx.globalAlpha = 0.2 + s.z * 0.5;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    ctx.fillStyle = level.accent + "14";
    ctx.font = "900 140px sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(level.id, W - 36, 150);
    const par = -camX * 0.2;
    ctx.strokeStyle = level.accent + "22";
    for (let i = 0; i < 8; i++) {
      ctx.beginPath();
      ctx.moveTo(par + i * 220, 80);
      ctx.lineTo(par + i * 220 + 120, FLOOR);
      ctx.stroke();
    }
  }

  function drawWorld() {
    ctx.save();
    ctx.translate(-camX, 0);

    for (const p of plats) {
      if (p.kind === "ground") {
        const dirt = ctx.createLinearGradient(0, p.y, 0, p.y + p.h);
        dirt.addColorStop(0, "#2a3d62");
        dirt.addColorStop(0.08, "#151e33");
        dirt.addColorStop(1, "#080b14");
        ctx.fillStyle = dirt;
        ctx.fillRect(p.x, p.y, p.w, p.h);
        ctx.fillStyle = level.accent;
        ctx.fillRect(p.x, p.y, p.w, 7);
        ctx.fillStyle = level.accent + "55";
        for (let gx = p.x; gx < p.x + p.w; gx += 28) ctx.fillRect(gx, p.y + 10, 14, 3);
      } else {
        ctx.fillStyle = "#2c3f64";
        ctx.strokeStyle = level.accent;
        ctx.lineWidth = 2;
        roundRect(p.x, p.y, p.w, p.h, 6);
        ctx.fill();
        ctx.stroke();
      }
    }

    for (const h of hazards) {
      if (h.type === "laser" && h.on) {
        ctx.strokeStyle = "#ff5d4a";
        ctx.shadowColor = "#ff5d4a";
        ctx.shadowBlur = 12;
        ctx.lineWidth = 6;
        ctx.beginPath();
        ctx.moveTo(h.x, h.y0);
        ctx.lineTo(h.x, h.y1);
        ctx.stroke();
        ctx.shadowBlur = 0;
      } else if (h.type === "pad") {
        ctx.fillStyle = "#b4ff4d";
        roundRect(h.x, h.y, h.w, h.h, 4);
        ctx.fill();
      }
    }

    if (gate && gate.closed) {
      ctx.fillStyle = "rgba(139,92,246,0.55)";
      ctx.fillRect(gate.x, gate.y, gate.w, gate.h);
      ctx.fillStyle = "#e9d5ff";
      ctx.font = "11px sans-serif";
      ctx.fillText("ZK GATE", gate.x - 8, gate.y - 8);
    }

    for (const it of items) {
      if (it.type === "token") {
        ctx.fillStyle = "#f0c36a";
        ctx.beginPath();
        ctx.arc(it.x, it.y, it.r, 0, Math.PI * 2);
        ctx.fill();
      } else if (it.type === "proof") {
        ctx.fillStyle = "rgba(139,92,246,0.4)";
        ctx.strokeStyle = "#c4b5fd";
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
          const a = t * 2 + i * Math.PI / 3;
          const fn = i ? ctx.lineTo : ctx.moveTo;
          fn.call(ctx, it.x + Math.cos(a) * it.r, it.y + Math.sin(a) * it.r);
        }
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      } else if (it.type === "heart") {
        ctx.fillStyle = "#e25b6a";
        ctx.beginPath();
        ctx.arc(it.x - 5, it.y, 6, 0, Math.PI * 2);
        ctx.arc(it.x + 5, it.y, 6, 0, Math.PI * 2);
        ctx.fill();
      } else if (it.type === "weapon") {
        ctx.fillStyle = it.weapon === "laser" ? "#67e8f9" : "#fb923c";
        roundRect(it.x - 12, it.y - 10, 24, 20, 4);
        ctx.fill();
        ctx.fillStyle = "#111";
        ctx.font = "bold 10px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(it.weapon === "laser" ? "L" : "S", it.x, it.y + 4);
      }
    }

    for (const e of enemies) {
      if (e.type === "walker") {
        ctx.fillStyle = "#ff5d73";
        roundRect(e.x - 14, e.y - 34, 28, 34, 4);
        ctx.fill();
        ctx.fillStyle = "#2a0a10";
        ctx.fillRect(e.x - 6, e.y - 26, 12, 8);
      } else if (e.type === "turret") {
        ctx.fillStyle = "#94a3b8";
        ctx.fillRect(e.x - 15, e.y - 24, 30, 24);
        ctx.fillStyle = "#e2e8f0";
        ctx.fillRect(e.x - 26, e.y - 16, 16, 8);
      } else if (e.type === "flyer") {
        ctx.fillStyle = "#7dd3fc";
        ctx.beginPath();
        ctx.moveTo(e.x + 14, e.y);
        ctx.lineTo(e.x - 12, e.y - 8);
        ctx.lineTo(e.x - 12, e.y + 8);
        ctx.closePath();
        ctx.fill();
      } else if (e.type === "capsule") {
        ctx.fillStyle = "#ef4444";
        roundRect(e.x - 14, e.y - 8, 28, 16, 8);
        ctx.fill();
        ctx.fillStyle = "#fff";
        ctx.font = "bold 10px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("S", e.x, e.y + 3);
      }
    }

    if (boss && boss.alive) {
      ctx.save();
      ctx.globalAlpha = boss.hurtT > 0 ? 0.5 : 1;
      ctx.fillStyle = level.accent;
      roundRect(boss.x - boss.w / 2, boss.y - boss.h, boss.w, boss.h, 12);
      ctx.fill();
      ctx.fillStyle = "#071018";
      ctx.fillRect(boss.x - 18, boss.y - 70, 14, 14);
      ctx.fillRect(boss.x + 4, boss.y - 70, 14, 14);
      ctx.fillStyle = "#fff";
      ctx.font = "bold 12px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(boss.type.toUpperCase(), boss.x, boss.y - boss.h - 10);
      ctx.fillStyle = "#1a1a1a";
      ctx.fillRect(boss.x - 40, boss.y - boss.h - 24, 80, 6);
      ctx.fillStyle = "#ef4444";
      ctx.fillRect(boss.x - 40, boss.y - boss.h - 24, 80 * clamp(boss.hp / boss.max, 0, 1), 6);
      ctx.restore();
    }

    if (exitDoor) {
      ctx.save();
      ctx.translate(exitDoor.x, exitDoor.y);
      ctx.rotate(t * 1.5);
      ctx.strokeStyle = level.accent;
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.ellipse(0, 0, 36, 20, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
      ctx.fillStyle = "#fff";
      ctx.font = "bold 12px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("EXIT", exitDoor.x, exitDoor.y + 36);
    }

    for (const b of ebullets) {
      ctx.fillStyle = "#ff8a5b";
      ctx.beginPath();
      ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
      ctx.fill();
    }
    for (const b of bullets) {
      ctx.fillStyle = player.weapon === "laser" ? "#67e8f9" : "#ffd089";
      ctx.beginPath();
      ctx.arc(b.x, b.y, b.r + 1, 0, Math.PI * 2);
      ctx.fill();
    }
    for (const p of particles) {
      ctx.globalAlpha = p.life / p.max;
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    drawHero();
    ctx.restore();
  }

  function drawHero() {
    const blink = player.inv > 0 && Math.sin(t * 28) > 0 ? 0.35 : 1;
    ctx.save();
    ctx.translate(player.x, player.y);
    ctx.scale(player.face * 1.2, 1.2);
    ctx.globalAlpha = blink;
    const duck = player.duck && player.onGround;
    const flap = player.onGround ? 0.15 : 0.55 + Math.sin(t * 16) * 0.2;
    ctx.fillStyle = "#148f86";
    ctx.beginPath();
    ctx.moveTo(-4, -28);
    ctx.quadraticCurveTo(-10, -28 - 40 * flap, 18, -24 - 36 * flap);
    ctx.quadraticCurveTo(2, -28, -4, -22);
    ctx.fill();

    ctx.fillStyle = "#2ee6c8";
    roundRect(-12, duck ? -26 : -42, 24, duck ? 26 : 42, 8);
    ctx.fill();
    ctx.fillStyle = "#f3d48a";
    ctx.beginPath();
    ctx.ellipse(10, duck ? -20 : -36, 12, 10, 0.1, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#12202a";
    ctx.beginPath();
    ctx.arc(14, duck ? -22 : -38, 2.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#4de2c8";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(-12, -16);
    ctx.quadraticCurveTo(-28, -10 + Math.sin(t * 8) * 4, -34, -6);
    ctx.stroke();
    if (player.onGround && Math.abs(player.vx) > 20) {
      ctx.fillStyle = "#0b3b40";
      const step = Math.sin(player.runT) * 6;
      ctx.fillRect(-8, -8, 7, 10 + step);
      ctx.fillRect(2, -8, 7, 10 - step);
    }
    ctx.restore();
    ctx.globalAlpha = 1;
  }

  function draw() {
    ctx.save();
    if (shake > 0) ctx.translate(rand(-shake, shake), rand(-shake, shake));
    if (state === "menu" || state === "select" || state === "help") {
      drawBg();
      player.x = 360;
      player.y = FLOOR - 8;
      player.face = 1;
      player.onGround = true;
      player.duck = false;
      player.inv = 0;
      player.runT = t * 6;
      player.vx = 80;
      camX = 0;
      drawHero();
      ctx.fillStyle = "rgba(5,8,16,0.15)";
      ctx.fillRect(0, 0, W, H);
    } else {
      drawBg();
      drawWorld();
    }
    ctx.restore();
  }

  let last = performance.now();
  function loop(now) {
    const dt = clamp((now - last) / 1000, 0, 0.05);
    last = now;
    update(dt);
    draw();
    requestAnimationFrame(loop);
  }

  function renderLevelGrid() {
    const grid = $("level-grid");
    grid.innerHTML = "";
    const unlocked = loadUnlock();
    LEVELS.forEach((lv, i) => {
      const locked = i >= unlocked;
      const card = document.createElement("button");
      card.className = "card" + (locked ? " locked" : "");
      card.style.borderColor = lv.accent + "66";
      card.innerHTML = `<div class="id" style="color:${lv.accent}">${lv.id}</div>
        <div class="name">${lv.name}</div>
        <div class="desc">${lv.desc}</div>
        ${locked ? '<div class="lock">通关上一关后解锁</div>' : ""}`;
      card.addEventListener("click", () => {
        if (i >= loadUnlock()) return;
        ensureAudio();
        startLevel(i);
      });
      grid.appendChild(card);
    });
  }

  function goMenu() {
    state = "menu";
    hideAllScreens();
    screens.menu.classList.remove("hidden");
    syncHud();
  }

  function bind() {
    const setKey = (e, down) => {
      const k = e.key.toLowerCase();
      if (k === "a" || k === "arrowleft") input.left = down;
      if (k === "d" || k === "arrowright") input.right = down;
      if (k === "w" || k === "arrowup") input.up = down;
      if (k === "s" || k === "arrowdown") input.down = down;
      if (k === " " || k === "k") {
        if (down && !input.jumpHeld) input.jump = true;
        input.jumpHeld = down;
        e.preventDefault();
      }
      if (k === "j" || k === "f") input.fire = down;
      if (down && k === "enter" && state === "menu") {
        ensureAudio();
        startLevel(0);
      }
      if (down && (k === "p" || k === "escape")) {
        if (state === "play") {
          state = "pause";
          screens.pause.classList.remove("hidden");
          syncHud();
        } else if (state === "pause") {
          state = "play";
          screens.pause.classList.add("hidden");
          syncHud();
        }
      }
    };
    window.addEventListener("keydown", (e) => setKey(e, true));
    window.addEventListener("keyup", (e) => setKey(e, false));
    window.addEventListener("mousedown", (e) => {
      if (state === "play" && e.button === 0) input.fire = true;
    });
    window.addEventListener("mouseup", () => { input.fire = false; });

    const stickZone = $("stick-zone");
    const readStick = (ev) => {
      const rect = stickZone.getBoundingClientRect();
      const touch = ev.touches[0];
      input.stickX = clamp((touch.clientX - rect.left) / rect.width * 2 - 1, -1, 1);
      input.touching = true;
    };
    stickZone.addEventListener("touchstart", (e) => { readStick(e); e.preventDefault(); }, { passive: false });
    stickZone.addEventListener("touchmove", (e) => { readStick(e); e.preventDefault(); }, { passive: false });
    stickZone.addEventListener("touchend", () => { input.touching = false; input.stickX = 0; });
    $("fire-btn").addEventListener("touchstart", (e) => { input.fire = true; e.preventDefault(); }, { passive: false });
    $("fire-btn").addEventListener("touchend", () => { input.fire = false; });
    $("jump-btn").addEventListener("touchstart", (e) => { input.jump = true; input.jumpHeld = true; e.preventDefault(); }, { passive: false });
    $("jump-btn").addEventListener("touchend", () => { input.jumpHeld = false; });

    $("btn-start").addEventListener("click", () => { ensureAudio(); startLevel(0); });
    $("btn-select").addEventListener("click", () => {
      renderLevelGrid();
      hideAllScreens();
      screens.select.classList.remove("hidden");
      state = "select";
    });
    $("btn-help").addEventListener("click", () => {
      hideAllScreens();
      screens.help.classList.remove("hidden");
      state = "help";
    });
    $("btn-select-back").addEventListener("click", goMenu);
    $("btn-help-back").addEventListener("click", goMenu);
    $("btn-resume").addEventListener("click", () => {
      state = "play";
      screens.pause.classList.add("hidden");
      syncHud();
    });
    $("btn-pause-menu").addEventListener("click", goMenu);
    $("btn-retry").addEventListener("click", () => startLevel(levelIndex));
    $("btn-dead-select").addEventListener("click", () => {
      renderLevelGrid();
      hideAllScreens();
      screens.select.classList.remove("hidden");
      state = "select";
      syncHud();
    });
    $("btn-dead-menu").addEventListener("click", goMenu);
    $("btn-next").addEventListener("click", () => {
      if (levelIndex + 1 < LEVELS.length) startLevel(levelIndex + 1);
      else goMenu();
    });
    $("btn-clear-retry").addEventListener("click", () => startLevel(levelIndex));
    $("btn-clear-menu").addEventListener("click", goMenu);
  }

  resize();
  window.addEventListener("resize", resize);
  makeStars();
  renderLevelGrid();
  bind();
  goMenu();
  requestAnimationFrame(loop);
})();
