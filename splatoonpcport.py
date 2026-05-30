#!/usr/bin/env python3
"""AC's Splatoon 4K — Splatoon PC port (FILES=OFF · # pr).

Procedural stages · raycast ink engine · Switch→PC keybindings.
Python 3.10+ · pygame + math only · no asset files.
"""

from __future__ import annotations

import array
import math
import random
import sys
from dataclasses import dataclass

try:
    import pygame
except ImportError:
    print("Install pygame: pip install pygame-ce")
    sys.exit(1)

# --- Display ---
WIDTH, HEIGHT = 900, 600
HALF_HEIGHT = HEIGHT // 2
FPS = 60
APP_NAME = "AC's Splatoon 4K PC Port"
VERSION = "0.1"
ENGINE = "ink_raycast"
WINDOW_TITLE = f"{APP_NAME} {VERSION} by ac · FILES=OFF"

# Splatoon Switch → PC port bindings (# pr · no config files)
PC_BIND: list[tuple[str, str, str]] = [
    ("Move", "WASD / Arrows", "Left stick"),
    ("Look / Aim", "Mouse", "Right stick"),
    ("Shoot ink (ZR)", "Left mouse · hold", "ZR"),
    ("Sub burst", "Right mouse", "Sub weapon"),
    ("Jump (B)", "Space", "B"),
    ("Squid form (ZL)", "Ctrl / C · hold", "ZL"),
    ("Special ink", "E", "R stick click"),
    ("Toggle map", "Tab", "D-Pad"),
    ("Pause", "Esc", "+"),
    ("Start / confirm", "Enter / Space", "A"),
]

MOUSE_SENS = 0.0032
WALK_SPEED = 2.8
SQUID_SPEED = 5.2
INK_REGEN = 0.15

# Splatoon 2 jump (kid form · ground only · FILES=OFF physics)
JUMP_VEL = 10.5
GRAVITY_Z = 32.0
MAX_JUMP_Z = 28.0
AIR_CONTROL = 0.55
COYOTE_TIME = 0.12
LAND_SPLAT_R = 22.0

MENU_ITEMS = (
    "HELP",
    "PLAY GAME",
    "EXIT",
    "CONTROLS",
    "SOUND",
    "SETTINGS",
    "ABOUT",
)

FOV = math.pi / 3
NUM_RAYS = 160
MAX_DEPTH = 900
DELTA_ANGLE = FOV / NUM_RAYS
DIST = NUM_RAYS / (2 * math.tan(FOV / 2))
PROJ_COEFF = 3 * DIST * 44
TILE = 64

# --- Splatoon palette (procedural · # pr) ---
BG = (12, 14, 22)
SKY = (18, 22, 38)
FLOOR = (22, 26, 36)
INK_PLAYER = (50, 120, 255)
INK_ENEMY = (255, 80, 80)
WALL_BASE = (72, 76, 88)
WALL_TOP = (110, 114, 128)
TEXT = (220, 230, 255)
GOLD = (255, 210, 60)


@dataclass
class Settings:
    sound_on: bool = True
    volume: float = 0.7
    mouse_sens: float = MOUSE_SENS
    show_minimap: bool = True


def _make_beep(freq: float, ms: int, vol: float) -> pygame.mixer.Sound | None:
    try:
        sr = 22050
        n = int(sr * ms / 1000)
        buf = array.array("h")
        phase = 0.0
        step = freq / sr
        for i in range(n):
            phase = (phase + step) % 1.0
            raw = 1.0 if phase < 0.25 else -1.0
            fade = 1.0 - i / max(1, n - 1)
            buf.append(int(max(-32768, min(32767, raw * fade * vol * 9000))))
        return pygame.mixer.Sound(buffer=buf)
    except (pygame.error, ValueError, OSError):
        return None


class Sfx:
    def __init__(self) -> None:
        self.menu = _make_beep(660, 60, 0.25)
        self.confirm = _make_beep(880, 90, 0.3)
        self.ink = _make_beep(520, 40, 0.15)
        self.special = _make_beep(440, 120, 0.35)
        self.jump = _make_beep(740, 70, 0.28)
        self.land = _make_beep(320, 50, 0.2)

    def play(self, snd: pygame.mixer.Sound | None, settings: Settings) -> None:
        if not settings.sound_on or snd is None:
            return
        try:
            snd.set_volume(settings.volume)
            snd.play()
        except pygame.error:
            pass


# 1 = wall · 0 = inkable turf · 2 = spawn pad (walkable)
# Layouts inspired by Splatoon 1/2 stages (YouTube pseudo-3D recreations)
MAPS: list[dict] = [
    {
        "name": "Urchin Underpass",
        "theme": "underpass",
        "floor": (28, 32, 48),
        "wall": (68, 72, 82),
        "accent": (80, 160, 255),
        "spawn": (2, 2),
        "grid": [
            "11111111111111111111",
            "10000000001100000001",
            "10011111001101111101",
            "10010001001101000101",
            "10010001001101000101",
            "10011111001101111101",
            "10000000000000000001",
            "11111110001111111111",
            "10000000001100000001",
            "10011111001101111101",
            "10010001001101000101",
            "10010001001101000101",
            "10011111001101111101",
            "10000000000000000001",
            "11111111111111111111",
        ],
    },
    {
        "name": "Saltspray Rig",
        "theme": "rig",
        "floor": (32, 38, 52),
        "wall": (90, 95, 105),
        "accent": (255, 140, 50),
        "spawn": (2, 7),
        "grid": [
            "11111111111111111111",
            "10000000000000000001",
            "10001111111111111001",
            "10001000000000001001",
            "10001001111111001001",
            "10001001000001001001",
            "10001001000001001001",
            "10001001111111001001",
            "10001000000000001001",
            "10001111111111111001",
            "10000000000000000001",
            "11111111111111111111",
        ],
    },
    {
        "name": "Blackbelly Skatepark",
        "theme": "skatepark",
        "floor": (36, 34, 44),
        "wall": (78, 70, 88),
        "accent": (255, 90, 180),
        "spawn": (2, 2),
        "grid": [
            "11111111111111111111",
            "10000000000000000001",
            "10011100000011100001",
            "10010000000000100001",
            "10010001111100100001",
            "10010001000100100001",
            "10010001000100100001",
            "10010001111100100001",
            "10010000000000100001",
            "10011100000011100001",
            "10000000000000000001",
            "11111111111111111111",
        ],
    },
    {
        "name": "Walleye Warehouse",
        "theme": "warehouse",
        "floor": (40, 36, 32),
        "wall": (95, 88, 72),
        "accent": (255, 200, 40),
        "spawn": (2, 2),
        "grid": [
            "11111111111111111111",
            "10000000000000000001",
            "10111101111101111001",
            "10100001000101000101",
            "10100001000101000101",
            "10111101111101111001",
            "10000000000000000001",
            "10111101111101111001",
            "10100001000101000101",
            "10100001000101000101",
            "10111101111101111001",
            "10000000000000000001",
            "11111111111111111111",
        ],
    },
    {
        "name": "Moray Towers",
        "theme": "towers",
        "floor": (30, 34, 50),
        "wall": (100, 105, 120),
        "accent": (120, 255, 160),
        "spawn": (9, 9),
        "grid": [
            "11111111111111111111",
            "10000000000000000001",
            "10001111111111111001",
            "10001000000000001001",
            "10001001111111001001",
            "10001001000101001001",
            "10001001000101001001",
            "10001001111111001001",
            "10001000000000001001",
            "10001111111111111001",
            "10000000000000000001",
            "11111111111111111111",
        ],
    },
    {
        "name": "Kelp Dome",
        "theme": "dome",
        "floor": (24, 42, 38),
        "wall": (60, 100, 88),
        "accent": (180, 255, 120),
        "spawn": (10, 10),
        "grid": [
            "11111111111111111111",
            "11100000000000000111",
            "11000000000000000011",
            "10000011111111000001",
            "10000100000000100001",
            "10000101111110100001",
            "10000101000101000001",
            "10000101111110100001",
            "10000100000000100001",
            "10000011111111000001",
            "11000000000000000011",
            "11100000000000000111",
            "11111111111111111111",
        ],
    },
    {
        "name": "Camp Triggerfish",
        "theme": "camp",
        "floor": (48, 42, 34),
        "wall": (88, 76, 58),
        "accent": (255, 120, 80),
        "spawn": (2, 6),
        "grid": [
            "11111111111111111111",
            "10000000000000000001",
            "10011100000011100001",
            "10010000000000100001",
            "10010000000000100001",
            "10011100000011100001",
            "10000000000000000001",
            "10001111111111111001",
            "10001000000000001001",
            "10001000000000001001",
            "10001111111111111001",
            "10000000000000000001",
            "11111111111111111111",
        ],
    },
    {
        "name": "Arowana Mall",
        "theme": "mall",
        "floor": (38, 36, 42),
        "wall": (120, 118, 125),
        "accent": (255, 100, 200),
        "spawn": (2, 2),
        "grid": [
            "11111111111111111111",
            "10000000000000000001",
            "10000011111111000001",
            "10000010000001000001",
            "10000010000001000001",
            "10000011111111000001",
            "10000000000000000001",
            "10000011111111000001",
            "10000010000001000001",
            "10000010000001000001",
            "10000011111111000001",
            "10000000000000000001",
            "11111111111111111111",
        ],
    },
]


def parse_map(spec: dict) -> tuple[list[list[int]], int, int]:
    rows = spec["grid"]
    h = len(rows)
    w = max(len(r) for r in rows)
    grid: list[list[int]] = []
    for row in rows:
        line = [int(c) for c in row.ljust(w, "1")]
        grid.append(line)
    return grid, w, h


class Stage:
    def __init__(self, spec: dict) -> None:
        self.name = spec["name"]
        self.theme = spec["theme"]
        self.floor_col = spec["floor"]
        self.wall_col = spec["wall"]
        self.accent = spec["accent"]
        self.grid, self.w, self.h = parse_map(spec)
        sx, sy = spec["spawn"]
        self.spawn_x = sx * TILE + TILE // 2
        self.spawn_y = sy * TILE + TILE // 2
        self.ink: list[list[int]] = [[0 for _ in range(self.w)] for _ in range(self.h)]

    def tile(self, gx: int, gy: int) -> int:
        if 0 <= gy < self.h and 0 <= gx < self.w:
            return self.grid[gy][gx]
        return 1

    def is_wall(self, x: float, y: float) -> bool:
        return self.tile(int(x // TILE), int(y // TILE)) == 1

    def splat(self, x: float, y: float, team: int = 1) -> None:
        gx, gy = int(x // TILE), int(y // TILE)
        if 0 <= gy < self.h and 0 <= gx < self.w and self.grid[gy][gx] == 0:
            self.ink[gy][gx] = team

    def on_team_ink(self, x: float, y: float, team: int = 1) -> bool:
        gx, gy = int(x // TILE), int(y // TILE)
        if 0 <= gy < self.h and 0 <= gx < self.w:
            return self.grid[gy][gx] == 0 and self.ink[gy][gx] == team
        return False

    def splat_radius(self, x: float, y: float, team: int, radius: float) -> None:
        gx0, gy0 = int(x // TILE), int(y // TILE)
        r_tiles = int(radius // TILE) + 1
        for gy in range(gy0 - r_tiles, gy0 + r_tiles + 1):
            for gx in range(gx0 - r_tiles, gx0 + r_tiles + 1):
                if 0 <= gy < self.h and 0 <= gx < self.w and self.grid[gy][gx] == 0:
                    cx = gx * TILE + TILE // 2
                    cy = gy * TILE + TILE // 2
                    if math.hypot(cx - x, cy - y) <= radius:
                        self.ink[gy][gx] = team


class Player:
    def __init__(self, stage: Stage) -> None:
        self.x = float(stage.spawn_x)
        self.y = float(stage.spawn_y)
        self.angle = 0.0
        self.ink = 100.0
        self.stage = stage
        self.squid = False
        self.z = 0.0
        self.vz = 0.0
        self.grounded = True
        self.coyote = 0.0
        self.special_cd = 0.0
        self.landed = False

    @property
    def airborne(self) -> bool:
        return not self.grounded or self.z > 0.05

    def view_bob(self) -> int:
        """Camera lift while jumping (Splatoon 2 kid hop)."""
        return int(self.z * 7.0)

    def update(self, stage: Stage, dt: float) -> None:
        self.landed = False
        keys = pygame.key.get_pressed()
        sin_a = math.sin(self.angle)
        cos_a = math.cos(self.angle)

        on_ink = stage.on_team_ink(self.x, self.y, 1)
        want_squid = keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL] or keys[pygame.K_c]
        self.squid = want_squid and on_ink and self.grounded and self.z <= 0.05

        speed = SQUID_SPEED if self.squid else WALK_SPEED
        if self.airborne:
            speed *= AIR_CONTROL

        dx = dy = 0.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dx += cos_a * speed
            dy += sin_a * speed
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dx -= cos_a * speed
            dy -= sin_a * speed
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx += -sin_a * speed
            dy += cos_a * speed
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += sin_a * speed
            dy -= cos_a * speed

        if not stage.is_wall(self.x + dx, self.y):
            self.x += dx
        if not stage.is_wall(self.x, self.y + dy):
            self.y += dy

        if (dx or dy) and not self.squid and self.grounded:
            stage.splat(self.x, self.y, 1)
            self.ink = max(0.0, self.ink - 0.06 * dt * 60)

        if self.grounded:
            self.coyote = COYOTE_TIME
            self.z = 0.0
            if self.vz < 0:
                self.vz = 0.0
        else:
            self.coyote = max(0.0, self.coyote - dt)
            self.vz -= GRAVITY_Z * dt
            self.z += self.vz * dt
            if self.z > MAX_JUMP_Z:
                self.z = MAX_JUMP_Z
                self.vz = min(0.0, self.vz)
            if self.z <= 0.0:
                self.z = 0.0
                self.vz = 0.0
                self.grounded = True
                self.landed = True
                stage.splat_radius(self.x, self.y, 1, LAND_SPLAT_R)

        if self.ink < 100.0:
            self.ink = min(100.0, self.ink + INK_REGEN * dt * (1.6 if on_ink else 1.0))

        if self.special_cd > 0:
            self.special_cd = max(0.0, self.special_cd - dt)

    def jump(self, stage: Stage) -> bool:
        """B button hop — kid form only, grounded or coyote window."""
        if self.squid or self.airborne:
            return False
        if self.coyote <= 0.0 and not self.grounded:
            return False
        self.vz = JUMP_VEL
        self.z = 0.01
        self.grounded = False
        self.coyote = 0.0
        self.squid = False
        stage.splat(self.x, self.y, 1)
        return True

    def can_special(self) -> bool:
        return self.special_cd <= 0 and self.ink >= 25 and not self.squid


def fire_ink(
    player: Player,
    stage: Stage,
    enemies: list["Enemy"] | None = None,
    *,
    burst: bool = False,
) -> None:
    """ZR ink shooter — LMB stream · RMB sub burst."""
    if player.squid:
        return
    dist = 55 if burst else 48
    cost = 10.0 if burst else 0.35
    if player.ink < cost:
        return
    bx = player.x + math.cos(player.angle) * dist
    by = player.y + math.sin(player.angle) * dist
    player.ink -= cost
    stage.splat(bx, by, 1)
    if burst:
        stage.splat_radius(bx, by, 1, 38)
        for _ in range(4):
            stage.splat(bx + random.uniform(-24, 24), by + random.uniform(-24, 24), 1)
    if burst and enemies is not None:
        for e in enemies[:]:
            if math.hypot(e.x - bx, e.y - by) < 62 and e.hit():
                enemies.remove(e)


def fire_special(player: Player, stage: Stage, enemies: list["Enemy"]) -> None:
    if not player.can_special():
        return
    player.ink -= 25
    player.special_cd = 3.0
    bx = player.x + math.cos(player.angle) * 70
    by = player.y + math.sin(player.angle) * 70
    stage.splat_radius(bx, by, 1, 72)
    for e in enemies[:]:
        if math.hypot(e.x - bx, e.y - by) < 75:
            e.hp = 0
            enemies.remove(e)


class Enemy:
    def __init__(self, stage: Stage) -> None:
        for _ in range(40):
            gx = random.randint(1, stage.w - 2)
            gy = random.randint(1, stage.h - 2)
            if stage.grid[gy][gx] == 0:
                self.x = gx * TILE + TILE // 2
                self.y = gy * TILE + TILE // 2
                break
        else:
            self.x, self.y = stage.spawn_x + 80, stage.spawn_y + 80
        self.hp = 3

    def update(self, player: Player, stage: Stage) -> None:
        angle = math.atan2(player.y - self.y, player.x - self.x)
        nx = self.x + math.cos(angle) * 1.1
        ny = self.y + math.sin(angle) * 1.1
        if not stage.is_wall(nx, self.y):
            self.x = nx
        if not stage.is_wall(self.x, ny):
            self.y = ny
        stage.splat(self.x, self.y, 2)

    def hit(self) -> bool:
        self.hp -= 1
        return self.hp <= 0


def cast_rays(screen: pygame.Surface, player: Player, stage: Stage) -> None:
    start_angle = player.angle - FOV / 2
    ray_w = max(1, WIDTH // NUM_RAYS)
    bob = player.view_bob()

    for ray in range(NUM_RAYS):
        angle = start_angle + ray * DELTA_ANGLE
        sin_a = math.sin(angle)
        cos_a = math.cos(angle)

        hit = False
        depth = 0.0
        side = 0
        for step in range(0, MAX_DEPTH, 4):
            depth = float(step)
            x = player.x + depth * cos_a
            y = player.y + depth * sin_a
            if stage.is_wall(x, y):
                hit = True
                gx = int(x // TILE)
                side = 1 if int(x) % TILE < TILE // 2 else 0
                break

        if not hit:
            continue

        corrected = depth * math.cos(player.angle - angle)
        if corrected < 0.001:
            corrected = 0.001
        proj_h = min(HEIGHT, int(PROJ_COEFF / corrected))

        base = stage.wall_col
        shade = max(0.45, min(1.0, 280.0 / (corrected + 1.0)))
        if side:
            shade *= 0.78
        col = tuple(int(c * shade) for c in base)
        top = HALF_HEIGHT - proj_h // 2 + bob
        pygame.draw.rect(screen, col, (ray * ray_w, top, ray_w + 1, proj_h))
        # wall cap (Splatoon-style accent stripe)
        cap = tuple(min(255, int(stage.accent[i] * shade * 0.35 + base[i] * 0.65)) for i in range(3))
        pygame.draw.rect(screen, cap, (ray * ray_w, top, ray_w + 1, max(2, proj_h // 8)))


def draw_floor(screen: pygame.Surface, player: Player, stage: Stage) -> None:
    """Pseudo-3D floor with stage tint + ink coverage."""
    bob = player.view_bob()
    horizon = HALF_HEIGHT + bob
    pygame.draw.rect(screen, SKY, (0, 0, WIDTH, horizon))
    pygame.draw.rect(screen, stage.floor_col, (0, horizon, WIDTH, HEIGHT - horizon))

    # horizon ink gradient bands
    for i in range(8):
        t = i / 7.0
        col = tuple(
            int(stage.floor_col[j] * (1 - t * 0.3) + stage.accent[j] * t * 0.08)
            for j in range(3)
        )
        y = horizon + int((HALF_HEIGHT / 8) * i)
        h = HALF_HEIGHT // 8 + 1
        pygame.draw.rect(screen, col, (0, y, WIDTH, h))


def draw_enemies(
    screen: pygame.Surface,
    player: Player,
    enemies: list[Enemy],
) -> None:
    for e in enemies:
        dx = e.x - player.x
        dy = e.y - player.y
        dist = math.hypot(dx, dy)
        if dist < 8:
            continue
        rel = math.atan2(dy, dx) - player.angle
        while rel > math.pi:
            rel -= math.tau
        while rel < -math.pi:
            rel += math.tau
        if abs(rel) > FOV / 2:
            continue
        size = max(6, int(4200 / (dist + 1)))
        sx = int(WIDTH // 2 + (rel / (FOV / 2)) * (WIDTH // 2))
        sy = int(HALF_HEIGHT + size // 4 + player.view_bob())
        pygame.draw.ellipse(screen, INK_ENEMY, (sx - size // 2, sy - size, size, size * 2))
        pygame.draw.circle(screen, (40, 20, 20), (sx - size // 5, sy - size // 2), max(2, size // 8))
        pygame.draw.circle(screen, (40, 20, 20), (sx + size // 5, sy - size // 2), max(2, size // 8))


def draw_minimap(
    screen: pygame.Surface,
    player: Player,
    enemies: list[Enemy],
    stage: Stage,
) -> None:
    scale = 6
    ox, oy = WIDTH - stage.w * scale - 12, 12
    for gy, row in enumerate(stage.grid):
        for gx, cell in enumerate(row):
            if cell == 1:
                col = stage.wall_col
            elif stage.ink[gy][gx] == 1:
                col = INK_PLAYER
            elif stage.ink[gy][gx] == 2:
                col = INK_ENEMY
            else:
                col = stage.floor_col
            pygame.draw.rect(screen, col, (ox + gx * scale, oy + gy * scale, scale, scale))
    pygame.draw.rect(screen, GOLD, (ox - 1, oy - 1, stage.w * scale + 2, stage.h * scale + 2), 1)
    px = ox + int(player.x / TILE * scale)
    py = oy + int(player.y / TILE * scale)
    pygame.draw.circle(screen, INK_PLAYER, (px, py), 3)
    for e in enemies:
        ex = ox + int(e.x / TILE * scale)
        ey = oy + int(e.y / TILE * scale)
        pygame.draw.circle(screen, INK_ENEMY, (ex, ey), 2)


def turf_percent(stage: Stage) -> float:
    total = inked = 0
    for gy, row in enumerate(stage.grid):
        for gx, cell in enumerate(row):
            if cell == 0:
                total += 1
                if stage.ink[gy][gx] == 1:
                    inked += 1
    return (inked / total * 100.0) if total else 0.0


def draw_hud(
    screen: pygame.Surface,
    font: pygame.font.Font,
    font_sm: pygame.font.Font,
    stage: Stage,
    level: int,
    player: Player,
    enemies: list[Enemy],
    fps: float,
    show_map: bool,
    paused: bool,
) -> None:
    turf = turf_percent(stage)
    mode = "SQUID" if player.squid else ("AIR" if player.airborne else "KID")
    lines = (
        f"{stage.name}  ·  STAGE {level}/{len(MAPS)}  ·  {mode}",
        f"TURF {turf:.0f}%  INK {int(player.ink)}  FOES {len(enemies)}  FPS {fps:.0f}",
    )
    for i, line in enumerate(lines):
        t = font.render(line, True, TEXT if i == 0 else GOLD)
        screen.blit(t, (10, HEIGHT - 44 + i * 18))
    hint = font_sm.render(
        "PC port: LMB ZR · RMB sub · Ctrl squid · Space jump · E special · Tab map",
        True, (140, 150, 180),
    )
    screen.blit(hint, (10, 8))
    if player.special_cd > 0:
        cd = font_sm.render(f"Special {player.special_cd:.1f}s", True, (255, 140, 80))
        screen.blit(cd, (10, 26))
    if show_map:
        big = pygame.Surface((stage.w * 14 + 20, stage.h * 14 + 20), pygame.SRCALPHA)
        big.fill((0, 0, 0, 200))
        for gy, row in enumerate(stage.grid):
            for gx, cell in enumerate(row):
                if cell == 1:
                    col = stage.wall_col
                elif stage.ink[gy][gx] == 1:
                    col = INK_PLAYER
                elif stage.ink[gy][gx] == 2:
                    col = INK_ENEMY
                else:
                    col = stage.floor_col
                pygame.draw.rect(big, col, (10 + gx * 14, 10 + gy * 14, 14, 14))
        px = 10 + int(player.x / TILE * 14)
        py = 10 + int(player.y / TILE * 14)
        pygame.draw.circle(big, GOLD, (px, py), 4)
        rx = WIDTH // 2 - big.get_width() // 2
        ry = HEIGHT // 2 - big.get_height() // 2
        screen.blit(big, (rx, ry))
    if paused:
        draw_pause_overlay(screen, font, font_sm)


def draw_pause_overlay(
    screen: pygame.Surface,
    font: pygame.font.Font,
    font_sm: pygame.font.Font,
) -> None:
    ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 190))
    screen.blit(ov, (0, 0))
    t = font.render("PAUSED — SPLATOON PC PORT", True, GOLD)
    screen.blit(t, (WIDTH // 2 - t.get_width() // 2, 40))
    y = 80
    hdr = font_sm.render("Switch          PC binding              Button", True, TEXT)
    screen.blit(hdr, (WIDTH // 2 - 200, y))
    y += 22
    for label, pc, sw in PC_BIND:
        row = font_sm.render(f"{label:14}  {pc:22}  {sw}", True, (180, 190, 210))
        screen.blit(row, (WIDTH // 2 - 200, y))
        y += 18
    foot = font_sm.render("Esc resume · Q quit to title", True, (140, 150, 180))
    screen.blit(foot, (WIDTH // 2 - foot.get_width() // 2, HEIGHT - 36))


def draw_menu_bg(screen: pygame.Surface, t: float) -> None:
    screen.fill(BG)
    for i in range(12):
        x = int((math.sin(t * 0.7 + i) * 0.5 + 0.5) * WIDTH)
        y = 80 + i * 42
        col = tuple(int(INK_PLAYER[j] * (0.15 + 0.05 * i)) for j in range(3))
        pygame.draw.ellipse(screen, col, (x - 60, y, 120, 28))


def draw_main_menu(
    screen: pygame.Surface,
    font_lg: pygame.font.Font,
    font: pygame.font.Font,
    font_sm: pygame.font.Font,
    menu_sel: int,
    t: float,
) -> None:
    draw_menu_bg(screen, t)
    title = font_lg.render(APP_NAME.upper(), True, INK_PLAYER)
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 48))
    sub = font.render(f"Splatoon PC port {VERSION} · FILES=OFF", True, TEXT)
    screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, 96))
    y0 = 150
    for i, item in enumerate(MENU_ITEMS):
        col = GOLD if i == menu_sel else TEXT
        prefix = "> " if i == menu_sel else "  "
        row = font.render(prefix + item, True, col)
        screen.blit(row, (WIDTH // 2 - 100, y0 + i * 34))
    if int(t * 2) % 2 == 0:
        hint = font_sm.render("Up/Down · Enter · Esc back", True, (140, 150, 180))
        screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, HEIGHT - 36))


def _draw_panel(screen: pygame.Surface, title: str, font: pygame.font.Font, font_sm: pygame.font.Font) -> int:
    draw_menu_bg(screen, pygame.time.get_ticks() / 1000.0)
    t = font.render(title, True, GOLD)
    screen.blit(t, (WIDTH // 2 - t.get_width() // 2, 36))
    foot = font_sm.render("Enter / Esc — back to main menu", True, (140, 150, 180))
    screen.blit(foot, (WIDTH // 2 - foot.get_width() // 2, HEIGHT - 32))
    return 80


def draw_menu_help(screen: pygame.Surface, font: pygame.font.Font, font_sm: pygame.font.Font) -> None:
    y = _draw_panel(screen, "HELP", font, font_sm)
    lines = (
        "Turf War — ink the stage and splat rivals.",
        "",
        "Win by covering 80% turf with your ink,",
        "or eliminate all enemy Octarians.",
        "",
        f"Clear all {len(MAPS)} stages in order.",
        "Walk on ink to swim as a squid (Ctrl).",
        "Space — kid jump (ground only, not while squid).",
        "Special ink (E) clears a wide area.",
        "",
        "Pause in-game with Esc · Q returns to menu.",
    )
    for line in lines:
        row = font_sm.render(line, True, TEXT if line else (0, 0, 0))
        screen.blit(row, (WIDTH // 2 - 200, y))
        y += 22


def draw_menu_controls(screen: pygame.Surface, font: pygame.font.Font, font_sm: pygame.font.Font) -> None:
    y = _draw_panel(screen, "CONTROLS", font, font_sm)
    hdr = font_sm.render(f"{'Action':14}  {'PC':22}  Switch", True, GOLD)
    screen.blit(hdr, (WIDTH // 2 - 200, y))
    y += 24
    for label, pc, sw in PC_BIND:
        row = font_sm.render(f"{label:14}  {pc:22}  {sw}", True, (180, 190, 210))
        screen.blit(row, (WIDTH // 2 - 200, y))
        y += 20


def draw_menu_sound(screen: pygame.Surface, font: pygame.font.Font, font_sm: pygame.font.Font, settings: Settings) -> None:
    y = _draw_panel(screen, "SOUND", font, font_sm)
    rows = (
        ("Sound", "ON" if settings.sound_on else "OFF"),
        ("Volume", f"{int(settings.volume * 100)}%"),
    )
    for label, val in rows:
        row = font.render(f"{label}:  {val}", True, TEXT)
        screen.blit(row, (WIDTH // 2 - 120, y))
        y += 36
    tips = (
        "Left/Right — toggle sound",
        "Up/Down — volume",
    )
    y += 16
    for tip in tips:
        screen.blit(font_sm.render(tip, True, (140, 150, 180)), (WIDTH // 2 - 100, y))
        y += 20


def draw_menu_settings(screen: pygame.Surface, font: pygame.font.Font, font_sm: pygame.font.Font, settings: Settings) -> None:
    y = _draw_panel(screen, "SETTINGS", font, font_sm)
    rows = (
        ("Mouse sensitivity", f"{settings.mouse_sens:.4f}"),
        ("Minimap in play", "ON" if settings.show_minimap else "OFF"),
        ("Engine", ENGINE),
        ("Target FPS", str(FPS)),
    )
    for label, val in rows:
        row = font.render(f"{label}:  {val}", True, TEXT)
        screen.blit(row, (WIDTH // 2 - 160, y))
        y += 34
    tips = (
        "Left/Right — mouse sens",
        "Up/Down — toggle minimap",
    )
    y += 12
    for tip in tips:
        screen.blit(font_sm.render(tip, True, (140, 150, 180)), (WIDTH // 2 - 110, y))
        y += 20


def draw_menu_about(screen: pygame.Surface, font: pygame.font.Font, font_sm: pygame.font.Font) -> None:
    y = _draw_panel(screen, "ABOUT", font, font_sm)
    lines = (
        APP_NAME,
        f"Version {VERSION}",
        "",
        "Splatoon PC port · clean-room recreation",
        "Procedural maps · raycast ink engine",
        "Python 3.14 · pygame-ce · FILES=OFF",
        "",
        "Stages inspired by Splatoon 1/2:",
        "Urchin Underpass · Saltspray Rig · more",
        "",
        "by ac holding",
    )
    for line in lines:
        if not line:
            y += 12
            continue
        f = font if line == APP_NAME or line.startswith("Version") else font_sm
        row = f.render(line, True, TEXT if f == font else (180, 190, 210))
        screen.blit(row, (WIDTH // 2 - row.get_width() // 2, y))
        y += 24


def handle_menu_input(
    event: pygame.event.Event,
    menu_sel: int,
    menu_sub: str | None,
    settings: Settings,
    sfx: Sfx,
) -> tuple[int, str | None, str | None]:
    """Returns (menu_sel, menu_sub, action) where action is 'play'|'exit'|None."""
    action: str | None = None
    sel = menu_sel
    sub = menu_sub

    if event.type != pygame.KEYDOWN:
        return sel, sub, action

    key = event.key
    if sub == "sound":
        if key in (pygame.K_LEFT, pygame.K_RIGHT):
            settings.sound_on = not settings.sound_on
            sfx.play(sfx.menu, settings)
        elif key == pygame.K_UP:
            settings.volume = min(1.0, settings.volume + 0.1)
        elif key == pygame.K_DOWN:
            settings.volume = max(0.0, settings.volume - 0.1)
        elif key in (pygame.K_RETURN, pygame.K_ESCAPE):
            sub = None
        return sel, sub, action

    if sub == "settings":
        if key in (pygame.K_LEFT, pygame.K_RIGHT):
            settings.mouse_sens = max(0.001, min(0.012, settings.mouse_sens + (0.0005 if key == pygame.K_RIGHT else -0.0005)))
        elif key == pygame.K_UP:
            settings.show_minimap = not settings.show_minimap
        elif key in (pygame.K_RETURN, pygame.K_ESCAPE):
            sub = None
        return sel, sub, action

    if sub in ("help", "controls", "about"):
        if key in (pygame.K_RETURN, pygame.K_ESCAPE):
            sub = None
        return sel, sub, action

    # main menu
    if key in (pygame.K_UP, pygame.K_w):
        sel = (sel - 1) % len(MENU_ITEMS)
        sfx.play(sfx.menu, settings)
    elif key in (pygame.K_DOWN, pygame.K_s):
        sel = (sel + 1) % len(MENU_ITEMS)
        sfx.play(sfx.menu, settings)
    elif key in (pygame.K_RETURN, pygame.K_SPACE):
        sfx.play(sfx.confirm, settings)
        item = MENU_ITEMS[sel]
        if item == "PLAY GAME":
            action = "play"
        elif item == "EXIT":
            action = "exit"
        elif item == "HELP":
            sub = "help"
        elif item == "CONTROLS":
            sub = "controls"
        elif item == "SOUND":
            sub = "sound"
        elif item == "SETTINGS":
            sub = "settings"
        elif item == "ABOUT":
            sub = "about"
    elif key == pygame.K_ESCAPE:
        action = "exit"

    return sel, sub, action


def load_stage(index: int) -> tuple[Stage, Player, list[Enemy]]:
    stage = Stage(MAPS[index % len(MAPS)])
    player = Player(stage)
    count = 2 + (index % 4)
    enemies = [Enemy(stage) for _ in range(count)]
    return stage, player, enemies


def begin_play(level_idx: int) -> tuple[str, int, Stage, Player, list[Enemy], bool, bool]:
    stage, player, enemies = load_stage(level_idx)
    pygame.mouse.set_visible(False)
    pygame.event.set_grab(True)
    return "play", level_idx, stage, player, enemies, False, False


def draw_title(screen: pygame.Surface, font_lg: pygame.font.Font, font: pygame.font.Font, font_sm: pygame.font.Font, t: float) -> None:
    """Legacy alias — main menu."""
    draw_main_menu(screen, font_lg, font, font_sm, 1, t)


def main() -> None:
    pygame.mixer.pre_init(22050, -16, 1, 256)
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption(WINDOW_TITLE)
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 26)
    font_sm = pygame.font.Font(None, 18)
    font_lg = pygame.font.Font(None, 48)
    settings = Settings()
    sfx = Sfx()

    state = "menu"
    menu_sel = 1  # PLAY GAME default highlight
    menu_sub: str | None = None
    menu_t = 0.0
    level_idx = 0
    stage, player, enemies = load_stage(0)
    win_timer = 0.0
    paused = False
    show_map = False

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        dt = min(dt, 0.05)
        sens = settings.mouse_sens

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            if state == "menu":
                if event.type == pygame.KEYDOWN:
                    menu_sel, menu_sub, action = handle_menu_input(event, menu_sel, menu_sub, settings, sfx)
                    if action == "play":
                        state, level_idx, stage, player, enemies, paused, show_map = begin_play(0)
                    elif action == "exit":
                        running = False
                continue

            if event.type == pygame.MOUSEMOTION and state == "play" and not paused:
                player.angle += event.rel[0] * sens
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if state == "play" and not paused:
                    if event.button == 1:
                        fire_ink(player, stage, enemies, burst=False)
                        sfx.play(sfx.ink, settings)
                    elif event.button == 3:
                        fire_ink(player, stage, enemies, burst=True)
                        sfx.play(sfx.special, settings)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if state == "play":
                        paused = not paused
                    else:
                        state = "menu"
                        menu_sub = None
                        paused = False
                        pygame.mouse.set_visible(True)
                        pygame.event.set_grab(False)
                elif event.key == pygame.K_q and state == "play":
                    state = "menu"
                    menu_sub = None
                    paused = False
                    pygame.mouse.set_visible(True)
                    pygame.event.set_grab(False)
                elif event.key == pygame.K_TAB and state == "play":
                    show_map = not show_map
                elif event.key == pygame.K_SPACE and state == "play" and not paused:
                    if player.jump(stage):
                        sfx.play(sfx.jump, settings)
                elif event.key == pygame.K_e and state == "play" and not paused:
                    fire_special(player, stage, enemies)
                    sfx.play(sfx.special, settings)

        if state == "menu":
            pygame.mouse.set_visible(True)
            pygame.event.set_grab(False)
            menu_t += dt
            if menu_sub == "help":
                draw_menu_help(screen, font, font_sm)
            elif menu_sub == "controls":
                draw_menu_controls(screen, font, font_sm)
            elif menu_sub == "sound":
                draw_menu_sound(screen, font, font_sm, settings)
            elif menu_sub == "settings":
                draw_menu_settings(screen, font, font_sm, settings)
            elif menu_sub == "about":
                draw_menu_about(screen, font, font_sm)
            else:
                draw_main_menu(screen, font_lg, font, font_sm, menu_sel, menu_t)
            pygame.display.flip()
            continue

        screen.fill(BG)
        draw_floor(screen, player, stage)
        cast_rays(screen, player, stage)
        draw_enemies(screen, player, enemies)

        if state == "play" and not paused:
            player.update(stage, dt)
            if player.landed:
                sfx.play(sfx.land, settings)
            for e in enemies:
                e.update(player, stage)
            mouse = pygame.mouse.get_pressed()
            if mouse[0]:
                fire_ink(player, stage)

        if not show_map and settings.show_minimap:
            draw_minimap(screen, player, enemies, stage)
        draw_hud(screen, font, font_sm, stage, level_idx + 1, player, enemies, clock.get_fps(), show_map, paused)

        turf = turf_percent(stage)
        cleared = len(enemies) == 0
        won_turf = turf >= 80.0

        if state == "play" and (cleared or won_turf):
            state = "clear"
            win_timer = 2.5

        if state == "clear":
            win_timer -= dt
            msg = "TURF WAR WON!" if won_turf else "SPLAT!"
            ov = pygame.Surface((WIDTH, 80), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 160))
            screen.blit(ov, (WIDTH // 2 - 180, HEIGHT // 2 - 40))
            t = font_lg.render(msg, True, GOLD)
            screen.blit(t, (WIDTH // 2 - t.get_width() // 2, HEIGHT // 2 - 30))
            if win_timer <= 0:
                level_idx += 1
                if level_idx >= len(MAPS):
                    state = "menu"
                    menu_sub = None
                    level_idx = 0
                    pygame.mouse.set_visible(True)
                    pygame.event.set_grab(False)
                else:
                    stage, player, enemies = load_stage(level_idx)
                    state = "play"
                    pygame.mouse.set_visible(False)
                    pygame.event.set_grab(True)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
