import pygame
import platform
import asyncio
import math
from functools import lru_cache

# Colors for terrain
TERRAIN_COLORS = {
    'water': (0, 0, 200),
    'river': (0, 50, 200),
    'grass': (50, 200, 50),
    'sand': (230, 220, 130),
    'rock': (130, 130, 130),
    'forest': (16, 100, 16)
}

TILE_SIZE = 32
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720

# Zoom limits
MIN_ZOOM = 0.1
MAX_ZOOM = 4.0

UI_HEIGHT = 50
BUTTON_PADDING = 10
BUTTON_WIDTH = 80
BUTTON_HEIGHT = 30

# Terrain generation params
SEED = 1337
ELEV_OCTAVES = 6
MOIST_OCTAVES = 4
RIVER_OCTAVES = 5

# Smaller scale = higher frequency
ELEV_FREQ = 1 / 50.0
MOIST_FREQ = 1 / 20.0
RIVER_FREQ = 1 / 100.0

SEA_LEVEL = 0.45
BEACH_WIDTH = 0.03
MOUNTAIN_LEVEL = 0.75
RIVER_THRESHOLD = 0.18

# -------------------
# Noise functions
# -------------------
def hash01(ix, iy, seed=SEED):
    n = (ix * 374761393 + iy * 668265263 + seed * 982451653) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return (n & 0xFFFFFF) / float(1 << 24)

def fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)

def lerp(a, b, t):
    return a + (b - a) * t

def value_noise(x, y, freq):
    fx = x * freq
    fy = y * freq
    ix = math.floor(fx)
    iy = math.floor(fy)
    tx = fx - ix
    ty = fy - iy
    u = fade(tx)
    v = fade(ty)
    n00 = hash01(ix, iy)
    n10 = hash01(ix + 1, iy)
    n01 = hash01(ix, iy + 1)
    n11 = hash01(ix + 1, iy + 1)
    nx0 = lerp(n00, n10, u)
    nx1 = lerp(n01, n11, u)
    return lerp(nx0, nx1, v)

def fbm(x, y, base_freq, octaves, persistence=0.5, lacunarity=2.0):
    value = 0.0
    amplitude = 1.0
    frequency = base_freq
    max_ampl = 0.0
    for _ in range(octaves):
        value += (value_noise(x, y, frequency) * 2 - 1) * amplitude
        max_ampl += amplitude
        amplitude *= persistence
        frequency *= lacunarity
    return max(0.0, min(1.0, (value / max_ampl + 1) / 2))

def ridged_fbm(x, y, base_freq, octaves):
    v = fbm(x, y, base_freq, octaves)
    r = (1.0 - v)
    return r * r

# -------------------
# Cached biome calculation
# -------------------
@lru_cache(maxsize=None)
def get_tile_biome(tile_x, tile_y):
    sx = tile_x + 0.5
    sy = tile_y + 0.5

    elev = fbm(sx, sy, ELEV_FREQ, ELEV_OCTAVES)
    continental = value_noise(sx, sy, ELEV_FREQ * 0.2) * 0.25 + 0.75
    elev *= continental
    elev = max(0.0, min(1.0, elev))

    moist = fbm(sx + 2000, sy - 1230, MOIST_FREQ, MOIST_OCTAVES, persistence=0.65)

    near_sea = 0.0
    for ox in (-1, 0, 1):
        for oy in (-1, 0, 1):
            near_elev = fbm(sx + ox * 3, sy + oy * 3, ELEV_FREQ, 2)
            if near_elev < SEA_LEVEL:
                near_sea += 1
    near_sea /= 9.0
    moist *= (0.7 + 0.8 * near_sea)
    moist = max(0.0, min(1.0, moist))

    drain = ridged_fbm(sx + 6000, sy - 4000, RIVER_FREQ, RIVER_OCTAVES)

    if elev < SEA_LEVEL:
        return 'water'
    if drain < RIVER_THRESHOLD and SEA_LEVEL + 0.02 < elev < MOUNTAIN_LEVEL + 0.05:
        return 'river'
    if elev < SEA_LEVEL + BEACH_WIDTH:
        return 'sand'
    if elev > MOUNTAIN_LEVEL:
        return 'rock'
    if moist > 0.58 and elev < MOUNTAIN_LEVEL - 0.05:
        return 'forest'
    return 'grass'

# -------------------
# Game class
# -------------------
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Endless Map Simulator")
        self.clock = pygame.time.Clock()
        self.camera_x, self.camera_y = 0.0, 0.0
        self.zoom_factor = 1.0
        self.terrain = {}
        self.current_tool = 'grass'
        self.brush_size = 1
        self.is_painting = False
        self.dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.mouse_pos = (0, 0)
        self.font = pygame.font.SysFont(None, 24)
        self.buttons = []
        self.setup_ui()

    def setup_ui(self):
        x = BUTTON_PADDING
        y = (UI_HEIGHT - BUTTON_HEIGHT) // 2
        for material in TERRAIN_COLORS.keys():
            rect = pygame.Rect(x, y, BUTTON_WIDTH, BUTTON_HEIGHT)
            self.buttons.append(("material", material, rect))
            x += BUTTON_WIDTH + BUTTON_PADDING
        rect_minus = pygame.Rect(x, y, 40, BUTTON_HEIGHT)
        self.buttons.append(("brush_minus", None, rect_minus))
        x += 40 + BUTTON_PADDING
        rect_plus = pygame.Rect(x, y, 40, BUTTON_HEIGHT)
        self.buttons.append(("brush_plus", None, rect_plus))

    def paint_tile(self, mx, my):
        my -= UI_HEIGHT
        if my < 0:
            return
        tile_size = TILE_SIZE * self.zoom_factor
        world_x = self.camera_x + mx / tile_size
        world_y = self.camera_y + my / tile_size
        tile_x = math.floor(world_x)
        tile_y = math.floor(world_y)
        for dx in range(-self.brush_size + 1, self.brush_size):
            for dy in range(-self.brush_size + 1, self.brush_size):
                self.terrain[(tile_x + dx, tile_y + dy)] = self.current_tool

    def zoom_at(self, factor_mult, mx, my):
        old_tile_size = TILE_SIZE * self.zoom_factor
        world_x = self.camera_x + mx / old_tile_size
        world_y = self.camera_y + (my - UI_HEIGHT) / old_tile_size
        self.zoom_factor *= factor_mult
        self.zoom_factor = max(MIN_ZOOM, min(MAX_ZOOM, self.zoom_factor))
        new_tile_size = TILE_SIZE * self.zoom_factor
        if new_tile_size == 0:
            return
        self.camera_x = world_x - mx / new_tile_size
        self.camera_y = world_y - (my - UI_HEIGHT) / new_tile_size

    def handle_ui_click(self, pos):
        for btn_type, value, rect in self.buttons:
            if rect.collidepoint(pos):
                if btn_type == "material":
                    self.current_tool = value
                elif btn_type == "brush_minus":
                    self.brush_size = max(1, self.brush_size - 1)
                elif btn_type == "brush_plus":
                    self.brush_size += 1
                return True
        return False

    def draw_ui(self):
        pygame.draw.rect(self.screen, (50, 50, 50), (0, 0, SCREEN_WIDTH, UI_HEIGHT))
        for btn_type, value, rect in self.buttons:
            color = (200, 200, 200)
            if btn_type == "material" and value == self.current_tool:
                color = (255, 255, 255)
            pygame.draw.rect(self.screen, color, rect)
            pygame.draw.rect(self.screen, (0, 0, 0), rect, 2)
            if btn_type == "material":
                text_surf = self.font.render(value, True, (0, 0, 0))
            elif btn_type == "brush_minus":
                text_surf = self.font.render("-", True, (0, 0, 0))
            elif btn_type == "brush_plus":
                text_surf = self.font.render("+", True, (0, 0, 0))
            self.screen.blit(text_surf, text_surf.get_rect(center=rect.center))
        brush_label = self.font.render(f"Brush: {self.brush_size}", True, (255, 255, 255))
        self.screen.blit(brush_label, (SCREEN_WIDTH - 150, (UI_HEIGHT - brush_label.get_height()) // 2))

    def draw_brush_preview(self):
        mx, my = self.mouse_pos
        my_adj = my - UI_HEIGHT
        if my_adj < 0:
            return
        tile_size = TILE_SIZE * self.zoom_factor
        world_x = self.camera_x + mx / tile_size
        world_y = self.camera_y + my_adj / tile_size
        tile_x = math.floor(world_x)
        tile_y = math.floor(world_y)
        overlay = pygame.Surface((math.ceil(tile_size) + 1, math.ceil(tile_size) + 1), pygame.SRCALPHA)
        base = TERRAIN_COLORS.get(self.current_tool, (255, 255, 255))
        overlay.fill((base[0], base[1], base[2], 100))
        for dx in range(-self.brush_size + 1, self.brush_size):
            for dy in range(-self.brush_size + 1, self.brush_size):
                screen_x = round((tile_x + dx - self.camera_x) * tile_size)
                screen_y = round((tile_y + dy - self.camera_y) * tile_size + UI_HEIGHT)
                self.screen.blit(overlay, (screen_x, screen_y))

    async def main(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        if event.pos[1] <= UI_HEIGHT:
                            self.handle_ui_click(event.pos)
                        else:
                            self.is_painting = True
                            self.paint_tile(*event.pos)
                    elif event.button == 3:
                        self.dragging = True
                        self.drag_start_x, self.drag_start_y = event.pos
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.is_painting = False
                    elif event.button == 3:
                        self.dragging = False
                elif event.type == pygame.MOUSEMOTION:
                    self.mouse_pos = event.pos
                    if self.is_painting and event.pos[1] > UI_HEIGHT:
                        self.paint_tile(*event.pos)
                    if self.dragging:
                        dx = event.pos[0] - self.drag_start_x
                        dy = event.pos[1] - self.drag_start_y
                        tile_size = TILE_SIZE * self.zoom_factor
                        if tile_size != 0:
                            self.camera_x -= dx / tile_size
                            self.camera_y -= dy / tile_size
                        self.drag_start_x, self.drag_start_y = event.pos
                elif event.type == pygame.MOUSEWHEEL:
                    mx, my = pygame.mouse.get_pos()
                    if my > UI_HEIGHT:
                        if event.y > 0:
                            self.zoom_at(1.1, mx, my)
                        elif event.y < 0:
                            self.zoom_at(1 / 1.1, mx, my)

            # Movement keys (consistent speed regardless of zoom)
            keys = pygame.key.get_pressed()
            pixels_per_second = 400  # speed in screen pixels
            move_speed = (pixels_per_second / TILE_SIZE) / self.zoom_factor / 60.0  # tiles per frame

            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                self.camera_x -= move_speed
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                self.camera_x += move_speed
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                self.camera_y -= move_speed
            if keys[pygame.K_DOWN] or keys[pygame.K_s]:
                self.camera_y += move_speed

            self.screen.fill((0, 0, 0))
            tile_size = TILE_SIZE * self.zoom_factor
            if tile_size <= 0:
                tile_size = TILE_SIZE * MIN_ZOOM
            tiles_wide = math.ceil(SCREEN_WIDTH / tile_size) + 2
            tiles_high = math.ceil((SCREEN_HEIGHT - UI_HEIGHT) / tile_size) + 2
            start_x = math.floor(self.camera_x)
            start_y = math.floor(self.camera_y)
            offset_x = (start_x - self.camera_x) * tile_size
            offset_y = (start_y - self.camera_y) * tile_size + UI_HEIGHT

            for dx in range(tiles_wide):
                for dy in range(tiles_high):
                    tile_x = start_x + dx
                    tile_y = start_y + dy
                    if (tile_x, tile_y) not in self.terrain:
                        self.terrain[(tile_x, tile_y)] = get_tile_biome(tile_x, tile_y)
                    color = TERRAIN_COLORS[self.terrain[(tile_x, tile_y)]]
                    pygame.draw.rect(
                        self.screen, color,
                        (round(offset_x + dx * tile_size),
                         round(offset_y + dy * tile_size),
                         math.ceil(tile_size) + 1,
                         math.ceil(tile_size) + 1)
                    )

            self.draw_brush_preview()
            self.draw_ui()
            pygame.display.flip()
            self.clock.tick(60)
            await asyncio.sleep(1.0 / 60)

if platform.system() == "Emscripten":
    asyncio.ensure_future(Game().main())
else:
    if __name__ == "__main__":
        asyncio.run(Game().main())
