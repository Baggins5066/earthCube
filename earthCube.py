import pygame
import random
import platform
import asyncio

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
        self.camera_x, self.camera_y = 0, 0
        self.terrain = {}  # (x, y): terrain_type
        self.current_tool = 'grass'  # Default tool
        self.is_painting = False  # Track mouse button state

    def generate_terrain(self, x, y):
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
        # Adjust mouse coordinates by camera offset
        tile_x = (mx + self.camera_x * TILE_SIZE) // TILE_SIZE
        tile_y = (my + self.camera_y * TILE_SIZE) // TILE_SIZE
        self.terrain[(tile_x, tile_y)] = self.current_tool

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
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Left mouse button
                        self.is_painting = True
                        mx, my = pygame.mouse.get_pos()
                        self.paint_tile(mx, my)
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.is_painting = False
                elif event.type == pygame.MOUSEMOTION and self.is_painting:
                    mx, my = pygame.mouse.get_pos()
                    self.paint_tile(mx, my)

            # Movement
            keys = pygame.key.get_pressed()
            if keys[pygame.K_LEFT]:
                self.camera_x -= 1
            if keys[pygame.K_RIGHT]:
                self.camera_x += 1
            if keys[pygame.K_UP]:
                self.camera_y -= 1
            if keys[pygame.K_DOWN]:
                self.camera_y += 1

            self.screen.fill((0, 0, 0))

            # Draw visible tiles
            for dx in range(SCREEN_WIDTH // TILE_SIZE + 2):
                for dy in range(SCREEN_HEIGHT // TILE_SIZE + 2):
                    tile_x = self.camera_x + dx
                    tile_y = self.camera_y + dy
                    self.generate_terrain(tile_x, tile_y)
                    color = TERRAIN_COLORS[self.terrain[(tile_x, tile_y)]]
                    pygame.draw.rect(self.screen, color,
                                     ((dx - self.camera_x % 1) * TILE_SIZE, 
                                      (dy - self.camera_y % 1) * TILE_SIZE, 
                                      TILE_SIZE, TILE_SIZE))

            pygame.display.flip()
            self.clock.tick(60)
            await asyncio.sleep(1.0 / 60)

if platform.system() == "Emscripten":
    asyncio.ensure_future(Game().main())
else:
    if __name__ == "__main__":
        asyncio.run(Game().main())