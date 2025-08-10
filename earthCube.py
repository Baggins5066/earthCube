import pygame
import platform
import asyncio
import math
import random
from functools import lru_cache

# -------------------
# Constants
# -------------------
TERRAIN_COLORS = {
    'ocean': (0, 0, 200),
    'shallow water': (0, 50, 200),
    'grass': (50, 200, 50),
    'sand': (230, 220, 130),
    'rock': (130, 130, 130),
    'forest': (16, 100, 16)
}

TILE_SIZE = 32
SCREEN_WIDTH, SCREEN_HEIGHT = 1280, 720

MIN_ZOOM = 0.05
MAX_ZOOM = 1.0

UI_HEIGHT = 50
BUTTON_PADDING = 10
BUTTON_WIDTH = 80
BUTTON_HEIGHT = 30

# Slider constants
SLIDER_WIDTH = 200
SLIDER_HEIGHT = 16
SLIDER_PADDING = 20  # distance from bottom-right corner

# Terrain gen params
SEED = 1337
ELEV_OCTAVES = 6
MOIST_OCTAVES = 4
RIVER_OCTAVES = 5
ELEV_FREQ = 1 / 50.0
MOIST_FREQ = 1 / 20.0
RIVER_FREQ = 1 / 100.0
SEA_LEVEL = 0.45
BEACH_WIDTH = 0.03
MOUNTAIN_LEVEL = 0.75
SHALLOW_WATER_THRESHOLD = 0.18

# Entity settings
ENTITY_SPAWN_CHANCE = 0.02  # Chance per tile to spawn on initial load
ENTITY_MAX_PER_TILE = 3     # Max entities per tile
ENTITY_SPEED = 0.05         # Tiles per second
ENTITY_SIZE = 8             # Pixel size for rendering

# Entity types and their allowed terrains
ENTITY_TYPES = {
    'fish': {'terrains': ['ocean', 'shallow water'], 'color': (255, 255, 0), 'move_type': 'swim'},
    'deer': {'terrains': ['forest', 'grass'], 'color': (139, 69, 19), 'move_type': 'walk'},
    'bush': {'terrains': ['grass', 'forest'], 'color': (0, 128, 0), 'move_type': 'static'}
}

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
        return 'ocean'
    if drain < SHALLOW_WATER_THRESHOLD and SEA_LEVEL + 0.02 < elev < MOUNTAIN_LEVEL + 0.05:
        return 'shallow water'
    if elev < SEA_LEVEL + BEACH_WIDTH:
        return 'sand'
    if elev > MOUNTAIN_LEVEL:
        return 'rock'
    if moist > 0.58 and elev < MOUNTAIN_LEVEL - 0.05:
        return 'forest'
    return 'grass'

# -------------------
# Entity Class
# -------------------
class Entity:
    def __init__(self, entity_type, x, y):
        self.type = entity_type
        self.x = x
        self.y = y
        self.move_type = ENTITY_TYPES[entity_type]['move_type']
        self.vx = random.uniform(-ENTITY_SPEED, ENTITY_SPEED) if self.move_type != 'static' else 0
        self.vy = random.uniform(-ENTITY_SPEED, ENTITY_SPEED) if self.move_type != 'static' else 0
        self.color = ENTITY_TYPES[entity_type]['color']

    def update(self, terrain, tile_x, tile_y):
        if self.move_type == 'static':
            return True
        # Move entity (walk or swim)
        self.x += self.vx / 60.0
        self.y += self.vy / 60.0
        new_tile_x = math.floor(self.x)
        new_tile_y = math.floor(self.y)
        
        # Check if entity is still in valid terrain
        tile_key = (new_tile_x, new_tile_y)
        if tile_key in terrain:
            tile_type = terrain[tile_key]
        else:
            tile_type = get_tile_biome(new_tile_x, new_tile_y)
        if tile_type not in ENTITY_TYPES[self.type]['terrains']:
            return False  # Remove entity if terrain is invalid
        
        # Bounce at tile edges
        if new_tile_x != tile_x or new_tile_y != tile_y:
            if abs(self.x - tile_x) > 0.5:
                self.vx = -self.vx
                self.x = tile_x + math.copysign(0.49, self.x - tile_x)
            if abs(self.y - tile_y) > 0.5:
                self.vy = -self.vy
                self.y = tile_y + math.copysign(0.49, self.y - tile_y)
        return True

    def draw(self, screen, camera_x, camera_y, zoom_factor, ui_height):
        tile_size = TILE_SIZE * zoom_factor
        screen_x = round((self.x - camera_x) * tile_size)
        screen_y = round((self.y - camera_y) * tile_size + ui_height)
        if self.move_type == 'swim':
            # Fish: draw as triangle pointing in movement direction
            angle = math.atan2(self.vy, self.vx)
            points = [
                (screen_x + math.cos(angle) * ENTITY_SIZE * zoom_factor, screen_y + math.sin(angle) * ENTITY_SIZE * zoom_factor),
                (screen_x + math.cos(angle + 2.5) * ENTITY_SIZE * zoom_factor * 0.5, screen_y + math.sin(angle + 2.5) * ENTITY_SIZE * zoom_factor * 0.5),
                (screen_x + math.cos(angle - 2.5) * ENTITY_SIZE * zoom_factor * 0.5, screen_y + math.sin(angle - 2.5) * ENTITY_SIZE * zoom_factor * 0.5)
            ]
            pygame.draw.polygon(screen, self.color, points)
        elif self.move_type == 'walk':
            # Deer: draw as square
            size = ENTITY_SIZE * zoom_factor
            pygame.draw.rect(screen, self.color, (screen_x - size / 2, screen_y - size / 2, size, size))
        else:
            # Bush: draw as circle
            pygame.draw.circle(screen, self.color, (screen_x, screen_y), ENTITY_SIZE * zoom_factor)

# -------------------
# Game Class
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
        self.entities = {}  # Dict of (tile_x, tile_y) -> list of entities
        self.loaded_tiles = set()  # Track loaded tiles to prevent respawning
        self.current_tool = 'grass'
        self.brush_size = 1
        self.is_painting = False
        self.dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.mouse_pos = (0, 0)
        self.font = pygame.font.SysFont(None, 24)
        self.buttons = []
        self.slider_dragging = False
        self.slider_rect = pygame.Rect(0, 0, 0, 0)
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
                tile_key = (tile_x + dx, tile_y + dy)
                old_terrain = self.terrain.get(tile_key, get_tile_biome(tile_x + dx, tile_y + dy))
                self.terrain[tile_key] = self.current_tool
                # Remove entities if terrain becomes invalid
                if tile_key in self.entities:
                    valid_entities = []
                    for entity in self.entities[tile_key]:
                        if self.current_tool in ENTITY_TYPES[entity.type]['terrains']:
                            valid_entities.append(entity)
                    self.entities[tile_key] = valid_entities
                    if not valid_entities:
                        del self.entities[tile_key]

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

    def draw_zoom_slider(self):
        slider_x = SCREEN_WIDTH - SLIDER_WIDTH - BUTTON_PADDING
        slider_y = (UI_HEIGHT - SLIDER_HEIGHT) // 2
        pygame.draw.rect(self.screen, (100, 100, 100), (slider_x, slider_y, SLIDER_WIDTH, SLIDER_HEIGHT))
        t = (self.zoom_factor - MIN_ZOOM) / (MAX_ZOOM - MIN_ZOOM)
        handle_x = slider_x + int(t * (SLIDER_WIDTH - SLIDER_HEIGHT))
        pygame.draw.rect(self.screen, (200, 200, 200), (handle_x, slider_y, SLIDER_HEIGHT, SLIDER_HEIGHT))
        return pygame.Rect(slider_x, slider_y, SLIDER_WIDTH, SLIDER_HEIGHT)

    def handle_slider_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.slider_rect.collidepoint(event.pos):
                self.slider_dragging = True
                self.update_zoom_from_slider(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.slider_dragging = False
        elif event.type == pygame.MOUSEMOTION and self.slider_dragging:
            self.update_zoom_from_slider(event.pos[0])

    def update_zoom_from_slider(self, mouse_x):
        slider_x = SCREEN_WIDTH - SLIDER_WIDTH - SLIDER_PADDING
        t = (mouse_x - slider_x) / (SLIDER_WIDTH - SLIDER_HEIGHT)
        t = max(0, min(1, t))
        self.zoom_factor = MIN_ZOOM + t * (MAX_ZOOM - MIN_ZOOM)

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

    def spawn_entities(self, start_x, start_y, tiles_wide, tiles_high):
        for dx in range(tiles_wide):
            for dy in range(tiles_high):
                tile_x = start_x + dx
                tile_y = start_y + dy
                tile_key = (tile_x, tile_y)
                if tile_key in self.loaded_tiles:
                    continue  # Skip if tile already loaded
                self.loaded_tiles.add(tile_key)
                tile_type = self.terrain.get(tile_key, get_tile_biome(tile_x, tile_y))
                
                # Count existing entities
                entity_count = len(self.entities.get(tile_key, []))
                if entity_count >= ENTITY_MAX_PER_TILE:
                    continue
                    
                # Try to spawn a new entity
                if random.random() < ENTITY_SPAWN_CHANCE:
                    valid_entities = [e for e, data in ENTITY_TYPES.items() if tile_type in data['terrains']]
                    if valid_entities:
                        entity_type = random.choice(valid_entities)
                        new_entity = Entity(entity_type, tile_x + 0.5, tile_y + 0.5)
                        if tile_key not in self.entities:
                            self.entities[tile_key] = []
                        self.entities[tile_key].append(new_entity)

    def update_entities(self):
        for tile_key in list(self.entities.keys()):
            entities = self.entities[tile_key]
            valid_entities = []
            for entity in entities:
                if entity.update(self.terrain, *tile_key):
                    new_tile_x = math.floor(entity.x)
                    new_tile_y = math.floor(entity.y)
                    new_tile_key = (new_tile_x, new_tile_y)
                    if new_tile_key != tile_key:
                        if new_tile_key not in self.entities:
                            self.entities[new_tile_key] = []
                        self.entities[new_tile_key].append(entity)
                    else:
                        valid_entities.append(entity)
            self.entities[tile_key] = valid_entities
            if not self.entities[tile_key]:
                del self.entities[tile_key]

    async def main(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                self.handle_slider_event(event)
                if event.type == pygame.MOUSEBUTTONDOWN:
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

            # Consistent WASD/arrow movement
            keys = pygame.key.get_pressed()
            pixels_per_second = 400
            move_speed = (pixels_per_second / TILE_SIZE) / self.zoom_factor / 60.0
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

            # Draw terrain
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

            # Spawn entities only for newly loaded tiles
            self.spawn_entities(start_x, start_y, tiles_wide, tiles_high)
            self.update_entities()

            # Draw entities
            for tile_key in self.entities:
                for entity in self.entities[tile_key]:
                    entity.draw(self.screen, self.camera_x, self.camera_y, self.zoom_factor, UI_HEIGHT)

            self.draw_brush_preview()
            self.draw_ui()
            self.slider_rect = self.draw_zoom_slider()
            pygame.display.flip()
            self.clock.tick(60)
            await asyncio.sleep(1.0 / 60)

if platform.system() == "Emscripten":
    asyncio.ensure_future(Game().main())
else:
    if __name__ == "__main__":
        asyncio.run(Game().main())