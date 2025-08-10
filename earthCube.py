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
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Endless Map Simulator")
        self.clock = pygame.time.Clock()
        self.camera_x, self.camera_y = 0.0, 0.0
        self.zoom_factor = 1.0
        self.terrain = {}  # (x, y): terrain_type
        self.current_tool = 'grass'  # Default tool
        self.is_painting = False  # Track mouse button state
        self.dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0

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
        tile_size = TILE_SIZE * self.zoom_factor
        world_x = self.camera_x + mx / tile_size
        world_y = self.camera_y + my / tile_size
        tile_x = math.floor(world_x)
        tile_y = math.floor(world_y)
        self.terrain[(tile_x, tile_y)] = self.current_tool

    def zoom_at(self, factor_mult, mx, my):
        old_tile_size = TILE_SIZE * self.zoom_factor
        world_x = self.camera_x + mx / old_tile_size
        world_y = self.camera_y + my / old_tile_size
        self.zoom_factor *= factor_mult
        self.zoom_factor = max(0.1, self.zoom_factor)
        new_tile_size = TILE_SIZE * self.zoom_factor
        self.camera_x = world_x - mx / new_tile_size
        self.camera_y = world_y - my / new_tile_size

    async def main(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_1:
                        self.current_tool = 'water'
                    elif event.key == pygame.K_2:
                        self.current_tool = 'grass'
                    elif event.key == pygame.K_3:
                        self.current_tool = 'sand'
                    elif event.key == pygame.K_4:
                        self.current_tool = 'rock'
                    elif event.key == pygame.K_5:
                        self.current_tool = 'forest'
                    elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                        mx, my = pygame.mouse.get_pos()
                        self.zoom_at(1.1, mx, my)
                    elif event.key == pygame.K_MINUS:
                        mx, my = pygame.mouse.get_pos()
                        self.zoom_at(1 / 1.1, mx, my)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Left mouse button
                        self.is_painting = True
                        mx, my = event.pos
                        self.paint_tile(mx, my)
                    elif event.button == 3:  # Right mouse button
                        self.dragging = True
                        self.drag_start_x, self.drag_start_y = event.pos
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.is_painting = False
                    elif event.button == 3:
                        self.dragging = False
                elif event.type == pygame.MOUSEMOTION:
                    mx, my = event.pos
                    if self.is_painting:
                        self.paint_tile(mx, my)
                    if self.dragging:
                        dx = mx - self.drag_start_x
                        dy = my - self.drag_start_y
                        tile_size = TILE_SIZE * self.zoom_factor
                        self.camera_x -= dx / tile_size
                        self.camera_y -= dy / tile_size
                        self.drag_start_x = mx
                        self.drag_start_y = my
                elif event.type == pygame.MOUSEWHEEL:
                    mx, my = pygame.mouse.get_pos()
                    if event.y > 0:
                        self.zoom_at(1.1, mx, my)
                    elif event.y < 0:
                        self.zoom_at(1 / 1.1, mx, my)

            # Movement
            keys = pygame.key.get_pressed()
            move_speed = 0.1  # Adjust for desired speed
            if keys[pygame.K_LEFT]:
                self.camera_x -= move_speed
            if keys[pygame.K_RIGHT]:
                self.camera_x += move_speed
            if keys[pygame.K_UP]:
                self.camera_y -= move_speed
            if keys[pygame.K_DOWN]:
                self.camera_y += move_speed

            self.screen.fill((0, 0, 0))

            # Draw visible tiles
            tile_size = TILE_SIZE * self.zoom_factor
            tiles_wide = math.ceil(SCREEN_WIDTH / tile_size) + 2
            tiles_high = math.ceil(SCREEN_HEIGHT / tile_size) + 2
            start_x = math.floor(self.camera_x)
            start_y = math.floor(self.camera_y)
            offset_x = (start_x - self.camera_x) * tile_size
            offset_y = (start_y - self.camera_y) * tile_size

            for dx in range(tiles_wide):
                for dy in range(tiles_high):
                    tile_x = start_x + dx
                    tile_y = start_y + dy
                    self.generate_terrain(tile_x, tile_y)
                    color = TERRAIN_COLORS[self.terrain[(tile_x, tile_y)]]
                    rect_x = offset_x + dx * tile_size
                    rect_y = offset_y + dy * tile_size
                    pygame.draw.rect(self.screen, color, (rect_x, rect_y, tile_size, tile_size))

            pygame.display.flip()
            self.clock.tick(60)
            await asyncio.sleep(1.0 / 60)

if platform.system() == "Emscripten":
    asyncio.ensure_future(Game().main())
else:
    if __name__ == "__main__":
        asyncio.run(Game().main())