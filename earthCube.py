import pygame
import random
import platform
import asyncio
import math

# Colors for terrain
TERRAIN_COLORS = {
    'water': (0, 0, 255),
    'grass': (0, 255, 0),
    'sand': (255, 255, 0),
    'rock': (128, 128, 128),
    'forest': (0, 100, 0)
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
        self.mouse_pos = (0, 0)  # Track cursor position for preview

        # UI setup
        self.font = pygame.font.SysFont(None, 24)
        self.buttons = []
        self.setup_ui()

    def setup_ui(self):
        x = BUTTON_PADDING
        y = (UI_HEIGHT - BUTTON_HEIGHT) // 2
        # Material buttons
        for material in TERRAIN_COLORS.keys():
            rect = pygame.Rect(x, y, BUTTON_WIDTH, BUTTON_HEIGHT)
            self.buttons.append(("material", material, rect))
            x += BUTTON_WIDTH + BUTTON_PADDING
        # Brush controls
        rect_minus = pygame.Rect(x, y, 40, BUTTON_HEIGHT)
        self.buttons.append(("brush_minus", None, rect_minus))
        x += 40 + BUTTON_PADDING
        rect_plus = pygame.Rect(x, y, 40, BUTTON_HEIGHT)
        self.buttons.append(("brush_plus", None, rect_plus))

    def generate_terrain(self, x, y):
        x, y = int(x), int(y)
        if (x, y) not in self.terrain:
            rand = random.random()
            if rand < 0.2:
                self.terrain[(x, y)] = 'water'
            elif rand < 0.4:
                self.terrain[(x, y)] = 'sand'
            elif rand < 0.6:
                self.terrain[(x, y)] = 'rock'
            elif rand < 0.8:
                self.terrain[(x, y)] = 'forest'
            else:
                self.terrain[(x, y)] = 'grass'

    def paint_tile(self, mx, my):
        # Adjust for UI bar
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
            text_rect = text_surf.get_rect(center=rect.center)
            self.screen.blit(text_surf, text_rect)

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
        overlay.fill((255, 255, 255, 80))  # semi-transparent white

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

            # Movement keys
            keys = pygame.key.get_pressed()
            move_speed = 0.1
            if keys[pygame.K_LEFT]:
                self.camera_x -= move_speed
            if keys[pygame.K_RIGHT]:
                self.camera_x += move_speed
            if keys[pygame.K_UP]:
                self.camera_y -= move_speed
            if keys[pygame.K_DOWN]:
                self.camera_y += move_speed

            self.screen.fill((0, 0, 0))

            # Draw world
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
                    self.generate_terrain(tile_x, tile_y)
                    color = TERRAIN_COLORS[self.terrain[(tile_x, tile_y)]]
                    rect_x = round(offset_x + dx * tile_size)
                    rect_y = round(offset_y + dy * tile_size)
                    rect_w = math.ceil(tile_size) + 1
                    rect_h = math.ceil(tile_size) + 1
                    pygame.draw.rect(self.screen, color, (rect_x, rect_y, rect_w, rect_h))

            # Draw brush preview
            self.draw_brush_preview()

            # Draw UI last
            self.draw_ui()

            pygame.display.flip()
            self.clock.tick(60)
            await asyncio.sleep(1.0 / 60)

if platform.system() == "Emscripten":
    asyncio.ensure_future(Game().main())
else:
    if __name__ == "__main__":
        asyncio.run(Game().main())
