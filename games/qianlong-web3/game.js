(() => {
  "use strict";

  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");
  const W = 1280;
  const H = 720;
  const FLOOR = 590;
  const SAVE_KEY = "qianlong-web3-unlock";
  const MAX_HP = 4;
  const MAX_LIVES = 3;
  const WEAPON_NAME = { rifle: "步枪", machine: "机枪", spread: "散弹", laser: "激光", flame: "龙焰" };

  const LEVELS = [
    { id: "ETH", name: "ETH · 创世基地", desc: "教学闯关。连射清兵，中段坦克，关底 Gas 巨像。", hint: "按住 J 连射 · 空格跳 · 打红胶囊换枪", accent: "#627eea", bgTop: "#0a1024", bgBot: "#05070f", proofs: 0, boss: "golem", bossHp: 28 },
    { id: "ARB", name: "ARB · Nitro 工厂", desc: "移动平台、管道火力，Boss 是 Sequencer。", hint: "踩住移动平台，机枪清管道炮", accent: "#12aaff", bgTop: "#07141c", bgBot: "#03080c", proofs: 0, boss: "sequencer", bossHp: 34 },
    { id: "ZK", name: "ZK · 电路要塞", desc: "走高台收集 4 枚证明，才能打开 Boss 闸门。", hint: "高路上有证明 · 凑齐后闸门打开", accent: "#8b5cf6", bgTop: "#140a22", bgBot: "#07040e", proofs: 4, boss: "circuit", bossHp: 36 },
    { id: "STARK", name: "STARK · 激光防线", desc: "间歇激光网，找空隙突击多项式巨蛇。", hint: "激光会开关，看准空隙再冲", accent: "#ec796b", bgTop: "#1a0d0a", bgBot: "#0b0605", proofs: 0, boss: "serpent", bossHp: 38 },
    { id: "L0", name: "L0 · 跨链大桥", desc: "传送垫换航道，桥上坦克和报文炮更密。", hint: "踩青垫传送 · 别在桥缝里掉下去", accent: "#b4ff4d", bgTop: "#0b140c", bgBot: "#050805", proofs: 0, boss: "warden", bossHp: 40 },
    { id: "BASE", name: "BASE · 链上盛夏", desc: "终章弹幕最密，用散弹/激光打蓝鲸。", hint: "终章 · 换好武器再进 Boss 房", accent: "#4d8bff", bgTop: "#071028", bgBot: "#040814", proofs: 0, boss: "whale", bossHp: 46 },
  ];

  const $ = (id) => document.getElementById(id);
  const screens = {
    menu: $("screen-menu"), select: $("screen-select"), help: $("screen-help"),
    pause: $("screen-pause"), dead: $("screen-dead"), clear: $("screen-clear"),
  };
  const input = {
    left: false, right: false, up: false, down: false,
    jump: false, jumpHeld: false, fire: false, stickX: 0, touching: false,
  };

  const rand = (a, b) => a + Math.random() * (b - a);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const aabb = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;

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
    g.gain.value = vol || 0.035;
    g.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + dur);
    o.connect(g).connect(audio.destination);
    o.start();
    o.stop(audio.currentTime + dur);
  }
  const sfx = {
    shoot: () => beep(620, 0.045, "square", 0.025, 240),
    hit: () => beep(190, 0.07, "square", 0.04, 70),
    boom: () => beep(110, 0.18, "sawtooth", 0.05, 40),
    collect: () => beep(740, 0.1, "sine", 0.05, 1200),
    jump: () => beep(310, 0.07, "triangle", 0.025, 170),
    hurt: () => beep(120, 0.22, "sawtooth", 0.07, 45),
    win: () => { beep(523, 0.1, "sine", 0.05); setTimeout(() => beep(784, 0.2, "sine", 0.06), 140); },
    lose: () => beep(170, 0.4, "triangle", 0.06, 60),
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
  let worldW = 5800;
  let plats = [];
  let enemies = [];
  let items = [];
  let hazards = [];
  let bullets = [];
  let ebullets = [];
  let particles = [];
  let explosions = [];
  let floats = [];
  let decos = [];
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
    weapon: "rifle", runT: 0, muzzle: 0,
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
      const s = rand(40, spd || 220);
      particles.push({ x, y, vx: Math.cos(a) * s, vy: Math.sin(a) * s, life: rand(0.2, 0.55), max: 0.55, r: rand(1.4, 3.4), color });
    }
  }
  function boom(x, y, r) {
    explosions.push({ x, y, r: r || 36, life: 0.32, max: 0.32 });
    burst(x, y, "#ffb15a", 18, 280);
    sfx.boom();
  }
  function pop(x, y, text) {
    floats.push({ x, y, text, life: 0.7 });
  }
  function pRect() {
    const duck = player.duck && player.onGround;
    const h = duck ? 26 : 46;
    return { x: player.x - 14, y: player.y - h, w: 28, h };
  }
  function makeStars() {
    stars = Array.from({ length: 90 }, () => ({ x: Math.random() * W, y: Math.random() * H, z: rand(0.2, 1.3), r: rand(0.6, 2) }));
  }

  function addGround(x, w) {
    plats.push({ x, y: FLOOR, w, h: H - FLOOR, kind: "ground" });
  }
  function addPlat(x, y, w, kind) {
    plats.push({ x, y, w, h: 18, kind: kind || "plat", bx: x, range: 70, phase: rand(0, 6), dx: 0 });
  }
  function addSoldier(x, y, silent) {
    enemies.push({ type: "soldier", x, y: y || FLOOR, hp: 2, dir: -1, shootCd: rand(0.4, 1.2), silent: !!silent, w: 26, h: 36, hop: 0, phase: rand(0, 6) });
  }
  function addJumper(x, y) {
    enemies.push({ type: "jumper", x, y: y || FLOOR, hp: 2, dir: 1, shootCd: 1, w: 24, h: 28, phase: rand(0, 4) });
  }
  function addTurret(x, y) {
    enemies.push({ type: "turret", x, y, hp: 4, shootCd: rand(0.2, 1), w: 32, h: 26 });
  }
  function addSniper(x, y) {
    enemies.push({ type: "sniper", x, y, hp: 3, shootCd: 0.8, w: 24, h: 34 });
  }
  function addFlyer(x, y, silent) {
    enemies.push({ type: "flyer", x, y, hp: 1, phase: rand(0, 6), homeY: y, shootCd: rand(0.6, 1.6), silent: !!silent, w: 26, h: 16 });
  }
  function addCapsule(x, y, drop) {
    enemies.push({ type: "capsule", x, y, homeY: y, hp: 1, phase: 0, w: 30, h: 16, drop });
  }
  function addTank(x) {
    enemies.push({ type: "tank", x, y: FLOOR, hp: 10, shootCd: 0.8, dir: -1, w: 70, h: 44, phase: 0 });
  }
  function addCoins(x, n, y) {
    for (let i = 0; i < n; i++) items.push({ type: "token", x: x + i * 36, y: y || FLOOR - 24, r: 9 });
  }

  function buildStage(lv) {
    plats = []; enemies = []; items = []; hazards = []; bullets = []; ebullets = [];
    particles = []; explosions = []; floats = []; decos = [];
    boss = null; gate = null; exitDoor = null; lockCam = false;
    const easy = lv.id === "ETH";
    const id = lv.id;
    let x = 0;

    addGround(0, 1040);
    addCoins(240, 5);
    addCoins(520, 3, FLOOR - 24);
    if (easy) addSoldier(720, FLOOR, true);
    x = 1040;

    addPlat(x + 40, FLOOR - 118, 96);
    if (id === "ARB") addPlat(x + 30, FLOOR - 118, 110, "move");
    addCoins(x + 50, 2, FLOOR - 140);
    x += 170;
    addGround(x, 820);
    addSoldier(x + 180, FLOOR, easy);
    addSoldier(x + 320, FLOOR, easy);
    addJumper(x + 520);
    addPlat(x + 240, FLOOR - 130, 140);
    addSniper(x + 300, FLOOR - 130);
    addCapsule(x + 400, 168, "spread");
    x += 820;

    addGround(x, 980);
    addPlat(x + 80, FLOOR - 120, 220);
    addPlat(x + 280, FLOOR - 210, 240);
    addCoins(x + 300, 4, FLOOR - 236);
    addSoldier(x + 140, FLOOR, false);
    addSoldier(x + 430, FLOOR, false);
    addJumper(x + 620);
    if (lv.proofs) items.push({ type: "proof", x: x + 380, y: FLOOR - 236, r: 14 });
    addTurret(x + 400, FLOOR - 210);
    addFlyer(x + 700, 210, easy);
    if (id === "L0") {
      hazards.push({ type: "pad", x: x + 80, y: FLOOR - 10, w: 54, h: 12, tx: x + 520, ty: FLOOR, cool: 0 });
      hazards.push({ type: "pad", x: x + 500, y: FLOOR - 10, w: 54, h: 12, tx: x + 110, ty: FLOOR, cool: 0 });
    }
    x += 980;

    addPlat(x + 20, FLOOR - 100, 90);
    if (id === "STARK" || id === "BASE") {
      hazards.push({ type: "laser", x: x + 70, y0: 90, y1: FLOOR, period: 1.7, phase: 0.2, on: false });
    }
    x += 150;
    addGround(x, 760);
    addTurret(x + 200, FLOOR);
    addTurret(x + 420, FLOOR);
    addSoldier(x + 300, FLOOR, false);
    addFlyer(x + 500, 190, false);
    addCapsule(x + 280, 150, "machine");
    addCoins(x + 40, 4);
    if (lv.proofs) items.push({ type: "proof", x: x + 600, y: FLOOR - 28, r: 14 });
    x += 760;

    addGround(x, 1100);
    addPlat(x + 40, FLOOR - 80, 90);
    addPlat(x + 140, FLOOR - 150, 90);
    addPlat(x + 240, FLOOR - 220, 160);
    addCoins(x + 250, 3, FLOOR - 246);
    addSniper(x + 310, FLOOR - 220);
    addSoldier(x + 500, FLOOR, false);
    addJumper(x + 640);
    addFlyer(x + 720, 230, false);
    if (lv.proofs) items.push({ type: "proof", x: x + 300, y: FLOOR - 246, r: 14 });
    if (id === "STARK") hazards.push({ type: "laser", x: x + 430, y0: 80, y1: FLOOR, period: 1.5, phase: 0.6, on: false });
    x += 700;
    addTank(x + 80);
    items.push({ type: "heart", x: x + 240, y: FLOOR - 26, r: 12 });
    addCapsule(x + 200, 160, "laser");
    x += 400;

    addPlat(x + 30, FLOOR - 110, 100);
    if (id === "ARB" || id === "L0") addPlat(x + 20, FLOOR - 150, 120, "move");
    x += 180;
    addGround(x, 900);
    addSoldier(x + 120, FLOOR, false);
    addSoldier(x + 250, FLOOR, false);
    addSoldier(x + 400, FLOOR, false);
    addJumper(x + 560);
    addTurret(x + 700, FLOOR);
    addFlyer(x + 300, 180, false);
    addFlyer(x + 620, 240, false);
    addCapsule(x + 480, 140, "flame");
    if (lv.proofs) items.push({ type: "proof", x: x + 220, y: FLOOR - 28, r: 14 });
    if (id === "STARK" || id === "BASE") {
      hazards.push({ type: "laser", x: x + 330, y0: 90, y1: FLOOR, period: 1.8, phase: 0, on: false });
      hazards.push({ type: "laser", x: x + 520, y0: 90, y1: FLOOR, period: 1.8, phase: 0.9, on: false });
    }
    x += 900;

    const arena = x;
    addGround(arena, 980);
    if (lv.proofs) gate = { x: arena + 40, y: 110, w: 26, h: FLOOR - 110, closed: true };
    boss = {
      type: lv.boss, x: arena + 640, y: FLOOR, hp: lv.bossHp, max: lv.bossHp,
      w: 108, h: 96, shootCd: 1, phase: 0, active: false, alive: true, hurtT: 0, jumping: 0,
    };
    items.push({ type: "heart", x: arena + 180, y: FLOOR - 26, r: 12 });
    worldW = arena + 980;
    checkXs = [90, 1400, 2800, 4100, arena + 80];
    for (let i = 80; i < worldW; i += 240) {
      decos.push({ x: i, h: 90 + (i * 13) % 140, kind: id });
    }
  }

  function startLevel(index) {
    levelIndex = index;
    level = LEVELS[index];
    buildStage(level);
    state = "play";
    t = 0; camX = 0; shake = 0; score = 0; tokens = 0; proofs = 0; hintTimer = 5.5;
    Object.assign(player, {
      x: 90, y: FLOOR, vx: 0, vy: 0, hp: MAX_HP, lives: MAX_LIVES, inv: 2,
      face: 1, weapon: "rifle", wing: true, fireCd: 0, duck: false, muzzle: 0,
    });
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
    player.vx = 0; player.vy = 0; player.hp = MAX_HP; player.inv = 2; player.wing = true;
    boom(player.x, player.y - 20, 28);
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
      ? `分数 ${score} · 下一关 ${next.name}`
      : `全链通关！分数 ${score}。潜龙打穿了 Web3。`;
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
    $("hud-weapon").textContent = WEAPON_NAME[player.weapon] || "步枪";
    $("hud-bar").style.width = (clamp(player.x / worldW, 0, 1) * 100).toFixed(1) + "%";
    if (level.proofs) $("hud-special").textContent = `证明 ${proofs}/${level.proofs}`;
    else if (boss && boss.active && boss.alive) $("hud-special").textContent = `BOSS ${Math.max(0, boss.hp)}/${boss.max}`;
    else $("hud-special").textContent = "";
  }

  function groundedAt(px, py) {
    return plats.some((p) => aabb({ x: px - 6, y: py, w: 12, h: 8 }, p));
  }
  function aimVector() {
    let dx = 0, dy = 0;
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
    const mx = player.x + aim.x * 26;
    const my = player.y - (duck ? 14 : 32) + aim.y * 8;
    const base = Math.atan2(aim.y, aim.x);
    const add = (ang, spd, pierce, r, life, flame) => {
      bullets.push({
        x: mx, y: my, vx: Math.cos(ang) * spd, vy: Math.sin(ang) * spd,
        r, life: life || 0.85, pierce, hit: new Set(), flame: !!flame, born: t,
      });
    };
    const wpn = player.weapon;
    if (wpn === "spread") {
      player.fireCd = 0.18;
      for (let i = -2; i <= 2; i++) add(base + i * 0.22, 700, 0, 4.5);
    } else if (wpn === "laser") {
      player.fireCd = 0.07;
      add(base, 1100, 6, 3.2, 0.65);
    } else if (wpn === "flame") {
      player.fireCd = 0.13;
      add(base, 420, 1, 8, 1.1, true);
    } else if (wpn === "machine") {
      player.fireCd = 0.055;
      add(base + rand(-0.04, 0.04), 900, 0, 4);
    } else {
      player.fireCd = 0.1;
      add(base, 820, 0, 5);
    }
    player.muzzle = 0.06;
    burst(mx, my, "#ffb15a", 2, 60);
    sfx.shoot();
  }
  function hurt() {
    if (player.inv > 0) return;
    player.hp -= 1;
    player.inv = 1.15;
    shake = 9;
    burst(player.x, player.y - 22, "#ff6b7a", 16, 250);
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
    player.vx = mx * (player.duck ? 0 : 300);
    if (mx) player.face = Math.sign(mx);
    player.runT += Math.abs(mx) * dt * 12;
    player.muzzle = Math.max(0, player.muzzle - dt);
    player.jumpBuf = input.jump ? 0.12 : Math.max(0, player.jumpBuf - dt);
    if (player.onGround) { player.coyote = 0.1; player.wing = true; }
    else player.coyote = Math.max(0, player.coyote - dt);
    if (player.jumpBuf > 0 && player.coyote > 0) {
      player.vy = -660; player.onGround = false; player.jumpBuf = 0; player.coyote = 0; sfx.jump();
    } else if (player.jumpBuf > 0 && player.wing && !player.onGround) {
      player.vy = -500; player.wing = false; player.jumpBuf = 0;
      burst(player.x, player.y, "#4de2c8", 8, 120); sfx.jump();
    }
    if (!input.jumpHeld && player.vy < 0) player.vy += 2500 * dt;
    player.vy = Math.min(player.vy + 1800 * dt, 1000);

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
        player.y = p.y; player.vy = 0; player.onGround = true; ride = p; r = pRect();
      } else if (player.vy < 0 && prev.y >= p.y + p.h - 10) {
        player.y = p.y + p.h + r.h + 0.1; player.vy = 0; r = pRect();
      }
    }
    if (ride && ride.kind === "move") player.x += ride.dx;
    player.x = clamp(player.x, Math.max(16, camX + 24), worldW - 16);
    if (player.y > H + 40) die();
    for (const cx of checkXs) {
      if (player.onGround && player.x > cx && checkpoint.x < cx - 10) checkpoint = { x: player.x, y: player.y };
    }
  }

  function enemyRect(e) {
    if (e.type === "flyer" || e.type === "capsule") return { x: e.x - e.w / 2, y: e.y - e.h / 2, w: e.w, h: e.h };
    const hop = e.type === "jumper" ? Math.abs(Math.sin((e.phase || 0) * 6)) * 42 : 0;
    return { x: e.x - e.w / 2, y: e.y - e.h - hop, w: e.w, h: e.h };
  }
  function fireAt(x, y, tx, ty, spd) {
    const a = Math.atan2(ty - y, tx - x);
    ebullets.push({ x, y, vx: Math.cos(a) * spd, vy: Math.sin(a) * spd, r: 5.5, life: 3 });
  }
  function killEnemy(e) {
    const pts = e.type === "tank" ? 200 : e.type === "capsule" ? 20 : 50;
    score += pts;
    pop(e.x, e.y - 30, "+" + pts);
    boom(e.x, e.y - 16, e.type === "tank" ? 58 : 30);
    if (e.type === "capsule") items.push({ type: "weapon", x: e.x, y: e.y, r: 13, weapon: e.drop });
    if (e.type === "tank") items.push({ type: "heart", x: e.x, y: e.y - 20, r: 12 });
  }

  function updateEnemies(dt) {
    const onScreen = (e) => e.x > camX - 40 && e.x < camX + W + 80;
    for (const e of enemies) {
      if (e.type === "soldier") {
        e.x += e.dir * 90 * dt;
        if (!groundedAt(e.x + e.dir * 16, e.y) || e.x < 40) e.dir *= -1;
        if (onScreen(e) && player.x < e.x) e.dir = -1;
        if (onScreen(e) && player.x > e.x + 80) e.dir = 1;
        e.shootCd -= dt;
        if (!e.silent && onScreen(e) && e.shootCd <= 0 && Math.abs(player.x - e.x) < 420) {
          e.shootCd = 1.35;
          fireAt(e.x, e.y - 22, player.x, player.y - 26, 300);
        }
      } else if (e.type === "jumper") {
        e.phase += dt;
        e.x += e.dir * 50 * dt;
        if (!groundedAt(e.x + e.dir * 14, e.y)) e.dir *= -1;
      } else if (e.type === "turret" || e.type === "sniper") {
        e.shootCd -= dt;
        if (onScreen(e) && e.shootCd <= 0 && Math.abs(player.x - e.x) < 620) {
          e.shootCd = e.type === "sniper" ? 1.05 : 1.2;
          fireAt(e.x, e.y - 18, player.x, player.y - 28, e.type === "sniper" ? 380 : 300);
        }
      } else if (e.type === "flyer") {
        e.phase += dt;
        e.x -= 85 * dt;
        e.y = e.homeY + Math.sin(e.phase * 2.4) * 34;
        e.shootCd -= dt;
        if (!e.silent && onScreen(e) && e.shootCd <= 0) {
          e.shootCd = 1.8;
          fireAt(e.x, e.y, player.x, player.y - 20, 270);
        }
      } else if (e.type === "capsule") {
        e.phase += dt;
        e.x -= 22 * dt;
        e.y = e.homeY + Math.sin(e.phase * 2.2) * 26;
      } else if (e.type === "tank") {
        e.phase += dt;
        e.x += Math.sin(e.phase) * 20 * dt;
        e.shootCd -= dt;
        if (onScreen(e) && e.shootCd <= 0) {
          e.shootCd = 0.9;
          for (let i = -1; i <= 1; i++) {
            const a = Math.PI + i * 0.28;
            ebullets.push({ x: e.x - 20, y: e.y - 28, vx: Math.cos(a) * 280, vy: Math.sin(a) * 280, r: 7, life: 3.2 });
          }
        }
      }
    }
    for (const b of ebullets) { b.x += b.vx * dt; b.y += b.vy * dt; b.life -= dt; }
    ebullets = ebullets.filter((b) => b.life > 0 && b.x > camX - 50 && b.x < camX + W + 50);
    for (const b of bullets) {
      b.x += b.vx * dt;
      b.y += b.vy * dt;
      b.life -= dt;
      if (b.flame) b.y += Math.sin((t - b.born) * 14) * 90 * dt;
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
          burst(b.x, b.y, level.accent, 5, 130);
          sfx.hit();
          if (b.pierce <= 0) b.life = 0; else b.pierce -= 1;
          if (e.hp <= 0) killEnemy(e);
        }
      }
      if (boss && boss.alive && boss.active) {
        const r = { x: boss.x - boss.w / 2, y: boss.y - boss.h, w: boss.w, h: boss.h };
        if (b.x > r.x && b.x < r.x + r.w && b.y > r.y && b.y < r.y + r.h && !b.hit.has(boss)) {
          b.hit.add(boss);
          boss.hp -= 1;
          boss.hurtT = 0.1;
          if (b.pierce <= 0) b.life = 0;
          score += 12;
          burst(b.x, b.y, "#fff", 7, 150);
          sfx.hit();
          if (boss.hp <= 0) {
            boss.alive = false;
            score += 500;
            pop(boss.x, boss.y - 80, "+500");
            boom(boss.x, boss.y - 40, 80);
            exitDoor = { x: worldW - 120, y: FLOOR - 78, r: 50 };
          }
        }
      }
    }
    enemies = enemies.filter((e) => e.hp > 0 && e.x > camX - 160);

    const pr = pRect();
    for (const e of enemies) {
      if (e.type === "capsule") continue;
      if (aabb(pr, enemyRect(e))) hurt();
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
    if (!boss.active && player.x > boss.x - 520) boss.active = true;
    if (!boss.active) return;
    lockCam = true;
    boss.phase += dt;
    boss.shootCd -= dt;
    boss.hurtT = Math.max(0, boss.hurtT - dt);
    const ratio = boss.hp / boss.max;
    boss.x = lerp(boss.x, worldW - 300 + Math.sin(boss.phase * 0.8) * (ratio < 0.4 ? 90 : 40), 0.04);
    if (boss.type === "serpent" || boss.type === "warden") {
      boss.y = FLOOR - 20 - Math.abs(Math.sin(boss.phase * 1.5)) * (ratio < 0.5 ? 110 : 50);
    }
    const n = ratio < 0.35 ? 7 : ratio < 0.65 ? 5 : 3;
    const cd = ratio < 0.35 ? 0.55 : 0.95;
    if (boss.shootCd <= 0) {
      boss.shootCd = cd;
      for (let i = 0; i < n; i++) {
        const a = Math.PI + (i - (n - 1) / 2) * 0.22;
        ebullets.push({ x: boss.x - 24, y: boss.y - 52, vx: Math.cos(a) * 320, vy: Math.sin(a) * 320, r: 7, life: 4 });
      }
      if (ratio < 0.45 && Math.random() < 0.4) {
        addFlyer(boss.x - 40, 180, false);
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
        h.on = (h.phase % h.period) < h.period * 0.42;
        if (h.on && player.x > h.x - 9 && player.x < h.x + 9 && player.y > h.y0) hurt();
      } else if (h.type === "pad") {
        h.cool = Math.max(0, h.cool - dt);
        if (h.cool <= 0 && aabb(pRect(), { x: h.x, y: h.y, w: h.w, h: h.h + 8 })) {
          player.x = h.tx; player.y = h.ty - 24; player.vy = -240;
          for (const p of hazards) if (p.type === "pad") p.cool = 1;
          burst(player.x, player.y - 18, "#b4ff4d", 14, 180);
          sfx.collect();
        }
      }
    }
    for (const it of items) {
      if (Math.hypot(player.x - it.x, player.y - 22 - it.y) < 30) {
        it.dead = true;
        if (it.type === "token") { tokens += 1; score += 15; pop(it.x, it.y, "+15"); }
        if (it.type === "proof") {
          proofs += 1; score += 80;
          if (proofs >= level.proofs) {
            $("hud-hint").textContent = "证明已齐 · 闸门打开，去打 Boss";
            $("hud-hint").classList.remove("hidden");
            hintTimer = 3.2;
          }
        }
        if (it.type === "heart") player.hp = clamp(player.hp + 1, 0, MAX_HP);
        if (it.type === "weapon") {
          player.weapon = it.weapon;
          pop(it.x, it.y - 10, WEAPON_NAME[it.weapon]);
        }
        sfx.collect();
        burst(it.x, it.y, "#f0c36a", 8, 120);
      }
    }
    items = items.filter((it) => !it.dead);
    if (exitDoor && Math.hypot(player.x - exitDoor.x, player.y - 40 - exitDoor.y) < 52) winLevel();
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
    for (const p of particles) { p.x += p.vx * dt; p.y += p.vy * dt; p.life -= dt; }
    particles = particles.filter((p) => p.life > 0);
    for (const e of explosions) e.life -= dt;
    explosions = explosions.filter((e) => e.life > 0);
    for (const f of floats) { f.y -= 40 * dt; f.life -= dt; }
    floats = floats.filter((f) => f.life > 0);
    const want = lockCam ? worldW - W : player.x - 280;
    camX = lerp(camX, clamp(want, 0, Math.max(0, worldW - W)), 0.14);
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
      s.x -= s.z * 10 * 0.016;
      if (s.x < 0) s.x += W;
      ctx.globalAlpha = 0.22 + s.z * 0.5;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    ctx.fillStyle = level.accent + "16";
    ctx.font = "900 132px sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(level.id, W - 30, 140);
  }

  function drawDecosWorld() {
    for (const d of decos) {
      const x = d.x;
      if (x < camX - 80 || x > camX + W + 80) continue;
      ctx.fillStyle = level.accent + "18";
      ctx.fillRect(x, FLOOR - d.h, 54, d.h);
      ctx.fillRect(x + 18, FLOOR - d.h - 28, 18, 28);
      ctx.fillStyle = level.accent + "28";
      ctx.fillRect(x + 8, FLOOR - d.h + 20, 16, 12);
      ctx.fillRect(x + 30, FLOOR - d.h + 40, 14, 12);
    }
  }

  function drawWorld() {
    ctx.save();
    ctx.translate(-camX, 0);
    drawDecosWorld();

    for (const p of plats) {
      if (p.kind === "ground") {
        const dirt = ctx.createLinearGradient(0, p.y, 0, p.y + p.h);
        dirt.addColorStop(0, "#33486e");
        dirt.addColorStop(0.1, "#172238");
        dirt.addColorStop(1, "#080b14");
        ctx.fillStyle = dirt;
        ctx.fillRect(p.x, p.y, p.w, p.h);
        ctx.fillStyle = level.accent;
        ctx.fillRect(p.x, p.y, p.w, 8);
        ctx.fillStyle = level.accent + "55";
        for (let gx = p.x; gx < p.x + p.w; gx += 26) ctx.fillRect(gx, p.y + 11, 12, 3);
      } else {
        ctx.fillStyle = p.kind === "move" ? "#3d6d7a" : "#2c3f64";
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
        ctx.shadowBlur = 14;
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
      ctx.fillText("ZK GATE", gate.x - 10, gate.y - 8);
    }

    for (const it of items) {
      if (it.type === "token") {
        ctx.fillStyle = "#f0c36a";
        ctx.beginPath();
        ctx.arc(it.x, it.y, it.r, 0, Math.PI * 2);
        ctx.fill();
      } else if (it.type === "proof") {
        ctx.fillStyle = "rgba(139,92,246,0.45)";
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
        const map = { machine: "#fbbf24", spread: "#fb923c", laser: "#67e8f9", flame: "#f87171", rifle: "#fff" };
        ctx.fillStyle = map[it.weapon] || "#fff";
        roundRect(it.x - 13, it.y - 11, 26, 22, 4);
        ctx.fill();
        ctx.fillStyle = "#111";
        ctx.font = "bold 11px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText((it.weapon || "S")[0].toUpperCase(), it.x, it.y + 4);
      }
    }

    for (const e of enemies) {
      const r = enemyRect(e);
      if (e.type === "soldier" || e.type === "sniper") {
        ctx.fillStyle = e.type === "sniper" ? "#7f1d1d" : "#ef4444";
        roundRect(r.x, r.y, r.w, r.h, 4);
        ctx.fill();
        ctx.fillStyle = "#111";
        ctx.fillRect(r.x + 6, r.y + 6, 14, 7);
        ctx.fillStyle = "#d1d5db";
        ctx.fillRect(r.x - 8, r.y + 14, 12, 5);
      } else if (e.type === "jumper") {
        ctx.fillStyle = "#f97316";
        roundRect(r.x, r.y, r.w, r.h, 8);
        ctx.fill();
      } else if (e.type === "turret") {
        ctx.fillStyle = "#94a3b8";
        ctx.fillRect(r.x, r.y, r.w, r.h);
        ctx.fillStyle = "#e2e8f0";
        ctx.fillRect(r.x - 14, r.y + 8, 18, 8);
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
        roundRect(r.x, r.y, r.w, r.h, 8);
        ctx.fill();
        ctx.fillStyle = "#fff";
        ctx.font = "bold 11px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText((e.drop || "S")[0].toUpperCase(), e.x, e.y + 4);
      } else if (e.type === "tank") {
        ctx.fillStyle = "#64748b";
        roundRect(r.x, r.y, r.w, r.h, 6);
        ctx.fill();
        ctx.fillStyle = "#0f172a";
        ctx.fillRect(r.x + 16, r.y + 8, 28, 14);
        ctx.fillStyle = "#f8fafc";
        ctx.font = "bold 10px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("TANK", e.x, r.y - 6);
      }
    }

    if (boss && boss.alive) {
      ctx.save();
      ctx.globalAlpha = boss.hurtT > 0 ? 0.45 : 1;
      ctx.fillStyle = level.accent;
      roundRect(boss.x - boss.w / 2, boss.y - boss.h, boss.w, boss.h, 14);
      ctx.fill();
      ctx.fillStyle = "#071018";
      ctx.fillRect(boss.x - 22, boss.y - 72, 16, 16);
      ctx.fillRect(boss.x + 6, boss.y - 72, 16, 16);
      ctx.fillStyle = "#fff";
      ctx.font = "bold 13px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(boss.type.toUpperCase(), boss.x, boss.y - boss.h - 28);
      ctx.fillStyle = "#1a1a1a";
      ctx.fillRect(boss.x - 46, boss.y - boss.h - 18, 92, 8);
      ctx.fillStyle = "#ef4444";
      ctx.fillRect(boss.x - 46, boss.y - boss.h - 18, 92 * clamp(boss.hp / boss.max, 0, 1), 8);
      ctx.restore();
    }

    if (exitDoor) {
      ctx.save();
      ctx.translate(exitDoor.x, exitDoor.y);
      ctx.rotate(t * 1.6);
      ctx.strokeStyle = level.accent;
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.ellipse(0, 0, 38, 22, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();
      ctx.fillStyle = "#fff";
      ctx.font = "bold 12px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("EXIT", exitDoor.x, exitDoor.y + 40);
    }

    for (const b of ebullets) {
      ctx.fillStyle = "#ff8a5b";
      ctx.beginPath();
      ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
      ctx.fill();
    }
    for (const b of bullets) {
      ctx.fillStyle = b.flame ? "#fb7185" : player.weapon === "laser" ? "#67e8f9" : "#ffe08a";
      ctx.beginPath();
      ctx.arc(b.x, b.y, b.r + 1, 0, Math.PI * 2);
      ctx.fill();
    }
    for (const e of explosions) {
      const k = 1 - e.life / e.max;
      ctx.globalAlpha = 1 - k;
      ctx.strokeStyle = "#ffd089";
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.arc(e.x, e.y, e.r * k + 8, 0, Math.PI * 2);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
    for (const p of particles) {
      ctx.globalAlpha = p.life / p.max;
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    for (const f of floats) {
      ctx.globalAlpha = clamp(f.life * 2, 0, 1);
      ctx.fillStyle = "#fff7c2";
      ctx.font = "bold 14px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(f.text, f.x, f.y);
    }
    ctx.globalAlpha = 1;
    drawHero();
    ctx.restore();
  }

  function drawHero() {
    const blink = player.inv > 0 && Math.sin(t * 28) > 0 ? 0.35 : 1;
    ctx.save();
    ctx.translate(player.x, player.y);
    ctx.scale(player.face * 1.15, 1.15);
    ctx.globalAlpha = blink;
    const duck = player.duck && player.onGround;
    const run = player.onGround && Math.abs(player.vx) > 20;
    const step = run ? Math.sin(player.runT) * 7 : 0;
    ctx.fillStyle = "#0f766e";
    ctx.beginPath();
    ctx.moveTo(-10, -18);
    ctx.quadraticCurveTo(-28, -8 + Math.sin(t * 8) * 3, -36, -4);
    ctx.strokeStyle = "#14b8a6";
    ctx.lineWidth = 4;
    ctx.stroke();
    ctx.fillStyle = "#115e59";
    ctx.fillRect(-10, duck ? -12 : -8, 7, 10 + step);
    ctx.fillRect(2, duck ? -12 : -8, 7, 10 - step);
    ctx.fillStyle = "#2dd4bf";
    roundRect(-13, duck ? -28 : -46, 26, duck ? 28 : 40, 7);
    ctx.fill();
    ctx.fillStyle = "#f5d78a";
    ctx.beginPath();
    ctx.ellipse(8, duck ? -22 : -40, 12, 10, 0.12, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#0f172a";
    ctx.beginPath();
    ctx.arc(13, duck ? -24 : -42, 2.3, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#fbbf24";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(16, duck ? -28 : -48);
    ctx.lineTo(24, duck ? -36 : -58);
    ctx.stroke();
    ctx.fillStyle = "#94a3b8";
    ctx.fillRect(10, duck ? -18 : -30, 18, 6);
    if (player.muzzle > 0) {
      ctx.fillStyle = "#ffd089";
      ctx.beginPath();
      ctx.arc(30, duck ? -15 : -27, 7, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
    ctx.globalAlpha = 1;
  }

  function draw() {
    ctx.save();
    if (shake > 0) ctx.translate(rand(-shake, shake), rand(-shake, shake));
    if (state === "menu" || state === "select" || state === "help") {
      drawBg();
      player.x = 380; player.y = FLOOR - 6; player.face = 1; player.onGround = true;
      player.duck = false; player.inv = 0; player.runT = t * 8; player.vx = 90; player.muzzle = 0;
      camX = 0;
      drawHero();
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
      if (down && k === "enter" && state === "menu") { ensureAudio(); startLevel(0); }
      if (down && (k === "p" || k === "escape")) {
        if (state === "play") { state = "pause"; screens.pause.classList.remove("hidden"); syncHud(); }
        else if (state === "pause") { state = "play"; screens.pause.classList.add("hidden"); syncHud(); }
      }
    };
    window.addEventListener("keydown", (e) => setKey(e, true));
    window.addEventListener("keyup", (e) => setKey(e, false));
    window.addEventListener("mousedown", (e) => { if (state === "play" && e.button === 0) input.fire = true; });
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
      renderLevelGrid(); hideAllScreens(); screens.select.classList.remove("hidden"); state = "select";
    });
    $("btn-help").addEventListener("click", () => { hideAllScreens(); screens.help.classList.remove("hidden"); state = "help"; });
    $("btn-select-back").addEventListener("click", goMenu);
    $("btn-help-back").addEventListener("click", goMenu);
    $("btn-resume").addEventListener("click", () => { state = "play"; screens.pause.classList.add("hidden"); syncHud(); });
    $("btn-pause-menu").addEventListener("click", goMenu);
    $("btn-retry").addEventListener("click", () => startLevel(levelIndex));
    $("btn-dead-select").addEventListener("click", () => {
      renderLevelGrid(); hideAllScreens(); screens.select.classList.remove("hidden"); state = "select"; syncHud();
    });
    $("btn-dead-menu").addEventListener("click", goMenu);
    $("btn-next").addEventListener("click", () => {
      if (levelIndex + 1 < LEVELS.length) startLevel(levelIndex + 1); else goMenu();
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
