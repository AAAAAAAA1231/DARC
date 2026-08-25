(() => {
  "use strict";

  const canvas = document.getElementById("game");
  const ctx = canvas.getContext("2d");
  const W = 1280;
  const H = 720;

  const SAVE_KEY = "qianlong-web3-unlock";
  const MAX_HP = 5;

  const LEVELS = [
    {
      id: "ETH",
      name: "ETH · 创世主网",
      desc: "教学关。躲开紫色 Gas 墙，熟悉龙息。",
      hint: "WASD 移动 · 空格喷火 · 穿过终点传送门",
      accent: "#627eea",
      bgTop: "#0a1024",
      bgBot: "#05070f",
      speed: 210,
      length: 3200,
      hp: 5,
      proofsNeeded: 0,
      walls: 4,
      scouts: 10,
      bots: 2,
      turrets: 1,
      waves: 0,
      wormholes: 0,
      tokens: 14,
      nitro: false,
    },
    {
      id: "ARB",
      name: "ARB · Nitro 通道",
      desc: "滚动加速，小心 Sequencer 脉冲冲击波。",
      hint: "Nitro 加速中！脉冲来袭时贴边飞",
      accent: "#12aaff",
      bgTop: "#07141c",
      bgBot: "#03080c",
      speed: 310,
      length: 3800,
      hp: 5,
      proofsNeeded: 0,
      walls: 5,
      scouts: 16,
      bots: 5,
      turrets: 3,
      waves: 0,
      wormholes: 0,
      tokens: 16,
      nitro: true,
    },
    {
      id: "ZK",
      name: "ZK · 零知识电路",
      desc: "收集 6 枚 SNARK 证明，出口才会打开。",
      hint: "收集发光六边形证明 · 凑齐后传送门开启",
      accent: "#8b5cf6",
      bgTop: "#140a22",
      bgBot: "#07040e",
      speed: 230,
      length: 3600,
      hp: 5,
      proofsNeeded: 6,
      walls: 7,
      scouts: 12,
      bots: 3,
      turrets: 4,
      waves: 0,
      wormholes: 0,
      tokens: 10,
      nitro: false,
    },
    {
      id: "STARK",
      name: "STARK · 多项式风暴",
      desc: "正弦激光扫过航道，几何弹幕更密。",
      hint: "激光呈波浪起伏，找波谷穿过去",
      accent: "#ec796b",
      bgTop: "#1a0d0a",
      bgBot: "#0b0605",
      speed: 250,
      length: 4000,
      hp: 5,
      proofsNeeded: 0,
      walls: 3,
      scouts: 18,
      bots: 4,
      turrets: 3,
      waves: 5,
      wormholes: 0,
      tokens: 12,
      nitro: false,
    },
    {
      id: "L0",
      name: "L0 · 跨链之桥",
      desc: "钻进虫洞可传送航道。跨链报文会追尾。",
      hint: "飞进青色虫洞可换航道 · 躲开报文",
      accent: "#b4ff4d",
      bgTop: "#0b140c",
      bgBot: "#050805",
      speed: 270,
      length: 4200,
      hp: 5,
      proofsNeeded: 0,
      walls: 4,
      scouts: 14,
      bots: 6,
      turrets: 3,
      waves: 1,
      wormholes: 6,
      tokens: 14,
      nitro: false,
    },
    {
      id: "BASE",
      name: "BASE · 链上盛夏",
      desc: "终章。代币更多，火力更猛，守住龙鳞。",
      hint: "终章盛夏 · 清出一条通往 DARC 的航线",
      accent: "#0052ff",
      bgTop: "#071028",
      bgBot: "#040814",
      speed: 290,
      length: 4400,
      hp: 5,
      proofsNeeded: 0,
      walls: 6,
      scouts: 22,
      bots: 7,
      turrets: 5,
      waves: 2,
      wormholes: 2,
      tokens: 22,
      nitro: true,
    },
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
    up: false,
    down: false,
    left: false,
    right: false,
    fire: false,
    mouseX: 0,
    mouseY: 0,
    stickX: 0,
    stickY: 0,
    touching: false,
  };

  let audio;
  let audioReady = false;

  const rand = (a, b) => a + Math.random() * (b - a);
  const irand = (a, b) => Math.floor(rand(a, b + 1));
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

  function loadUnlock() {
    const n = Number(localStorage.getItem(SAVE_KEY) || "1");
    return clamp(n, 1, LEVELS.length);
  }
  function saveUnlock(n) {
    const cur = loadUnlock();
    if (n > cur) localStorage.setItem(SAVE_KEY, String(n));
  }

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
    if (slide) o.frequency.exponentialRampToValueAtTime(slide, audio.currentTime + dur);
    g.gain.value = vol || 0.04;
    g.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + dur);
    o.connect(g).connect(audio.destination);
    o.start();
    o.stop(audio.currentTime + dur);
  }

  const sfx = {
    shoot: () => beep(420, 0.08, "sawtooth", 0.03, 180),
    hit: () => beep(180, 0.12, "square", 0.05, 70),
    collect: () => beep(660, 0.1, "sine", 0.05, 990),
    hurt: () => beep(140, 0.22, "sawtooth", 0.07, 50),
    win: () => {
      beep(523, 0.12, "sine", 0.05);
      setTimeout(() => beep(659, 0.12, "sine", 0.05), 90);
      setTimeout(() => beep(784, 0.22, "sine", 0.06), 180);
    },
    lose: () => beep(220, 0.4, "triangle", 0.06, 80),
    portal: () => beep(300, 0.25, "sine", 0.05, 700),
  };

  let state = "menu";
  let levelIndex = 0;
  let level = LEVELS[0];
  let t = 0;
  let worldX = 0;
  let shake = 0;
  let score = 0;
  let tokens = 0;
  let proofs = 0;
  let combo = 0;
  let spawnCursor = 0;
  let nitroTimer = 0;
  let hintTimer = 0;

  const player = {
    x: 180,
    y: H / 2,
    vx: 0,
    vy: 0,
    hp: MAX_HP,
    inv: 0,
    fireCd: 0,
    angle: 0,
  };

  let bullets = [];
  let enemies = [];
  let hazards = [];
  let pickups = [];
  let particles = [];
  let stars = [];
  let exitPortal = null;
  let spawnPlan = [];

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function showScreen(name) {
    Object.entries(screens).forEach(([key, el]) => {
      el.classList.toggle("hidden", key !== name);
    });
    $("hud").classList.toggle("hidden", name !== null && name !== "pause" ? state !== "play" && state !== "pause" : false);
  }

  function syncHudVisibility() {
    $("hud").classList.toggle("hidden", state !== "play" && state !== "pause");
    const isTouch = window.matchMedia("(pointer: coarse)").matches || window.innerWidth <= 900;
    $("touch").classList.toggle("hidden", !(isTouch && state === "play"));
  }

  function hideAllScreens() {
    Object.values(screens).forEach((el) => el.classList.add("hidden"));
  }

  function burst(x, y, color, n, speed) {
    for (let i = 0; i < n; i++) {
      const a = rand(0, Math.PI * 2);
      const s = rand(20, speed || 220);
      particles.push({
        x, y,
        vx: Math.cos(a) * s,
        vy: Math.sin(a) * s,
        life: rand(0.25, 0.7),
        max: 0.7,
        r: rand(1.5, 3.5),
        color,
      });
    }
  }

  function makeStars() {
    stars = [];
    for (let i = 0; i < 90; i++) {
      stars.push({
        x: Math.random() * W,
        y: Math.random() * H,
        z: rand(0.2, 1.4),
        r: rand(0.6, 2.2),
      });
    }
  }

  function planLevel(lv) {
    const plan = [];
    const push = (at, kind, extra) => plan.push({ at, kind, extra: extra || {} });

    for (let i = 0; i < lv.tokens; i++) {
      push((i + 1) / (lv.tokens + 1) * 0.92, "token", { y: rand(80, H - 80) });
    }
    for (let i = 0; i < lv.scouts; i++) {
      push(0.08 + (i / lv.scouts) * 0.8, "scout", { y: rand(70, H - 70), n: irand(1, 3) });
    }
    for (let i = 0; i < lv.bots; i++) {
      push(0.18 + (i / Math.max(1, lv.bots)) * 0.7, "bot");
    }
    for (let i = 0; i < lv.turrets; i++) {
      push(0.2 + (i / Math.max(1, lv.turrets)) * 0.65, "turret", { y: rand(90, H - 90) });
    }
    for (let i = 0; i < lv.walls; i++) {
      push(0.12 + (i / Math.max(1, lv.walls)) * 0.75, "wall");
    }
    for (let i = 0; i < lv.waves; i++) {
      push(0.16 + (i / Math.max(1, lv.waves)) * 0.7, "wave");
    }
    for (let i = 0; i < lv.wormholes; i++) {
      push(0.15 + (i / Math.max(1, lv.wormholes)) * 0.7, "wormhole", { y: rand(110, H - 110) });
    }
    for (let i = 0; i < lv.proofsNeeded; i++) {
      push(0.1 + (i / lv.proofsNeeded) * 0.75, "proof", { y: rand(90, H - 90) });
    }
    if (lv.id !== "ETH") {
      push(0.45, "heart");
      push(0.75, "heart");
    } else {
      push(0.55, "heart");
    }
    plan.sort((a, b) => a.at - b.at);
    return plan;
  }

  function startLevel(index) {
    levelIndex = index;
    level = LEVELS[index];
    state = "play";
    t = 0;
    worldX = 0;
    shake = 0;
    score = 0;
    tokens = 0;
    proofs = 0;
    combo = 0;
    spawnCursor = 0;
    nitroTimer = 0;
    hintTimer = 5.5;
    bullets = [];
    enemies = [];
    hazards = [];
    pickups = [];
    particles = [];
    exitPortal = null;
    spawnPlan = planLevel(level);
    player.x = 180;
    player.y = H / 2;
    player.vx = 0;
    player.vy = 0;
    player.hp = level.hp;
    player.inv = 1.2;
    player.fireCd = 0;
    hideAllScreens();
    syncHudVisibility();
    $("hud-level-name").textContent = level.name;
    $("hud-hint").textContent = level.hint;
    $("hud-hint").classList.remove("hidden");
    updateHud();
    ensureAudio();
  }

  function spawnFromPlan(item) {
    const sx = W + 40;
    switch (item.kind) {
      case "token":
        pickups.push({ type: "token", x: sx, y: item.extra.y, r: 14, spin: rand(0, 6) });
        break;
      case "proof":
        pickups.push({ type: "proof", x: sx, y: item.extra.y, r: 16, spin: 0 });
        break;
      case "heart":
        pickups.push({ type: "heart", x: sx, y: rand(120, H - 120), r: 13, spin: 0 });
        break;
      case "scout": {
        const n = item.extra.n || 1;
        for (let i = 0; i < n; i++) {
          enemies.push({
            type: "scout",
            x: sx + i * 36,
            y: item.extra.y + Math.sin(i) * 26,
            hp: 1,
            r: 14,
            phase: rand(0, 6),
            shootCd: rand(0.8, 1.6),
          });
        }
        break;
      }
      case "bot":
        enemies.push({
          type: "bot",
          x: sx,
          y: rand(100, H - 100),
          hp: 3,
          r: 20,
          shootCd: 1.1,
        });
        break;
      case "turret":
        enemies.push({
          type: "turret",
          x: sx,
          y: item.extra.y,
          hp: 4,
          r: 22,
          shootCd: 0.2,
          vx: -level.speed * 0.35,
        });
        break;
      case "wall": {
        const gap = rand(130, 190);
        const gy = rand(90 + gap / 2, H - 90 - gap / 2);
        hazards.push({ type: "wall", x: sx, y: 0, w: 46, h: gy - gap / 2, gapY: gy, gap });
        break;
      }
      case "wave":
        hazards.push({
          type: "wave",
          x: sx,
          y: rand(140, H - 140),
          amp: rand(70, 120),
          len: 520,
          phase: rand(0, 4),
          thick: 10,
        });
        break;
      case "wormhole":
        hazards.push({
          type: "wormhole",
          x: sx,
          y: item.extra.y,
          r: 28,
          pairY: clamp(item.extra.y + (Math.random() < 0.5 ? -1 : 1) * rand(140, 240), 90, H - 90),
          cool: 0,
        });
        break;
      default:
        break;
    }
  }

  function fire() {
    if (player.fireCd > 0) return;
    player.fireCd = 0.16;
    bullets.push({
      x: player.x + 38,
      y: player.y + Math.sin(t * 18) * 3,
      vx: 620,
      vy: player.vy * 0.15,
      r: 6,
      life: 1.1,
    });
    burst(player.x + 30, player.y, "#ffb15a", 4, 80);
    sfx.shoot();
  }

  function hurt(amount) {
    if (player.inv > 0) return;
    player.hp -= amount || 1;
    player.inv = 1.05;
    shake = 10;
    combo = 0;
    burst(player.x, player.y, "#ff6b7a", 18, 280);
    sfx.hurt();
    if (player.hp <= 0) {
      player.hp = 0;
      die();
    }
    updateHud();
  }

  function die() {
    state = "dead";
    sfx.lose();
    $("dead-text").textContent = `${level.name} 失败。分数 ${score} · 代币 ${tokens}`;
    screens.dead.classList.remove("hidden");
    syncHudVisibility();
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
      : `全链通关！分数 ${score}。潜龙已穿过 Web3。`;
    $("btn-next").style.display = next ? "" : "none";
    screens.clear.classList.remove("hidden");
    syncHudVisibility();
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
    const p = clamp(worldX / level.length, 0, 1);
    $("hud-bar").style.width = (p * 100).toFixed(1) + "%";
    if (level.proofsNeeded) {
      $("hud-special").textContent = `证明 ${proofs}/${level.proofsNeeded}`;
    } else {
      $("hud-special").textContent = combo > 1 ? `连击 x${combo}` : "";
    }
  }

  function maybeSpawnExit() {
    if (exitPortal) return;
    const ready = worldX >= level.length - 40;
    const zkOk = !level.proofsNeeded || proofs >= level.proofsNeeded;
    if (ready && zkOk) {
      exitPortal = { x: W + 60, y: H / 2, r: 46, spin: 0 };
    }
  }

  function update(dt) {
    t += dt;
    if (state === "menu" || state === "select" || state === "help") {
      worldX += 40 * dt;
      return;
    }
    if (state !== "play") return;

    if (hintTimer > 0) {
      hintTimer -= dt;
      if (hintTimer <= 0) $("hud-hint").classList.add("hidden");
    }

    player.inv = Math.max(0, player.inv - dt);
    player.fireCd = Math.max(0, player.fireCd - dt);
    shake = Math.max(0, shake - dt * 18);

    let ax = 0;
    let ay = 0;
    if (input.left) ax -= 1;
    if (input.right) ax += 1;
    if (input.up) ay -= 1;
    if (input.down) ay += 1;
    if (input.touching) {
      ax += input.stickX;
      ay += input.stickY;
    }
    const len = Math.hypot(ax, ay) || 1;
    const accel = 1800;
    player.vx += (ax / len) * accel * dt;
    player.vy += (ay / len) * accel * dt;
    if (!ax) player.vx *= Math.pow(0.02, dt);
    if (!ay) player.vy *= Math.pow(0.02, dt);
    const spd = Math.hypot(player.vx, player.vy);
    const maxSpd = 420;
    if (spd > maxSpd) {
      player.vx *= maxSpd / spd;
      player.vy *= maxSpd / spd;
    }
    player.x = clamp(player.x + player.vx * dt, 50, W * 0.78);
    player.y = clamp(player.y + player.vy * dt, 50, H - 50);
    player.angle = lerp(player.angle, clamp(player.vy / 420, -0.5, 0.5), 0.2);

    if (input.fire) fire();

    let scroll = level.speed;
    if (level.nitro) {
      nitroTimer += dt;
      if (nitroTimer % 9 > 6.2) scroll *= 1.55;
    }
    worldX += scroll * dt;

    const progress = worldX / level.length;
    while (spawnCursor < spawnPlan.length && spawnPlan[spawnCursor].at <= progress) {
      spawnFromPlan(spawnPlan[spawnCursor]);
      spawnCursor += 1;
    }
    maybeSpawnExit();

    for (const b of bullets) {
      b.x += b.vx * dt;
      b.y += b.vy * dt;
      b.life -= dt;
    }
    bullets = bullets.filter((b) => b.life > 0 && b.x < W + 40);

    for (const e of enemies) {
      if (e.type === "scout") {
        e.x -= (scroll + 40) * dt;
        e.y += Math.sin(t * 3 + e.phase) * 70 * dt;
        e.y = clamp(e.y, 40, H - 40);
        e.shootCd -= dt;
        if (e.shootCd <= 0) {
          e.shootCd = 1.8;
          enemies.push({
            type: "shot",
            x: e.x,
            y: e.y,
            vx: -260,
            vy: (player.y - e.y) * 0.15,
            r: 5,
            hp: 1,
            life: 3,
          });
        }
      } else if (e.type === "bot") {
        e.x -= (scroll * 0.55) * dt;
        e.y += Math.sign(player.y - e.y) * 70 * dt;
        e.shootCd -= dt;
        if (e.shootCd <= 0) {
          e.shootCd = 1.35;
          const ang = Math.atan2(player.y - e.y, player.x - e.x);
          enemies.push({
            type: "shot",
            x: e.x,
            y: e.y,
            vx: Math.cos(ang) * 280,
            vy: Math.sin(ang) * 280,
            r: 6,
            hp: 1,
            life: 3,
          });
        }
      } else if (e.type === "turret") {
        e.x += (e.vx || -80) * dt - scroll * 0.2 * dt;
        e.shootCd -= dt;
        if (e.shootCd <= 0) {
          e.shootCd = 1.05;
          enemies.push({
            type: "shot",
            x: e.x - 10,
            y: e.y,
            vx: -340,
            vy: rand(-40, 40),
            r: 6,
            hp: 1,
            life: 3,
          });
        }
      } else if (e.type === "shot") {
        e.x += e.vx * dt;
        e.y += e.vy * dt;
        e.life -= dt;
      }
    }

    for (const h of hazards) {
      h.x -= scroll * dt;
      if (h.type === "wave") h.phase += dt * 1.6;
      if (h.type === "wormhole") h.cool = Math.max(0, h.cool - dt);
    }

    for (const p of pickups) {
      p.x -= scroll * dt;
      p.spin += dt * 3;
      p.y += Math.sin(t * 2 + p.spin) * 12 * dt;
    }

    if (exitPortal) {
      exitPortal.x -= scroll * 0.7 * dt;
      exitPortal.spin += dt * 2;
      if (exitPortal.x < W * 0.62) exitPortal.x = W * 0.62;
    }

    for (const p of particles) {
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.life -= dt;
      p.vx *= 0.98;
      p.vy *= 0.98;
    }
    particles = particles.filter((p) => p.life > 0);

    // bullet vs enemy
    for (const b of bullets) {
      for (const e of enemies) {
        if (e.type === "shot" || e.hp <= 0) continue;
        if (Math.hypot(b.x - e.x, b.y - e.y) < b.r + e.r) {
          e.hp -= 1;
          b.life = 0;
          burst(e.x, e.y, level.accent, 8, 160);
          sfx.hit();
          if (e.hp <= 0) {
            combo += 1;
            score += 50 * combo;
            burst(e.x, e.y, "#fff3c4", 16, 260);
          }
        }
      }
    }
    enemies = enemies.filter((e) => {
      if (e.type === "shot") return e.life > 0 && e.x > -40 && e.x < W + 80;
      return e.hp > 0 && e.x > -80;
    });

    // player vs enemy/shot
    for (const e of enemies) {
      if (Math.hypot(player.x - e.x, player.y - e.y) < 22 + e.r) {
        if (e.type === "shot") e.life = 0;
        hurt(1);
      }
    }

    // hazards
    for (const h of hazards) {
      if (h.type === "wall") {
        const top = { x: h.x, y: 0, w: h.w, h: h.h };
        const botY = h.h + h.gap;
        const bot = { x: h.x, y: botY, w: h.w, h: H - botY };
        const hitBox = (box) =>
          player.x + 18 > box.x && player.x - 18 < box.x + box.w &&
          player.y + 14 > box.y && player.y - 14 < box.y + box.h;
        if (hitBox(top) || hitBox(bot)) hurt(1);
        for (const b of bullets) {
          if (b.x > h.x && b.x < h.x + h.w && (b.y < h.h || b.y > h.h + h.gap)) {
            b.life = 0;
          }
        }
      } else if (h.type === "wave") {
        for (let i = 0; i < 18; i++) {
          const px = h.x + (i / 18) * h.len;
          const py = h.y + Math.sin(h.phase + i * 0.45) * h.amp;
          if (Math.hypot(player.x - px, player.y - py) < 16 + h.thick) hurt(1);
        }
      } else if (h.type === "wormhole" && h.cool <= 0) {
        if (Math.hypot(player.x - h.x, player.y - h.y) < h.r + 12) {
          player.y = h.pairY;
          player.inv = Math.max(player.inv, 0.35);
          h.cool = 1.2;
          burst(player.x, player.y, "#b4ff4d", 20, 200);
          sfx.portal();
        }
      }
    }
    hazards = hazards.filter((h) => h.x > -600);

    for (const p of pickups) {
      if (Math.hypot(player.x - p.x, player.y - p.y) < 28 + p.r) {
        p.dead = true;
        if (p.type === "token") {
          tokens += 1;
          score += 20;
          sfx.collect();
          burst(p.x, p.y, "#f0c36a", 10, 140);
        } else if (p.type === "proof") {
          proofs += 1;
          score += 80;
          sfx.collect();
          burst(p.x, p.y, "#c4b5fd", 14, 180);
          if (proofs >= level.proofsNeeded) {
            $("hud-hint").textContent = "证明已齐 · 飞向右侧传送门";
            $("hud-hint").classList.remove("hidden");
            hintTimer = 3;
            maybeSpawnExit();
          }
        } else if (p.type === "heart") {
          player.hp = clamp(player.hp + 1, 0, MAX_HP);
          sfx.collect();
          burst(p.x, p.y, "#ff6b7a", 12, 140);
        }
      }
    }
    for (const p of pickups) {
      if (p.type === "proof" && p.x < -30) {
        p.x = W + 50;
        p.y = rand(90, H - 90);
        p.dead = false;
      }
    }
    pickups = pickups.filter((p) => !p.dead && (p.type === "proof" || p.x > -40));

    if (exitPortal && Math.hypot(player.x - exitPortal.x, player.y - exitPortal.y) < exitPortal.r) {
      score += 200;
      winLevel();
    }

    if (level.proofsNeeded && worldX > level.length + 800 && !exitPortal) {
      // keep scrolling a little; extra proofs already in plan
    }

    updateHud();
  }

  function roundRect(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function drawDragon() {
    ctx.save();
    ctx.translate(player.x, player.y);
    ctx.rotate(player.angle);
    const blink = player.inv > 0 && Math.sin(t * 30) > 0 ? 0.35 : 1;
    ctx.globalAlpha = blink;
    const flap = Math.sin(t * 10) * 0.45;

    ctx.fillStyle = "rgba(77,226,200,0.18)";
    ctx.beginPath();
    ctx.ellipse(-8, 0, 46, 18, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.save();
    ctx.rotate(-0.5 + flap);
    ctx.fillStyle = "#1ec9b0";
    ctx.beginPath();
    ctx.moveTo(-6, 0);
    ctx.quadraticCurveTo(-8, -38, 22, -46);
    ctx.quadraticCurveTo(4, -16, -2, 0);
    ctx.fill();
    ctx.restore();
    ctx.save();
    ctx.rotate(0.5 - flap);
    ctx.fillStyle = "#148f86";
    ctx.beginPath();
    ctx.moveTo(-6, 0);
    ctx.quadraticCurveTo(-8, 38, 22, 46);
    ctx.quadraticCurveTo(4, 16, -2, 0);
    ctx.fill();
    ctx.restore();

    const body = ctx.createLinearGradient(-36, 0, 40, 0);
    body.addColorStop(0, "#0b3b40");
    body.addColorStop(0.5, "#2ee6c8");
    body.addColorStop(1, "#f0c36a");
    ctx.fillStyle = body;
    ctx.beginPath();
    ctx.ellipse(0, 0, 34, 13, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#f3d48a";
    ctx.beginPath();
    ctx.ellipse(28, -2, 14, 10, 0.1, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#12202a";
    ctx.beginPath();
    ctx.arc(34, -4, 2.4, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.beginPath();
    ctx.arc(34.7, -4.6, 0.8, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = "rgba(240,195,106,0.9)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(38, -6);
    ctx.lineTo(48, -14);
    ctx.moveTo(38, 2);
    ctx.lineTo(46, 8);
    ctx.stroke();

    ctx.strokeStyle = "#4de2c8";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(-30, 0);
    for (let i = 1; i <= 8; i++) {
      ctx.lineTo(-30 - i * 8, Math.sin(t * 8 + i) * 6);
    }
    ctx.stroke();

    ctx.restore();
    ctx.globalAlpha = 1;
  }

  function drawBg() {
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, level.bgTop);
    g.addColorStop(1, level.bgBot);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);

    ctx.fillStyle = "#d7e7ff";
    for (const s of stars) {
      s.x -= s.z * 18 * 0.016;
      if (s.x < 0) s.x += W;
      ctx.globalAlpha = 0.25 + s.z * 0.5;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    ctx.strokeStyle = level.accent + "22";
    ctx.lineWidth = 1;
    const off = worldX * 0.25;
    for (let x = -((off % 80)); x < W; x += 80) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, H);
      ctx.stroke();
    }
    for (let y = 0; y < H; y += 80) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(W, y);
      ctx.stroke();
    }

    ctx.fillStyle = level.accent + "18";
    ctx.font = "900 160px sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(level.id, W - 40, 160);
  }

  function drawEntities() {
    for (const p of pickups) {
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.spin);
      if (p.type === "token") {
        ctx.fillStyle = "#f0c36a";
        ctx.beginPath();
        ctx.arc(0, 0, p.r, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "#5b3b0a";
        ctx.font = "bold 10px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(level.id[0], 0, 1);
      } else if (p.type === "proof") {
        ctx.strokeStyle = "#c4b5fd";
        ctx.fillStyle = "rgba(139,92,246,0.35)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
          const a = (Math.PI / 3) * i;
          const fn = i ? ctx.lineTo : ctx.moveTo;
          fn.call(ctx, Math.cos(a) * p.r, Math.sin(a) * p.r);
        }
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      } else {
        ctx.fillStyle = "#e25b6a";
        ctx.beginPath();
        ctx.moveTo(0, 8);
        ctx.bezierCurveTo(-12, 0, -8, -10, 0, -4);
        ctx.bezierCurveTo(8, -10, 12, 0, 0, 8);
        ctx.fill();
      }
      ctx.restore();
    }

    for (const h of hazards) {
      if (h.type === "wall") {
        ctx.fillStyle = "rgba(120,90,255,0.45)";
        ctx.strokeStyle = "#b7a0ff";
        ctx.lineWidth = 2;
        roundRect(h.x, 0, h.w, h.h, 6);
        ctx.fill(); ctx.stroke();
        roundRect(h.x, h.h + h.gap, h.w, H - (h.h + h.gap), 6);
        ctx.fill(); ctx.stroke();
        ctx.fillStyle = "rgba(183,160,255,0.12)";
        ctx.fillRect(h.x + 8, h.h, h.w - 16, h.gap);
        ctx.fillStyle = "#d9ccff";
        ctx.font = "11px sans-serif";
        ctx.fillText("GAS", h.x + 8, h.h - 8);
      } else if (h.type === "wave") {
        ctx.strokeStyle = "#ec796b";
        ctx.shadowColor = "#ec796b";
        ctx.shadowBlur = 12;
        ctx.lineWidth = h.thick;
        ctx.beginPath();
        for (let i = 0; i <= 24; i++) {
          const px = h.x + (i / 24) * h.len;
          const py = h.y + Math.sin(h.phase + i * 0.45) * h.amp;
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.stroke();
        ctx.shadowBlur = 0;
      } else if (h.type === "wormhole") {
        ctx.save();
        ctx.translate(h.x, h.y);
        ctx.rotate(t * 2);
        ctx.strokeStyle = "#b4ff4d";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.ellipse(0, 0, h.r, h.r * 0.55, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.rotate(1);
        ctx.beginPath();
        ctx.ellipse(0, 0, h.r * 0.7, h.r * 0.35, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.restore();
        ctx.globalAlpha = 0.35;
        ctx.strokeStyle = "#b4ff4d";
        ctx.setLineDash([6, 6]);
        ctx.beginPath();
        ctx.moveTo(h.x, h.y);
        ctx.lineTo(h.x, h.pairY);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;
        ctx.beginPath();
        ctx.arc(h.x, h.pairY, 10, 0, Math.PI * 2);
        ctx.stroke();
      }
    }

    for (const e of enemies) {
      ctx.save();
      ctx.translate(e.x, e.y);
      if (e.type === "scout") {
        ctx.fillStyle = "#ff5d73";
        ctx.beginPath();
        ctx.moveTo(12, 0);
        ctx.lineTo(-10, -9);
        ctx.lineTo(-6, 0);
        ctx.lineTo(-10, 9);
        ctx.closePath();
        ctx.fill();
      } else if (e.type === "bot") {
        ctx.fillStyle = "#7dd3fc";
        roundRect(-16, -14, 32, 28, 6);
        ctx.fill();
        ctx.fillStyle = "#08202c";
        ctx.fillRect(-6, -6, 12, 8);
        ctx.fillStyle = "#12aaff";
        ctx.font = "8px sans-serif";
        ctx.fillText("MEV", -10, 16);
      } else if (e.type === "turret") {
        ctx.fillStyle = "#94a3b8";
        ctx.fillRect(-14, -14, 28, 28);
        ctx.fillStyle = "#e2e8f0";
        ctx.fillRect(-28, -5, 20, 10);
      } else if (e.type === "shot") {
        ctx.fillStyle = "#ff8a5b";
        ctx.beginPath();
        ctx.arc(0, 0, e.r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }

    for (const b of bullets) {
      const grd = ctx.createRadialGradient(b.x, b.y, 0, b.x, b.y, 10);
      grd.addColorStop(0, "#fff3c4");
      grd.addColorStop(1, "#ff7a1a00");
      ctx.fillStyle = grd;
      ctx.beginPath();
      ctx.arc(b.x, b.y, 10, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#ffd089";
      ctx.beginPath();
      ctx.arc(b.x, b.y, 4, 0, Math.PI * 2);
      ctx.fill();
    }

    if (exitPortal) {
      ctx.save();
      ctx.translate(exitPortal.x, exitPortal.y);
      ctx.rotate(exitPortal.spin);
      ctx.strokeStyle = level.accent;
      ctx.lineWidth = 4;
      for (let i = 0; i < 3; i++) {
        ctx.beginPath();
        ctx.ellipse(0, 0, exitPortal.r - i * 8, (exitPortal.r - i * 8) * 0.55, i, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.fillStyle = "#fff";
      ctx.font = "bold 12px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("EXIT", 0, 4);
      ctx.restore();
    }

    for (const p of particles) {
      ctx.globalAlpha = p.life / p.max;
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  function draw() {
    ctx.save();
    if (shake > 0) {
      ctx.translate(rand(-shake, shake), rand(-shake, shake));
    }
    drawBg();
    if (state === "play" || state === "pause" || state === "dead" || state === "clear") {
      drawEntities();
      drawDragon();
    } else {
      // title ambience: a drifting dragon
      player.x = W * 0.32 + Math.sin(t * 0.6) * 30;
      player.y = H * 0.42 + Math.cos(t * 0.8) * 24;
      player.angle = Math.sin(t * 0.8) * 0.15;
      drawDragon();
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
      const card = document.createElement("button");
      const isLocked = i >= unlocked;
      card.className = "card" + (isLocked ? " locked" : "");
      card.style.borderColor = lv.accent + "66";
      card.innerHTML = `<div class="id" style="color:${lv.accent}">${lv.id}</div>
        <div class="name">${lv.name}</div>
        <div class="desc">${lv.desc}</div>
        ${isLocked ? '<div class="lock">通关上一关后解锁</div>' : ""}`;
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
    syncHudVisibility();
  }

  function bind() {
    const setKey = (e, down) => {
      const k = e.key.toLowerCase();
      if (k === "w" || k === "arrowup") input.up = down;
      if (k === "s" || k === "arrowdown") input.down = down;
      if (k === "a" || k === "arrowleft") input.left = down;
      if (k === "d" || k === "arrowright") input.right = down;
      if (k === " " || k === "j") {
        input.fire = down;
        e.preventDefault();
      }
      if (down && (k === "enter") && state === "menu") {
        ensureAudio();
        startLevel(0);
      }
      if (down && (k === "p" || k === "escape")) {
        if (state === "play") {
          state = "pause";
          screens.pause.classList.remove("hidden");
          syncHudVisibility();
        } else if (state === "pause") {
          state = "play";
          screens.pause.classList.add("hidden");
          syncHudVisibility();
        }
      }
    };
    window.addEventListener("keydown", (e) => setKey(e, true));
    window.addEventListener("keyup", (e) => setKey(e, false));
    window.addEventListener("mousedown", () => {
      if (state === "play") input.fire = true;
    });
    window.addEventListener("mouseup", () => { input.fire = false; });

    const stickZone = $("stick-zone");
    const fireBtn = $("fire-btn");
    const readStick = (ev) => {
      const rect = stickZone.getBoundingClientRect();
      const touch = ev.touches ? ev.touches[0] : ev;
      const x = (touch.clientX - rect.left) / rect.width * 2 - 1;
      const y = (touch.clientY - rect.top) / rect.height * 2 - 1;
      input.stickX = clamp(x, -1, 1);
      input.stickY = clamp(y, -1, 1);
      input.touching = true;
    };
    stickZone.addEventListener("touchstart", (e) => { readStick(e); e.preventDefault(); }, { passive: false });
    stickZone.addEventListener("touchmove", (e) => { readStick(e); e.preventDefault(); }, { passive: false });
    stickZone.addEventListener("touchend", () => { input.touching = false; input.stickX = 0; input.stickY = 0; });
    fireBtn.addEventListener("touchstart", (e) => { input.fire = true; e.preventDefault(); }, { passive: false });
    fireBtn.addEventListener("touchend", () => { input.fire = false; });

    $("btn-start").addEventListener("click", () => {
      ensureAudio();
      startLevel(0);
    });
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
      syncHudVisibility();
    });
    $("btn-pause-menu").addEventListener("click", goMenu);
    $("btn-retry").addEventListener("click", () => startLevel(levelIndex));
    $("btn-dead-select").addEventListener("click", () => {
      renderLevelGrid();
      hideAllScreens();
      screens.select.classList.remove("hidden");
      state = "select";
      syncHudVisibility();
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
