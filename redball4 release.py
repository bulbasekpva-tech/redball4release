"""
RED BALL 4 (клон на pygame): 150 уровней, 6 миров, сохранение прогресса.
Запуск: python redball4.py   (pygame-ce поставится сам, если его нет)

Управление:
  A/D или стрелки - катиться     Пробел/W/Вверх - прыжок (держи - выше)
  R - заново                     Esc - в меню выбора уровней
Прогресс хранится в файле ~/.redball4_save.json
"""
import json
import math
import os
import random
import subprocess
import sys

try:
    import pygame
except ImportError:
    print("pygame не найден, ставлю pygame-ce...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pygame-ce"])
    import pygame

W, H = 960, 540
GRAV, JUMP, SPRING, MAXV, FALL_Y = 1900, 700, 1150, 300, 780
S = 36  # размер хитбокса шара
TOTAL = 150
SAVE_PATH = os.path.join(os.path.expanduser("~"), ".redball4_save.json")

THEMES = [
    dict(name="Зелёные холмы", sky=((110, 185, 255), (215, 242, 255)), hills=[(120, 195, 140), (88, 165, 112), (60, 135, 90)],
         top=(102, 204, 84), body=(125, 88, 58), edge=(78, 52, 34), night=False),
    dict(name="Пустыня", sky=((255, 165, 95), (255, 228, 175)), hills=[(238, 176, 116), (218, 146, 94), (192, 118, 72)],
         top=(244, 206, 116), body=(196, 136, 84), edge=(140, 92, 56), night=False),
    dict(name="Ледник", sky=((115, 165, 235), (225, 243, 255)), hills=[(205, 228, 252), (168, 203, 242), (132, 178, 228)],
         top=(238, 250, 255), body=(134, 178, 218), edge=(90, 132, 184), night=False),
    dict(name="Ночной лес", sky=((12, 16, 56), (54, 52, 114)), hills=[(44, 48, 104), (32, 36, 84), (22, 26, 64)],
         top=(72, 176, 124), body=(62, 52, 94), edge=(40, 32, 72), night=True),
    dict(name="Вулкан", sky=((58, 8, 20), (206, 74, 30)), hills=[(112, 36, 36), (86, 28, 30), (60, 20, 26)],
         top=(255, 124, 40), body=(72, 42, 48), edge=(40, 22, 28), night=False),
    dict(name="Закатные небеса", sky=((86, 48, 160), (255, 152, 142)), hills=[(152, 92, 172), (122, 72, 152), (92, 56, 132)],
         top=(255, 192, 214), body=(112, 72, 142), edge=(76, 46, 102), night=False),
]


# ------------------------------------------------------------------ сохранение
def load_save():
    d = {"unlocked": 1, "stars": {}, "best": {}, "deaths": 0}
    try:
        with open(SAVE_PATH, encoding="utf-8") as f:
            d.update(json.load(f))
    except Exception:
        pass
    d["unlocked"] = max(1, min(TOTAL, int(d.get("unlocked", 1))))
    return d


def write_save(d):
    try:
        with open(SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception:
        pass


# ------------------------------------------------------------------ логика (без pygame)
class Box:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h

    def hit(self, o):
        return self.x < o.x + o.w and o.x < self.x + self.w and self.y < o.y + o.h and o.y < self.y + self.h


class Mover(Box):
    def __init__(self, x0, y, w, x1):
        super().__init__(x0, y, w, 22)
        self.x0, self.x1, self.t, self.dx = x0, x1, 0.0, 0.0

    def update(self, h):
        self.t += h
        nx = self.x0 + (self.x1 - self.x0) * (0.5 - 0.5 * math.cos(self.t * 1.3))
        self.dx = nx - self.x
        self.x = nx


class Level:
    def __init__(self, n):
        r = random.Random(n * 7919 + 13)
        d = (n - 1) / (TOTAL - 1)
        self.n, self.theme = n, ((n - 1) // 25) % 6
        self.solids, self.movers, self.spikes, self.springs = [], [], [], []
        self.saws, self.stars, self.cands = [], [], []
        top = 400
        self.solids.append(Box(-300, top, 660, 700))
        self.start = (110, top - S)
        x = 360
        segs = int(6 + d * 16)
        for i in range(segs + 1):
            last = i == segs
            if not last and d > 0.1 and r.random() < 0.10 + 0.25 * d:
                gap = r.randint(230, 290)
                mw = 130
                m = Mover(x + 18, top, mw, x + gap - mw - 18)
                self.movers.append(m)
                new_top = top
            else:
                gap = r.randint(50, int(95 + 45 * d)) if not last else r.randint(60, 90)
                new_top = max(260, min(470, top + r.choice([-70, -40, -20, 0, 0, 20, 40, 70])))
                if top - new_top > 40:
                    gap = min(gap, 115)
            x += gap
            w = r.randint(180, 400) if not last else 440
            self.solids.append(Box(x, new_top, w, 700))
            top = new_top
            if last:
                cx = x + w // 2
                self.goal = Box(cx - 16, top - 130, 32, 130)
            else:
                cand = {"x": x + w / 2, "t": top, "spring": False}
                busy = False
                if w >= 280 and r.random() < 0.08 + 0.5 * d:
                    sw = r.choice([40, 60, 80])
                    if w - 240 - sw >= 0:
                        sx = x + r.randint(140, w - 100 - sw)
                        self.spikes.append(Box(sx + 4, top - 18, sw - 8, 18))
                        self.spikes[-1].full = (sx, top, sw)
                        busy = True
                if not busy and w >= 300 and r.random() < 0.05 + 0.4 * d:
                    self.saws.append(dict(x=x + 60.0, y=top - 20, x0=x + 60, x1=x + w - 60, v=80 + 60 * d, dir=1, a=0.0))
                    busy = True
                if not busy and w >= 200 and r.random() < 0.2:
                    self.springs.append(Box(cand["x"] - 20, top - 14, 40, 14))
                    cand["spring"] = True
                self.cands.append(cand)
            x += w
        self.width = x
        for c in r.sample(self.cands, 3):
            y = c["t"] - 14 - 205 if c["spring"] else c["t"] - 85
            self.stars.append(dict(x=c["x"], y=y, got=False))

    def update(self, h):
        for m in self.movers:
            m.update(h)
        for s in self.saws:
            s["x"] += s["dir"] * s["v"] * h
            s["a"] += h * 7
            if s["x"] > s["x1"]:
                s["x"], s["dir"] = s["x1"], -1
            elif s["x"] < s["x0"]:
                s["x"], s["dir"] = s["x0"], 1


class Player:
    def __init__(self, pos):
        self.x, self.y = pos
        self.vx = self.vy = 0.0
        self.on = False
        self.ride = None
        self.coy = self.buf = 0.0
        self.face = 1
        self.ang = self.spin = 0.0

    def box(self):
        return Box(self.x, self.y, S, S)

    def step(self, h, lv, ax, held, jump_req):
        ev = []
        if jump_req:
            self.buf = 0.12
        self.buf -= h
        self.coy = 0.1 if self.on else self.coy - h
        acc = 2300 if self.on else 1300
        if ax:
            self.vx += ax * acc * h
            self.vx = max(-MAXV, min(MAXV, self.vx))
            self.face = ax
        else:
            fr = (1800 if self.on else 250) * h
            self.vx = 0 if abs(self.vx) <= fr else self.vx - math.copysign(fr, self.vx)
        if self.buf > 0 and self.coy > 0:
            self.vy, self.buf, self.coy = -JUMP, 0, 0
            self.on = False
            ev.append("jump")
        if not held and self.vy < -260:
            self.vy = -260
        self.vy = min(self.vy + GRAV * h, 1250)
        if self.ride is not None:
            self.x += self.ride.dx
        solids = lv.solids + lv.movers
        self.x += self.vx * h
        for b in solids:
            if self.box().hit(b):
                if self.vx > 0 or (self.vx == 0 and self.x + S / 2 < b.x + b.w / 2):
                    self.x = b.x - S
                else:
                    self.x = b.x + b.w
                self.vx = 0
        was_on, self.on, self.ride = self.on, False, None
        self.y += self.vy * h
        for b in solids:
            if self.box().hit(b):
                if self.vy >= 0:
                    self.y = b.y - S
                    self.on = True
                    self.ride = b if isinstance(b, Mover) else None
                    if self.vy > 380 and not was_on:
                        ev.append("land")
                else:
                    self.y = b.y + b.h
                self.vy = 0
        for sp in lv.springs:
            if self.vy > 0 and self.box().hit(sp):
                self.vy = -SPRING
                self.on = False
                ev.append("spring")
        # катимся: угловая скорость = линейная / радиус; в воздухе вращение плавно затухает
        self.spin = self.vx / 18 if self.on else self.spin * (1 - 0.4 * h)
        self.ang += self.spin * h
        return ev


def bot_input(p, lv):
    """Грубый бот для самопроверки уровней (не используется в игре)."""
    ahead = p.x + S + 55
    floor_ahead = any(b.x <= ahead <= b.x + b.w and b.y <= p.y + S + 80 for b in lv.solids + lv.movers)
    danger = any(sp.x - 130 < p.x + S < sp.x + 20 for sp in lv.spikes)
    danger |= any(abs(s["x"] - p.x) < 120 and s["x"] > p.x - 40 for s in lv.saws)
    wall = any(b.x > p.x + S and b.x < p.x + S + 24 and b.y < p.y + S - 4 for b in lv.solids)
    return 1, True, p.on and (not floor_ahead or danger or wall)


# ------------------------------------------------------------------ графика
def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make_sky(theme):
    s = pygame.Surface((W, H))
    a, b = THEMES[theme]["sky"]
    for y in range(H):
        pygame.draw.line(s, lerp(a, b, y / H), (0, y), (W, y))
    return s


def make_vignette():
    sm = pygame.Surface((96, 54), pygame.SRCALPHA)
    for y in range(54):
        for x in range(96):
            d = math.hypot((x / 96 - 0.5) * 2, (y / 54 - 0.5) * 2) / 1.41
            sm.set_at((x, y), (0, 0, 20, int(150 * max(0, (d - 0.45) / 0.55) ** 1.5)))
    return pygame.transform.smoothscale(sm, (W, H))


def make_ball(r=18):
    """Тело шара с узором (вращается, чтобы было видно качение)."""
    n = r * 2 + 4
    c = r + 2
    s = pygame.Surface((n, n), pygame.SRCALPHA)
    pygame.draw.circle(s, (214, 24, 36), (c, c), r)
    pygame.draw.rect(s, (150, 8, 22), (0, c - 3, n, 6))
    pygame.draw.rect(s, (150, 8, 22), (c - 3, 0, 6, n))
    for dx, dy in ((9, -9), (-9, 8), (10, 9), (-9, -9)):
        pygame.draw.circle(s, (255, 190, 175), (c + dx, c + dy), 3)
    mask = pygame.Surface((n, n), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (c, c), r)
    s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    pygame.draw.circle(s, (70, 0, 6), (c, c), r, 2)
    return s


def make_shade(r=18):
    """Неподвижный слой: тень справа-снизу и блик слева-сверху."""
    n = r * 2 + 4
    c = r + 2
    s = pygame.Surface((n, n), pygame.SRCALPHA)
    for i in range(r, 0, -1):
        t = 1 - i / r
        off = (r - i) * 0.38
        if t < 0.55:
            col = (10, 0, 20, int(95 * (1 - t / 0.55)))
        else:
            col = (255, 255, 255, int(110 * ((t - 0.55) / 0.45) ** 1.5))
        pygame.draw.circle(s, col, (int(c - off), int(c - off)), i)
    gloss = pygame.Surface((n, n), pygame.SRCALPHA)
    pygame.draw.ellipse(gloss, (255, 255, 255, 120), (c - r * 0.65, c - r * 0.78, r * 0.7, r * 0.42))
    s.blit(gloss, (0, 0))
    return s


def make_glow(r, col):
    s = pygame.Surface((r * 2, r * 2))
    s.fill((0, 0, 0))
    for i in range(r, 0, -2):
        k = (1 - i / r) ** 2 * 0.6
        pygame.draw.circle(s, tuple(int(c * k) for c in col), (r, r), i)
    return s


def star_poly(cx, cy, r, rot=0.0):
    pts = []
    for i in range(10):
        a = rot - math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    return pts


class Game:
    def __init__(self):
        pygame.init()
        try:
            self.scr = pygame.display.set_mode((W, H), pygame.SCALED | pygame.RESIZABLE)
        except Exception:
            self.scr = pygame.display.set_mode((W, H))
        pygame.display.set_caption("Red Ball 4")
        self.clock = pygame.time.Clock()
        names = "arial,segoeui,dejavusans,liberationsans,freesans,notosans,ubuntu"
        self.fs = pygame.font.SysFont(names, 22, True)
        self.fm = pygame.font.SysFont(names, 34, True)
        self.fb = pygame.font.SysFont(names, 92, True)
        self.save = load_save()
        self.ball = make_ball(18)
        self.shade = make_shade(18)
        self.skies = [make_sky(i) for i in range(len(THEMES))]
        self.vig = make_vignette()
        self.glow = make_glow(40, (255, 220, 90))
        self.state = "menu"
        self.sel = self.save["unlocked"]
        self.parts, self.t, self.shake = [], 0.0, 0.0
        rr = random.Random(5)
        self.clouds = [(rr.random() * 1500, rr.randint(30, 230), rr.uniform(0.6, 1.4)) for _ in range(9)]
        self.nstars = [(rr.randint(0, W), rr.randint(0, 330), rr.random() * 6) for _ in range(110)]
        self.jump_req = False

    # ---------- уровни
    def start(self, n):
        self.n = n
        self.lv = Level(n)
        self.p = Player(self.lv.start)
        self.cx, self.cy = self.p.x - W * 0.4, 100.0
        self.time, self.dead_t = 0.0, 0.0
        self.state = "play"
        self.parts.clear()

    def burst(self, x, y, col, n=18, sp=260):
        for _ in range(n):
            a, v = random.uniform(0, 6.283), random.uniform(0.2, 1) * sp
            self.parts.append([x, y, math.cos(a) * v, math.sin(a) * v - 80, random.uniform(0.4, 0.9), 0.9, col, random.uniform(2, 5)])

    def die(self):
        self.state = "dead"
        self.dead_t = 0.9
        self.shake = 0.35
        self.save["deaths"] += 1
        self.burst(self.p.x + S / 2, self.p.y + S / 2, (230, 30, 40), 36, 380)

    def win(self):
        got = sum(s["got"] for s in self.lv.stars)
        key = str(self.n)
        self.save["stars"][key] = max(self.save["stars"].get(key, 0), got)
        if key not in self.save["best"] or self.time < self.save["best"][key]:
            self.save["best"][key] = round(self.time, 2)
        self.save["unlocked"] = max(self.save["unlocked"], min(TOTAL, self.n + 1))
        write_save(self.save)
        self.state = "win"
        self.won_stars = got
        self.burst(self.p.x + S / 2, self.p.y, (255, 220, 80), 50, 420)

    # ---------- обновление
    def update(self, dt):
        self.t += dt
        self.shake = max(0, self.shake - dt)
        for q in self.parts:
            q[0] += q[2] * dt
            q[1] += q[3] * dt
            q[3] += 900 * dt
            q[4] -= dt
        self.parts = [q for q in self.parts if q[4] > 0]
        if self.state == "dead":
            self.dead_t -= dt
            if self.dead_t <= 0:
                self.start(self.n)
            return
        if self.state != "play":
            return
        k = pygame.key.get_pressed()
        ax = int(bool(k[pygame.K_d] or k[pygame.K_RIGHT])) - int(bool(k[pygame.K_a] or k[pygame.K_LEFT]))
        held = bool(k[pygame.K_SPACE] or k[pygame.K_w] or k[pygame.K_UP])
        lv, p = self.lv, self.p
        n = int(dt / (1 / 120)) + 1
        h = dt / n
        for _ in range(n):
            lv.update(h)
            for ev in p.step(h, lv, ax, held, self.jump_req):
                cx, cy = p.x + S / 2, p.y + S
                if ev == "jump":
                    self.burst(cx, cy, (240, 240, 240), 6, 90)
                elif ev == "land":
                    self.burst(cx, cy, (230, 230, 230), 8, 120)
                elif ev == "spring":
                    self.burst(cx, cy, (255, 220, 80), 14, 200)
            self.jump_req = False
        if p.on and abs(p.vx) > 180 and random.random() < 0.3:
            self.burst(p.x + S / 2 - math.copysign(10, p.vx), p.y + S, (235, 235, 235), 1, 50)
        self.time += dt
        pb = Box(p.x + 5, p.y + 5, S - 10, S - 10)
        for sp in lv.spikes:
            if pb.hit(sp):
                return self.die()
        for sw in lv.saws:
            nx, ny = max(pb.x, min(sw["x"], pb.x + pb.w)), max(pb.y, min(sw["y"], pb.y + pb.h))
            if math.hypot(nx - sw["x"], ny - sw["y"]) < 20:
                return self.die()
        if p.y > FALL_Y:
            return self.die()
        for s in lv.stars:
            if not s["got"] and math.hypot(s["x"] - (p.x + S / 2), s["y"] - (p.y + S / 2)) < 32:
                s["got"] = True
                self.burst(s["x"], s["y"], (255, 225, 90), 20, 240)
        if pb.hit(lv.goal):
            return self.win()
        tx = p.x - W * 0.4 + p.vx * 0.3
        ty = max(-200, min(220, p.y - H * 0.55))
        k2 = min(1, dt * 6)
        self.cx += (tx - self.cx) * k2
        self.cy += (ty - self.cy) * k2

    # ---------- рисование мира
    def txt(self, font, t, pos, col=(255, 255, 255), center=False):
        img = font.render(t, True, col)
        r = img.get_rect()
        if center:
            r.center = pos
        else:
            r.topleft = pos
        self.scr.blit(font.render(t, True, (0, 0, 0)), (r.x + 2, r.y + 3))
        self.scr.blit(img, r)
        return r

    def hills(self, col, base, amp, freq, par, seed):
        pts = [(0, H)]
        for sx in range(0, W + 41, 40):
            wx = sx + self.cx * par
            y = base - self.cy * par * 0.3 - amp * (0.55 * math.sin(wx * freq + seed) + 0.3 * math.sin(wx * freq * 2.3 + seed * 2) + 0.15)
            pts.append((sx, y))
        pts.append((W, H))
        pygame.draw.polygon(self.scr, col, pts)

    def background(self, th):
        T = THEMES[th]
        self.scr.blit(self.skies[th], (0, 0))
        if T["night"]:
            for x, y, ph in self.nstars:
                b = 150 + int(105 * math.sin(self.t * 2 + ph))
                pygame.draw.circle(self.scr, (b, b, min(255, b + 20)), (x, y), 1 + (ph > 5))
            pygame.draw.circle(self.scr, (250, 246, 220), (780, 90), 34)
            pygame.draw.circle(self.scr, T["sky"][0], (794, 80), 30)
        else:
            sun = (255, 240, 190) if th != 4 else (255, 150, 60)
            pygame.draw.circle(self.scr, sun, (190, 110), 46)
            for x, y, sc in self.clouds:
                px = (x - self.cx * 0.25 - self.t * 8) % (W + 400) - 200
                for dx, dy, rr in ((0, 0, 28), (30, -10, 34), (62, 2, 26), (30, 8, 30)):
                    pygame.draw.circle(self.scr, (255, 255, 255), (int(px + dx * sc), int(y + dy * sc)), int(rr * sc))
        for i, c in enumerate(T["hills"]):
            self.hills(c, 330 + i * 70, 90 - i * 18, 0.004 + i * 0.002, 0.12 + i * 0.18, i * 1.7)

    def draw_world(self, th):
        T, lv, cx, cy = THEMES[th], self.lv, int(self.cx), int(self.cy)
        view = Box(cx - 50, cy - 50, W + 100, H + 100)
        for b in lv.solids:
            if not view.hit(b):
                continue
            x, y = int(b.x - cx), int(b.y - cy)
            bh = max(1, min(b.h, H - y + 10))
            pygame.draw.rect(self.scr, T["body"], (x, y, b.w, bh))
            for ly in range(y + 40, H + 10, 36):
                pygame.draw.line(self.scr, T["edge"], (x, ly), (x + b.w, ly), 1)
            pygame.draw.rect(self.scr, T["edge"], (x, y, b.w, bh), 3)
            pygame.draw.rect(self.scr, T["top"], (x - 2, y - 3, b.w + 4, 15), border_radius=7)
            hi = lerp(T["top"], (255, 255, 255), 0.35)
            pygame.draw.line(self.scr, hi, (x + 6, y), (x + b.w - 6, y), 2)
            for gx in range(x + 8, x + b.w - 8, 22):
                pygame.draw.polygon(self.scr, lerp(T["top"], (0, 0, 0), 0.15), [(gx, y + 11), (gx + 5, y + 22), (gx + 10, y + 11)])
        for m in lv.movers:
            x, y = int(m.x - cx), int(m.y - cy)
            pygame.draw.rect(self.scr, (70, 78, 96), (x, y + 4, m.w, m.h), border_radius=8)
            pygame.draw.rect(self.scr, (176, 188, 208), (x, y, m.w, m.h - 4), border_radius=8)
            pygame.draw.rect(self.scr, (236, 242, 250), (x + 4, y + 2, m.w - 8, 4), border_radius=3)
            for rx in (x + 12, x + m.w - 12):
                pygame.draw.circle(self.scr, (90, 98, 118), (rx, y + 9), 3)
        for sp in lv.springs:
            x, y = int(sp.x - cx), int(sp.y - cy)
            comp = 3 if self.p.vy < -600 else 0
            pygame.draw.rect(self.scr, (90, 90, 100), (x + 4, y + 8, 32, 6), border_radius=2)
            for i in range(3):
                pygame.draw.line(self.scr, (200, 200, 210), (x + 8, y + 8 - i * 3), (x + 32, y + 5 - i * 3), 2)
            pygame.draw.rect(self.scr, (255, 90, 70), (x, y + comp, 40, 6), border_radius=3)
        for sp in lv.spikes:
            sx, st, sw = sp.full
            for i in range(sw // 20):
                x, y = int(sx + i * 20 - cx), int(st - cy)
                pygame.draw.polygon(self.scr, (150, 156, 170), [(x, y), (x + 10, y - 24), (x + 20, y)])
                pygame.draw.polygon(self.scr, (225, 230, 240), [(x + 10, y - 24), (x + 20, y), (x + 13, y)])
                pygame.draw.polygon(self.scr, (60, 64, 76), [(x, y), (x + 10, y - 24), (x + 20, y)], 2)
        for s in lv.saws:
            x, y = int(s["x"] - cx), int(s["y"] - cy)
            pts = []
            for i in range(20):
                a = s["a"] + i * math.pi / 10
                r = 24 if i % 2 == 0 else 17
                pts.append((x + math.cos(a) * r, y + math.sin(a) * r))
            pygame.draw.polygon(self.scr, (190, 196, 208), pts)
            pygame.draw.polygon(self.scr, (70, 74, 88), pts, 2)
            pygame.draw.circle(self.scr, (120, 126, 140), (x, y), 8)
            pygame.draw.circle(self.scr, (60, 64, 76), (x, y), 3)
        for s in lv.stars:
            if s["got"]:
                continue
            x, y = int(s["x"] - cx), int(s["y"] - cy + math.sin(self.t * 3 + s["x"]) * 5)
            self.scr.blit(self.glow, (x - 40, y - 40), special_flags=pygame.BLEND_ADD)
            pygame.draw.polygon(self.scr, (255, 214, 60), star_poly(x, y, 16, math.sin(self.t * 2) * 0.2))
            pygame.draw.polygon(self.scr, (190, 120, 10), star_poly(x, y, 16, math.sin(self.t * 2) * 0.2), 2)
        g = lv.goal
        gx, gy = int(g.x - cx), int(g.y - cy)
        pygame.draw.rect(self.scr, (235, 235, 240), (gx + 13, gy, 6, g.h))
        pygame.draw.circle(self.scr, (255, 214, 60), (gx + 16, gy), 7)
        pts = [(gx + 19, gy + 8)]
        for i in range(0, 41, 8):
            pts.append((gx + 19 + i, gy + 8 + math.sin(self.t * 5 + i * 0.2) * 3))
        for i in range(40, -1, -8):
            pts.append((gx + 19 + i, gy + 34 + math.sin(self.t * 5 + i * 0.2) * 3))
        pygame.draw.polygon(self.scr, (235, 50, 60), pts)
        pygame.draw.polygon(self.scr, (120, 10, 20), pts, 2)

    def blit_ball(self, x, y, ang, st, size, look, down):
        k = size / 40
        body = pygame.transform.rotozoom(self.ball, -math.degrees(ang), k)
        w, h = max(2, int(body.get_width() * (1 - st))), max(2, int(body.get_height() * (1 + st)))
        self.scr.blit(pygame.transform.smoothscale(body, (w, h)), (int(x - w / 2), int(y - h / 2)))
        sw, sh = max(2, int(size * (1 - st))), max(2, int(size * (1 + st)))
        self.scr.blit(pygame.transform.smoothscale(self.shade, (sw, sh)), (int(x - sw / 2), int(y - sh / 2)))
        blink = (self.t % 3.2) < 0.12
        for ex in (-7, 7):
            px, py = int(x + (ex + look * 3) * k), int(y - 4 * k)
            if blink:
                pygame.draw.line(self.scr, (40, 0, 0), (px - 5 * k, py), (px + 5 * k, py), 2)
            else:
                pygame.draw.ellipse(self.scr, (255, 255, 255), (px - 5 * k, py - 7 * k, 10 * k, 14 * k))
                pygame.draw.circle(self.scr, (15, 15, 25), (int(px + look * 2.5 * k), int(py + (1 + down) * k)), max(2, int(3 * k)))

    def draw_ball(self):
        p, cx, cy = self.p, int(self.cx), int(self.cy)
        x, y = p.x + S / 2 - cx, p.y + S / 2 - cy
        best = None
        for b in self.lv.solids + self.lv.movers:
            if b.x < p.x + S and p.x < b.x + b.w and b.y >= p.y + S - 4 and (best is None or b.y < best):
                best = b.y
        if best is not None:
            dist = best - (p.y + S)
            a = max(20, 110 - dist * 0.4)
            sh = pygame.Surface((50, 14), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (0, 0, 0, int(a)), (0, 0, 50, 14))
            sc = max(0.4, 1 - dist / 400)
            sh = pygame.transform.smoothscale(sh, (int(50 * sc), int(14 * sc)))
            self.scr.blit(sh, (int(x - sh.get_width() / 2), int(best - cy - 6)))
        st = min(abs(p.vy), 900) / 900 * 0.16
        self.blit_ball(x, y + 2, p.ang, st, 40, max(-1, min(1, p.vx / MAXV)), p.vy > 200)

    def hud(self):
        self.txt(self.fm, f"Уровень {self.n}", (20, 12))
        self.txt(self.fs, THEMES[self.lv.theme]["name"], (22, 52), (255, 255, 255))
        for i, s in enumerate(self.lv.stars):
            c = (255, 214, 60) if s["got"] else (60, 64, 80)
            pts = star_poly(W - 150 + i * 44 + 20, 34, 15)
            pygame.draw.polygon(self.scr, c, pts)
            pygame.draw.polygon(self.scr, (20, 20, 30), pts, 2)
        self.txt(self.fs, f"{self.time:5.1f} c", (W - 150, 58))

    def draw_play(self):
        th = self.lv.theme
        self.background(th)
        off = (random.randint(-4, 4), random.randint(-4, 4)) if self.shake > 0 else (0, 0)
        if off != (0, 0):
            self.cx += off[0] * 0.5
            self.cy += off[1] * 0.5
        self.draw_world(th)
        if self.state != "dead":
            self.draw_ball()
        for q in self.parts:
            f = max(0, q[4] / q[5])
            pygame.draw.circle(self.scr, q[6], (int(q[0] - self.cx), int(q[1] - self.cy)), max(1, int(q[7] * f)))
        self.scr.blit(self.vig, (0, 0))
        self.hud()
        if self.state == "win":
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((10, 14, 40, 170))
            self.scr.blit(ov, (0, 0))
            done = self.n >= TOTAL
            self.txt(self.fm, "Игра пройдена! Все 150 уровней!" if done else "Уровень пройден!", (W // 2, 140), (255, 230, 120), True)
            for i in range(3):
                pts = star_poly(W // 2 - 70 + i * 70, 230, 30)
                pygame.draw.polygon(self.scr, (255, 214, 60) if i < self.won_stars else (70, 74, 96), pts)
                pygame.draw.polygon(self.scr, (20, 20, 30), pts, 3)
            self.txt(self.fs, f"Время: {self.time:.1f} c   Рекорд: {self.save['best'][str(self.n)]:.1f} c", (W // 2, 300), center=True)
            self.txt(self.fs, "Enter - дальше    R - ещё раз    Esc - уровни" if not done else "R - ещё раз    Esc - уровни", (W // 2, 360), center=True)

    # ---------- меню
    def cell(self, i):
        j = i - self.page * 30
        return pygame.Rect(66 + (j % 6) * 140, 90 + (j // 6) * 82, 128, 70)

    def draw_menu(self):
        self.scr.blit(self.skies[0], (0, 0))
        self.cx, self.cy = self.t * 60, 0
        for i, c in enumerate(THEMES[0]["hills"]):
            self.hills(c, 360 + i * 60, 90 - i * 15, 0.004 + i * 0.002, 0.2 + i * 0.2, i * 1.7)
        self.txt(self.fb, "RED BALL 4", (W // 2, 120), (255, 255, 255), True)
        by = 300 - abs(math.sin(self.t * 3)) * 90
        sh = pygame.Surface((60, 16), pygame.SRCALPHA)
        pygame.draw.ellipse(sh, (0, 0, 0, 90), (0, 0, 60, 16))
        self.scr.blit(sh, (W // 2 - 30, 352))
        self.blit_ball(W // 2, int(by) + 30, self.t * 4, 0.0, 60, 0.0, False)
        tot = sum(self.save["stars"].values())
        self.txt(self.fm, f"Enter - продолжить (уровень {self.save['unlocked']})", (W // 2, 410), center=True)
        self.txt(self.fs, "L - выбор уровня     Esc - выход", (W // 2, 455), center=True)
        self.txt(self.fs, f"Звёзды: {tot} / {TOTAL * 3}     Падений: {self.save['deaths']}", (W // 2, 495), center=True)
        self.scr.blit(self.vig, (0, 0))

    def draw_select(self):
        th = ((self.sel - 1) // 25) % 6
        self.scr.blit(self.skies[th], (0, 0))
        self.txt(self.fm, f"Выбор уровня: {THEMES[th]['name']}", (W // 2, 40), center=True)
        for i in range(self.page * 30 + 1, min(TOTAL, self.page * 30 + 30) + 1):
            r = self.cell(i)
            ok = i <= self.save["unlocked"]
            col = (255, 255, 255) if ok else (90, 96, 120)
            pygame.draw.rect(self.scr, (20, 24, 60) if not ok else (30, 40, 110), r.move(0, 4), border_radius=12)
            pygame.draw.rect(self.scr, (60, 70, 100) if not ok else (70, 110, 240), r, border_radius=12)
            if i == self.sel:
                pygame.draw.rect(self.scr, (255, 214, 60), r.inflate(8, 8), 4, border_radius=14)
            self.txt(self.fm, str(i), (r.centerx, r.y + 24), col, True)
            n = self.save["stars"].get(str(i), 0)
            for k in range(3):
                pts = star_poly(r.centerx - 26 + k * 26, r.y + 54, 9)
                pygame.draw.polygon(self.scr, (255, 214, 60) if k < n else (45, 50, 80), pts)
        self.txt(self.fs, f"Страница {self.page + 1} / 5   стрелки - выбор, Enter - играть, Esc - меню", (W // 2, 515), center=True)
        self.scr.blit(self.vig, (0, 0))

    # ---------- события
    def go_sel(self, v):
        self.sel = max(1, min(TOTAL, v))
        self.page = (self.sel - 1) // 30

    def events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            if e.type == pygame.KEYDOWN:
                k = e.key
                if self.state == "menu":
                    if k in (pygame.K_RETURN, pygame.K_SPACE):
                        self.start(self.save["unlocked"])
                    elif k == pygame.K_l:
                        self.state = "select"
                        self.go_sel(self.save["unlocked"])
                    elif k == pygame.K_ESCAPE:
                        return False
                elif self.state == "select":
                    d = {pygame.K_LEFT: -1, pygame.K_RIGHT: 1, pygame.K_UP: -6, pygame.K_DOWN: 6}.get(k)
                    if d:
                        self.go_sel(self.sel + d)
                    elif k in (pygame.K_RETURN, pygame.K_SPACE) and self.sel <= self.save["unlocked"]:
                        self.start(self.sel)
                    elif k == pygame.K_ESCAPE:
                        self.state = "menu"
                else:
                    if k in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
                        self.jump_req = True
                    elif k == pygame.K_r:
                        self.start(self.n)
                    elif k == pygame.K_ESCAPE:
                        self.state = "select"
                        self.go_sel(self.n)
                    elif k == pygame.K_RETURN and self.state == "win" and self.n < TOTAL:
                        self.start(self.n + 1)
            if self.state == "select" and e.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
                for i in range(self.page * 30 + 1, min(TOTAL, self.page * 30 + 30) + 1):
                    if self.cell(i).collidepoint(e.pos):
                        self.sel = i
                        if e.type == pygame.MOUSEBUTTONDOWN and i <= self.save["unlocked"]:
                            self.start(i)
                        break
            if self.state == "select" and e.type == pygame.MOUSEWHEEL:
                self.go_sel(self.sel - e.y * 30)
        return True

    def run(self):
        while self.events():
            dt = min(self.clock.tick(60) / 1000, 1 / 30)
            if self.state == "menu":
                self.t += dt
                self.draw_menu()
            elif self.state == "select":
                self.t += dt
                self.draw_select()
            else:
                self.update(dt)
                self.draw_play()
            pygame.display.flip()
        write_save(self.save)
        pygame.quit()


if __name__ == "__main__":
    try:
        Game().run()
    except Exception:
        import traceback
        traceback.print_exc()
        input("\nОшибка! Скопируй текст выше и отправь мне. Enter - закрыть...")
