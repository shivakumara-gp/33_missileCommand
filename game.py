import random
import pygame  

WIDTH, HEIGHT = 800, 600
GROUND_Y = HEIGHT - 40
INTERCEPTOR_SPEED, EXPLOSION_MAX, EXPLOSION_TIME = 420, 45, 1.2
AMMO_PER_BATTERY = 10
city_warning = ""


def explosion_color(progress):
    """Return an (r, g, b) colour for an explosion (progress 0..1 of its life), or None for the default."""
    # Start with a hot orange, peak at white, then cool to deep red as it fades.
    progress = max(0.0, min(1.0, progress))
    if progress <= 0.5:
        start, end = (255, 120, 20), (255, 255, 240)
        blend = progress * 2
    else:
        start, end = (255, 255, 240), (180, 20, 0)
        blend = (progress - 0.5) * 2
    return tuple(round(a + (b - a) * blend) for a, b in zip(start, end))


def on_city_destroyed(city):
    """Show a warning when a standing city is destroyed."""
    global city_warning
    city_warning = f"CITY DESTROYED at x={city.pos.x:.0f}!"


def city_repair_threshold():
    """Return a score value at which a destroyed city is rebuilt, or None to disable city repair."""
    return 2000


class Battery:
    def __init__(self, x):
        self.pos = pygame.Vector2(x, GROUND_Y)
        self.ammo = AMMO_PER_BATTERY
        self.alive = True


class City:
    def __init__(self, x):
        self.pos = pygame.Vector2(x, GROUND_Y)
        self.alive = True


class Interceptor:
    def __init__(self, origin, target):
        self.pos = pygame.Vector2(origin)
        self.origin = pygame.Vector2(origin)
        self.target = pygame.Vector2(target)

    def update(self, dt):
        """Advance toward the target; return True once the warhead should detonate."""
        offset = self.target - self.pos
        if offset.length() < 6:
            return True
        self.pos += offset.normalize() * INTERCEPTOR_SPEED * dt
        return False


class Explosion:
    def __init__(self, pos, max_radius=EXPLOSION_MAX):
        self.pos = pygame.Vector2(pos)
        self.max_radius = max_radius
        self.age = 0.0

    @property
    def progress(self):
        return self.age / EXPLOSION_TIME

    @property
    def radius(self):
        return self.max_radius * (1 - abs(2 * self.progress - 1))

    @property
    def done(self):
        return self.age >= EXPLOSION_TIME


class Missile:
    def __init__(self, target, speed):
        self.origin = pygame.Vector2(random.randint(20, WIDTH - 20), 0)
        self.pos = pygame.Vector2(self.origin)
        self.target = target
        self.velocity = (target.pos - self.origin).normalize() * speed

    def update(self, dt):
        self.pos += self.velocity * dt
        return self.pos.y >= GROUND_Y - 4


class Game:
    def __init__(self):
        self.font = pygame.font.Font(None, 26)
        self.reset()

    def reset(self):
        global city_warning
        city_warning = ""
        self.batteries = [Battery(60), Battery(WIDTH / 2), Battery(WIDTH - 60)]
        xs = [150, 230, 310, 490, 570, 650]
        self.cities = [City(x) for x in xs]
        self.score, self.wave, self.state = 0, 1, "play"
        self.repairs_awarded = 0
        self.start_wave()

    def start_wave(self):
        self.missiles, self.interceptors, self.explosions = [], [], []
        self.to_spawn = 6 + self.wave * 2
        self.spawn_timer = 1.0
        for battery in self.batteries:
            battery.alive, battery.ammo = True, AMMO_PER_BATTERY

    def nearest_battery(self, target):
        eligible = (b for b in self.batteries if b.alive and b.ammo > 0)
        return min(eligible, key=lambda b: b.pos.distance_squared_to(target), default=None)

    def launch(self, target):
        target = pygame.Vector2(target)
        if self.state != "play" or target.y > GROUND_Y - 20:
            return
        battery = self.nearest_battery(target)
        if battery is not None:
            battery.ammo -= 1
            self.interceptors.append(Interceptor(battery.pos, target))

    def spawn_missile(self):
        targets = [c for c in self.cities if c.alive] + [b for b in self.batteries if b.alive]
        if targets:
            self.missiles.append(Missile(random.choice(targets), 45 + self.wave * 6))

    def update(self, dt):
        if self.state != "play":
            return
        threshold = city_repair_threshold()
        if threshold and self.score // threshold > self.repairs_awarded:
            self.repairs_awarded = self.score // threshold
            for city in self.cities:
                if not city.alive:
                    city.alive = True
                    break
        self.spawn_timer -= dt
        if self.to_spawn > 0 and self.spawn_timer <= 0:
            self.spawn_missile()
            self.to_spawn -= 1
            self.spawn_timer = random.uniform(0.6, 1.6)
        for interceptor in self.interceptors[:]:
            if interceptor.update(dt):
                self.interceptors.remove(interceptor)
                self.explosions.append(Explosion(interceptor.pos))
        for explosion in self.explosions:
            explosion.age += dt
            for missile in self.missiles[:]:
                if missile.pos.distance_squared_to(explosion.pos) < explosion.radius ** 2:
                    self.missiles.remove(missile)
                    self.score += 25
        self.explosions = [e for e in self.explosions if not e.done]
        for missile in self.missiles[:]:
            if missile.update(dt):
                self.missiles.remove(missile)
                self.impact(missile)
        if not self.missiles and self.to_spawn == 0 and not self.explosions:
            self.finish_wave()

    def impact(self, missile):
        target = missile.target
        if target.alive:
            target.alive = False
            if isinstance(target, City):
                on_city_destroyed(target)
        self.explosions.append(Explosion(missile.pos, 30))
        if not any(c.alive for c in self.cities):
            self.state = "lose"

    def finish_wave(self):
        self.score += 100 * sum(c.alive for c in self.cities) + 5 * sum(b.ammo for b in self.batteries)
        self.wave += 1
        self.start_wave()

    def draw(self, screen):
        screen.fill((5, 5, 25))
        pygame.draw.rect(screen, (150, 110, 50), (0, GROUND_Y, WIDTH, HEIGHT - GROUND_Y))
        for city in self.cities:
            if city.alive:
                for i, h in enumerate((18, 28, 22)):
                    pygame.draw.rect(screen, (90, 190, 230), (city.pos.x - 18 + i * 12, GROUND_Y - h, 10, h))
        for battery in self.batteries:
            if battery.alive:
                x = battery.pos.x
                pygame.draw.polygon(screen, (220, 220, 80), [(x - 22, GROUND_Y), (x + 22, GROUND_Y), (x, GROUND_Y - 24)])
                label = self.font.render(str(battery.ammo), True, (20, 20, 20))
                screen.blit(label, label.get_rect(center=(x, GROUND_Y + 14)))
        for missile in self.missiles:
            pygame.draw.line(screen, (200, 60, 60), missile.origin, missile.pos, 1)
            pygame.draw.circle(screen, (255, 255, 255), missile.pos, 3)
        for interceptor in self.interceptors:
            pygame.draw.line(screen, (80, 180, 255), interceptor.origin, interceptor.pos, 1)
            pygame.draw.circle(screen, (80, 180, 255), interceptor.target, 5, 1)
        for explosion in self.explosions:
            fade = 1 - explosion.progress * 0.5
            color = explosion_color(explosion.progress) or (int(255 * fade), int(200 * fade), 60)
            pygame.draw.circle(screen, color, explosion.pos, max(1, int(explosion.radius)))
        hud = self.font.render(f"Score {self.score}   Wave {self.wave}   Click to fire   R = reset", True, (240, 240, 240))
        screen.blit(hud, (10, 8))
        if city_warning:
            warning = self.font.render(city_warning, True, (255, 90, 70))
            screen.blit(warning, warning.get_rect(center=(WIDTH // 2, 42)))
        if self.state == "lose":
            label = self.font.render("ALL CITIES LOST - Press R", True, (255, 255, 120))
            screen.blit(label, label.get_rect(center=(WIDTH // 2, HEIGHT // 2)))


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Missile Command")
    clock = pygame.time.Clock()
    game = Game()
    running = True
    while running:
        dt = min(clock.tick(60) / 1000, 0.05)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                game.launch(event.pos)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                game.reset()
        game.update(dt)
        game.draw(screen)
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
