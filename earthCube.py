import pygame
import random

# Colors for terrain
TERRAIN_COLORS = {
    'water': (0, 0, 255),
    'grass': (0, 255, 0),
    'sand': (255, 255, 0)
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

    def generate_terrain(self, x, y):
        if (x, y) not in self.terrain:
            rand = random.random()
            if rand < 0.3:
                self.terrain[(x, y)] = 'water'
            elif rand < 0.6:
                self.terrain[(x, y)] = 'sand'
            else:
                self.terrain[(x, y)] = 'grass'

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_1:
                        self.current_tool = 'water'
                    elif event.key == pygame.K_2:
                        self.current_tool = 'grass'
                    elif event.key == pygame.K_3:
                        self.current_tool = 'sand'
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = pygame.mouse.get_pos()
                    tile_x = (mx // TILE_SIZE) + self.camera_x
                    tile_y = (my // TILE_SIZE) + self.camera_y
                    self.terrain[(tile_x, tile_y)] = self.current_tool

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
                    tile_x = self.camera_x + dx - 1
                    tile_y = self.camera_y + dy - 1
                    self.generate_terrain(tile_x, tile_y)
                    color = TERRAIN_COLORS[self.terrain[(tile_x, tile_y)]]
                    pygame.draw.rect(self.screen, color,
                                     (dx * TILE_SIZE, dy * TILE_SIZE, TILE_SIZE, TILE_SIZE))

            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()

if __name__ == "__main__":
    game = Game()
    game.run()