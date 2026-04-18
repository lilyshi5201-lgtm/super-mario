
#!/usr/bin/env python3
"""A Mario-style platformer with 1-player and 2-player menu modes."""
from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pygame

FPS = 60
TILE_SIZE = 48
SCREEN_WIDTH = 20 * TILE_SIZE
SCREEN_HEIGHT = 14 * TILE_SIZE
MOVE_SPEED = 4.6
JUMP_SPEED = -12.0
POWER_JUMP_SPEED = -15.5
GRAVITY = 0.55
POWER_GRAVITY_ASCEND = 0.40
POWER_GRAVITY_DESCEND = 0.47
MAX_FALL_SPEED = 14
ENEMY_SPEED = 1.4
STARTING_LIVES = 3
PUNCH_DURATION = FPS // 3
HIT_INVULN_DURATION = FPS * 2
RESPAWN_INVULN_DURATION = FPS
ENEMY_MAX_HP = 3
ENEMY_DAMAGE_COOLDOWN = FPS
ENEMY_PUNCH_KNOCKBACK = TILE_SIZE
EXTRA_LIFE_COIN_STEP = 20
CAMERA_PLAYER_MARGIN = 90
INPUT_GRACE_FRAMES = 3
WINDOWED_WIDTH = SCREEN_WIDTH
WINDOWED_HEIGHT = SCREEN_HEIGHT
FULLSCREEN_BUTTON_SIZE = 40


def clamp(value: int | float, minimum: int | float, maximum: int | float) -> int | float:
    return max(minimum, min(value, maximum))


def draw_text(
        surface: pygame.Surface,
        font: pygame.font.Font,
        text: str,
        x: int,
        y: int,
        color: tuple[int, int, int] = (255, 255, 255),
        shadow_color: tuple[int, int, int] = (0, 0, 0),
) -> None:
    shadow = font.render(text, True, shadow_color)
    surface.blit(shadow, (x + 2, y + 2))
    image = font.render(text, True, color)
    surface.blit(image, (x, y))


def center_text(
        surface: pygame.Surface,
        font: pygame.font.Font,
        text: str,
        y: int,
        color: tuple[int, int, int] = (255, 255, 255),
) -> None:
    image = font.render(text, True, color)
    shadow = font.render(text, True, (0, 0, 0))
    x = (surface.get_width() - image.get_width()) // 2
    surface.blit(shadow, (x + 2, y + 2))
    surface.blit(image, (x, y))


def create_fallback_image(color: tuple[int, int, int],
                          size: tuple[int, int] = (TILE_SIZE, TILE_SIZE)) -> pygame.Surface:
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf.fill(color)
    pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), 2)
    return surf


def crop_transparent_surface(surface: pygame.Surface) -> pygame.Surface:
    try:
        alpha_rect = surface.get_bounding_rect(min_alpha=1)
    except TypeError:
        alpha_rect = surface.get_bounding_rect()
    if alpha_rect.width <= 0 or alpha_rect.height <= 0:
        return surface
    return surface.subsurface(alpha_rect).copy()


def fit_surface_to_tile(surface: pygame.Surface) -> pygame.Surface:
    surface = crop_transparent_surface(surface)
    width, height = surface.get_size()
    if width <= 0 or height <= 0:
        return create_fallback_image((80, 200, 80))
    scale = min((TILE_SIZE - 4) / width, (TILE_SIZE - 4) / height)
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    resized = pygame.transform.scale(surface, new_size)
    canvas = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
    dest = resized.get_rect(center=canvas.get_rect().center)
    canvas.blit(resized, dest)
    return canvas


def load_image_or_fallback(path: Path, size: tuple[int, int], fallback_color: tuple[int, int, int]) -> pygame.Surface:
    if not path.exists():
        return create_fallback_image(fallback_color, size)
    try:
        image = pygame.image.load(str(path)).convert_alpha()
        return pygame.transform.scale(image, size)
    except Exception:
        return create_fallback_image(fallback_color, size)


def load_character_image(path: Path, fallback_color: tuple[int, int, int]) -> pygame.Surface:
    if not path.exists():
        return create_fallback_image(fallback_color, (TILE_SIZE, TILE_SIZE))
    try:
        image = pygame.image.load(str(path)).convert_alpha()
        return fit_surface_to_tile(image)
    except Exception:
        return create_fallback_image(fallback_color, (TILE_SIZE, TILE_SIZE))


def load_menu_image(path: Path) -> pygame.Surface:
    fallback = create_fallback_image((60, 80, 180), (320, 240))
    if not path.exists():
        return fallback
    try:
        return pygame.image.load(str(path)).convert()
    except Exception:
        return fallback


def load_assets(base_dir: Path) -> dict[str, pygame.Surface]:
    coin_size = int(TILE_SIZE * 0.72)
    return {
        "background": load_image_or_fallback(base_dir / "0.png", (TILE_SIZE, TILE_SIZE), (100, 150, 255)),
        "brick": load_image_or_fallback(base_dir / "1.png", (TILE_SIZE, TILE_SIZE), (150, 75, 0)),
        "ground": load_image_or_fallback(base_dir / "2.png", (TILE_SIZE, TILE_SIZE), (50, 150, 50)),
        "enemy": load_image_or_fallback(base_dir / "3.png", (TILE_SIZE, TILE_SIZE), (200, 0, 0)),
        "coin": load_image_or_fallback(base_dir / "4.png", (coin_size, coin_size), (255, 255, 0)),
        "mario": load_character_image(base_dir / "5.png", (0, 0, 255)),
        "luigi": load_character_image(base_dir / "luigi.PNG", (0, 180, 0)),
        "flag": load_image_or_fallback(base_dir / "6.png", (TILE_SIZE, TILE_SIZE), (0, 255, 0)),
        "enemy_flat": load_image_or_fallback(base_dir / "death.png", (TILE_SIZE, TILE_SIZE), (100, 0, 0)),
        "lucky_box": load_image_or_fallback(base_dir / "power box.jpg", (TILE_SIZE, TILE_SIZE), (255, 200, 0)),
        "fireflower": load_image_or_fallback(base_dir / "fireflower.png", (TILE_SIZE, TILE_SIZE), (255, 100, 0)),
        "icef": load_image_or_fallback(base_dir / "icef.png", (TILE_SIZE, TILE_SIZE), (0, 255, 255)),
        "shroom": load_image_or_fallback(base_dir / "shroom.png", (TILE_SIZE, TILE_SIZE), (255, 50, 50)),
        "star": load_image_or_fallback(base_dir / "star.png", (TILE_SIZE, TILE_SIZE), (255, 255, 100)),
        "gshroom": load_image_or_fallback(base_dir / "gshroom.jpg", (TILE_SIZE, TILE_SIZE), (200, 180, 50)),
        "menu": load_menu_image(base_dir / "main menu.jpg"),
    }


@dataclass(frozen=True)
class ControlScheme:
    left_keys: tuple[int, ...]
    right_keys: tuple[int, ...]
    jump_keys: tuple[int, ...]
    shoot_keys: tuple[int, ...]
    punch_keys: tuple[int, ...]


@dataclass
class Tile:
    rect: pygame.Rect
    image: pygame.Surface
    kind: str


class Projectile:
    def __init__(self, x: float, y: float, direction: int, p_type: str, owner: "Player") -> None:
        self.x = x
        self.y = y
        self.vx = 8.0 * direction
        self.vy = 0.0
        self.p_type = p_type
        self.owner = owner
        self.rect = pygame.Rect(x, y, 16, 16)
        self.active = True

    def update(self, solid_rects: Iterable[pygame.Rect]) -> None:
        self.x += self.vx
        self.rect.x = round(self.x)
        for solid in solid_rects:
            if self.rect.colliderect(solid):
                self.active = False
                break

        self.vy = min(self.vy + GRAVITY, MAX_FALL_SPEED)
        self.y += self.vy
        self.rect.y = round(self.y)

        for solid in solid_rects:
            if self.rect.colliderect(solid):
                if self.vy > 0:
                    self.rect.bottom = solid.top
                    self.vy = -6.0
                elif self.vy < 0:
                    self.rect.top = solid.bottom
                    self.vy = 0
                self.y = float(self.rect.y)
                break

    def draw(self, screen: pygame.Surface, camera_x: int) -> None:
        color = (255, 100, 0) if self.p_type == "fire" else (100, 200, 255)
        pygame.draw.circle(screen, color, (self.rect.centerx - camera_x, self.rect.centery), 8)


class PowerUpEntity:
    def __init__(self, x: int, y: int, kind: str, image: pygame.Surface) -> None:
        self.kind = kind
        self.image = image
        self.rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
        self.x = float(x)
        self.y = float(y)
        self.vy = 0.0
        self.direction = 1 if random.choice([True, False]) else -1
        self.speed = 0.0 if kind == "coin" else ENEMY_SPEED * 1.2
        self.drop_target_x = float(x)
        self.drop_target_top: int | None = None
        self.drop_bounds: tuple[int, int] | None = None
        self.guided_drop = False
        self.anchored = False

    def anchor_on_tile(self, tile_rect: pygame.Rect) -> None:
        self.rect.bottom = tile_rect.top
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)
        self.vy = 0.0
        self.speed = 0.0
        self.guided_drop = False
        self.drop_target_top = None
        self.drop_bounds = None
        self.anchored = True

    def set_safe_drop_target(self, segment_rect: pygame.Rect, target_x: float) -> None:
        self.drop_target_x = float(target_x)
        self.drop_target_top = segment_rect.top
        self.drop_bounds = (segment_rect.left, segment_rect.right)
        self.guided_drop = True
        self.anchored = False
        if self.speed != 0:
            self.direction = -1 if self.drop_target_x < self.x else 1

    def _finish_guided_drop(self) -> None:
        if self.drop_target_top is None:
            self.guided_drop = False
            return
        self.rect.x = round(self.drop_target_x)
        self.rect.bottom = self.drop_target_top
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)
        self.vy = 0.0
        if self.speed != 0 and self.drop_bounds is not None:
            left, right = self.drop_bounds
            if self.rect.left <= left + 2:
                self.direction = 1
            elif self.rect.right >= right - 2:
                self.direction = -1
        self.guided_drop = False

    def update(self, solid_rects: Iterable[pygame.Rect], ground_rects: Iterable[pygame.Rect]) -> None:
        if self.anchored:
            return

        solid_rects = list(solid_rects)
        ground_rects = list(ground_rects)

        if self.guided_drop and self.drop_target_top is not None:
            horizontal_step = 2.8 if self.speed == 0 else 3.6
            dx = self.drop_target_x - self.x
            if abs(dx) > horizontal_step:
                self.x += horizontal_step if dx > 0 else -horizontal_step
            else:
                self.x = self.drop_target_x

            self.vy = min(self.vy + GRAVITY, MAX_FALL_SPEED)
            self.y += self.vy
            self.rect.x = round(self.x)
            self.rect.y = round(self.y)
            if self.rect.bottom >= self.drop_target_top:
                self._finish_guided_drop()
            return

        on_ground = False

        if self.speed != 0:
            self.x += self.speed * self.direction
            self.rect.x = round(self.x)
            for solid in solid_rects:
                if self.rect.colliderect(solid):
                    if self.direction > 0:
                        self.rect.right = solid.left
                    else:
                        self.rect.left = solid.right
                    self.x = float(self.rect.x)
                    self.direction *= -1
                    break

        self.vy = min(self.vy + GRAVITY, MAX_FALL_SPEED)
        self.y += self.vy
        self.rect.y = round(self.y)

        for solid in solid_rects:
            if self.rect.colliderect(solid):
                if self.vy > 0:
                    self.rect.bottom = solid.top
                    on_ground = True
                elif self.vy < 0:
                    self.rect.top = solid.bottom
                self.y = float(self.rect.y)
                self.vy = 0
                break

        if self.speed != 0 and on_ground:
            foot_x = self.rect.centerx + (self.rect.width // 2 + 3) * self.direction
            foot_y = self.rect.bottom + 2
            if not any(solid.collidepoint(foot_x, foot_y) for solid in ground_rects):
                self.direction *= -1

    def draw(self, screen: pygame.Surface, camera_x: int) -> None:
        draw_x = self.rect.x - camera_x + (self.rect.width - self.image.get_width()) // 2
        draw_y = self.rect.y + (self.rect.height - self.image.get_height()) // 2
        screen.blit(self.image, (draw_x, draw_y))


class Goal:
    def __init__(self, x: int, y: int, image: pygame.Surface) -> None:
        self.image = image
        self.draw_x = x
        self.draw_y = y
        self.rect = pygame.Rect(x + 10, y + 4, TILE_SIZE - 20, TILE_SIZE - 6)

    def draw(self, screen: pygame.Surface, camera_x: int, frame_count: int) -> None:
        bob = int(math.sin(frame_count * 0.08) * 2)
        screen.blit(self.image, (self.draw_x - camera_x, self.draw_y + bob))


class DefeatEffect:
    def __init__(self, x: int, y: int, image: pygame.Surface) -> None:
        self.image = image
        self.x = x
        self.y = y
        self.timer = 22

    def update(self) -> None:
        self.timer -= 1

    def draw(self, screen: pygame.Surface, camera_x: int) -> None:
        if self.timer > 0:
            screen.blit(self.image, (self.x - camera_x, self.y))


class BrickShard:
    def __init__(self, image: pygame.Surface, x: int, y: int, source_rect: pygame.Rect, vx: float, vy: float) -> None:
        self.image = image.subsurface(source_rect).copy()
        self.x = float(x + source_rect.x)
        self.y = float(y + source_rect.y)
        self.vx = vx
        self.vy = vy
        self.timer = 40

    def update(self) -> None:
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.45
        self.timer -= 1

    def draw(self, screen: pygame.Surface, camera_x: int) -> None:
        if self.timer > 0:
            screen.blit(self.image, (round(self.x) - camera_x, round(self.y)))


class Enemy:
    HITBOX_X = 4
    HITBOX_Y = 18
    HITBOX_W = TILE_SIZE - 8
    HITBOX_H = TILE_SIZE - 20

    def __init__(self, tile_x: int, tile_y: int, image: pygame.Surface) -> None:
        self.image = image
        self.flipped_image = pygame.transform.flip(image, True, False)
        self.rect = pygame.Rect(
            tile_x + self.HITBOX_X,
            tile_y + self.HITBOX_Y,
            self.HITBOX_W,
            self.HITBOX_H,
        )
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)
        self.vy = 0.0
        self.direction = -1
        self.frozen = False
        self.frozen_timer = 0
        self.hp = ENEMY_MAX_HP
        self.damage_cooldown = 0

    def freeze(self) -> None:
        self.frozen = True
        self.frozen_timer = FPS * 10

    def knockback(self, direction: int, solid_rects: Iterable[pygame.Rect]) -> None:
        if direction == 0:
            return
        self.direction = 1 if direction > 0 else -1
        self.rect.x += direction * ENEMY_PUNCH_KNOCKBACK
        for solid in solid_rects:
            if self.rect.colliderect(solid):
                if direction > 0:
                    self.rect.right = solid.left
                else:
                    self.rect.left = solid.right
        self.x = float(self.rect.x)

    def apply_punch_damage(self, attack_direction: int, solid_rects: Iterable[pygame.Rect]) -> bool:
        if self.damage_cooldown > 0:
            return False
        self.hp -= 1
        self.damage_cooldown = ENEMY_DAMAGE_COOLDOWN
        if self.hp <= 0:
            return True
        self.knockback(attack_direction, solid_rects)
        return False

    def update(self, solid_rects: Iterable[pygame.Rect]) -> None:
        if self.damage_cooldown > 0:
            self.damage_cooldown -= 1

        if self.frozen:
            self.frozen_timer -= 1
            if self.frozen_timer <= 0:
                self.frozen = False
            return

        self.x += ENEMY_SPEED * self.direction
        self.rect.x = round(self.x)
        for solid in solid_rects:
            if self.rect.colliderect(solid):
                if self.direction > 0:
                    self.rect.right = solid.left
                else:
                    self.rect.left = solid.right
                self.x = float(self.rect.x)
                self.direction *= -1
                break

        self.vy = min(self.vy + GRAVITY, MAX_FALL_SPEED)
        self.y += self.vy
        self.rect.y = round(self.y)

        on_ground = False
        for solid in solid_rects:
            if self.rect.colliderect(solid):
                if self.vy > 0:
                    self.rect.bottom = solid.top
                    on_ground = True
                elif self.vy < 0:
                    self.rect.top = solid.bottom
                self.y = float(self.rect.y)
                self.vy = 0
                break

        if on_ground:
            foot_x = self.rect.centerx + (self.rect.width // 2 + 3) * self.direction
            foot_y = self.rect.bottom + 2
            if not any(solid.collidepoint(foot_x, foot_y) for solid in solid_rects):
                self.direction *= -1

    def draw(self, screen: pygame.Surface, camera_x: int) -> None:
        draw_x = self.rect.x - self.HITBOX_X
        draw_y = self.rect.y - self.HITBOX_Y

        if self.frozen:
            ice_block = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            ice_block.fill((100, 200, 255, 180))
            screen.blit(ice_block, (draw_x - camera_x, draw_y))
            pygame.draw.rect(screen, (255, 255, 255), (draw_x - camera_x, draw_y, TILE_SIZE, TILE_SIZE), 2)
            return

        image = self.image if self.direction >= 0 else self.flipped_image
        screen.blit(image, (draw_x - camera_x, draw_y))

        if self.damage_cooldown > 0 and (self.damage_cooldown // 4) % 2 == 0:
            flash = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            flash.fill((255, 255, 255, 80))
            screen.blit(flash, (draw_x - camera_x, draw_y))


class Player:
    HITBOX_X = 5
    HITBOX_Y = 4
    HITBOX_W = TILE_SIZE - 10
    HITBOX_H = TILE_SIZE - 4

    def __init__(
            self,
            name: str,
            spawn_x: int,
            spawn_y: int,
            image: pygame.Surface,
            controls: ControlScheme,
            hud_color: tuple[int, int, int],
    ) -> None:
        self.name = name
        self.controls = controls
        self.hud_color = hud_color
        self.image_right = fit_surface_to_tile(image)
        self.image_left = pygame.transform.flip(self.image_right, True, False)
        self.facing = 1

        self.score = 0
        self.coins = 0
        self.lives = STARTING_LIVES
        self.punch_damage_hits = 0
        self.active = True

        self.power_type = "none"
        self.power_timer = 0
        self.shoot_cooldown = 0
        self.invuln_timer = 0
        self.punch_timer = 0
        self.ceiling_bump = False
        self.ceiling_hit_rect: pygame.Rect | None = None

        self.spawn_x = spawn_x
        self.spawn_y = spawn_y
        self.reset_physics(spawn_x, spawn_y)

    def set_spawn(self, spawn_x: int, spawn_y: int) -> None:
        self.spawn_x = spawn_x
        self.spawn_y = spawn_y

    def reset_physics(self, spawn_x: int, spawn_y: int) -> None:
        self.rect = pygame.Rect(
            spawn_x + self.HITBOX_X,
            spawn_y + self.HITBOX_Y,
            self.HITBOX_W,
            self.HITBOX_H,
        )
        self.x = float(self.rect.x)
        self.y = float(self.rect.y)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.punch_timer = 0
        self.ceiling_bump = False
        self.ceiling_hit_rect = None

    def save_state(self) -> dict[str, object]:
        return {
            "score": self.score,
            "coins": self.coins,
            "lives": self.lives,
            "power_type": self.power_type,
            "power_timer": self.power_timer,
            "punch_damage_hits": self.punch_damage_hits,
            "active": self.active,
        }

    def load_state(self, data: dict[str, object]) -> None:
        self.score = int(data.get("score", 0))
        self.coins = int(data.get("coins", 0))
        self.lives = int(data.get("lives", STARTING_LIVES))
        self.power_type = str(data.get("power_type", "none"))
        self.power_timer = int(data.get("power_timer", 0))
        self.punch_damage_hits = int(data.get("punch_damage_hits", 0))
        self.active = bool(data.get("active", True)) and self.lives > 0
        self.shoot_cooldown = 0

    def current_gravity(self) -> float:
        if self.power_type in ["golden", "mushroom", "star"]:
            return POWER_GRAVITY_ASCEND if self.vy <= 0 else POWER_GRAVITY_DESCEND
        return GRAVITY

    def desired_move(self, keys: pygame.key.ScancodeWrapper) -> int:
        move_dir = 0
        if any(keys[key] for key in self.controls.left_keys):
            move_dir -= 1
        if any(keys[key] for key in self.controls.right_keys):
            move_dir += 1
        return move_dir

    def jump(self) -> None:
        if not self.active:
            return
        if self.on_ground:
            self.vy = POWER_JUMP_SPEED if self.power_type in ["golden", "mushroom", "star"] else JUMP_SPEED
            self.on_ground = False

    def stomp_bounce(self) -> None:
        bounce = POWER_JUMP_SPEED if self.power_type in ["golden", "mushroom", "star"] else JUMP_SPEED
        self.vy = bounce * 0.55
        self.y += self.vy
        self.rect.y = round(self.y)

    def grant_power(self, p_type: str) -> None:
        self.power_type = p_type
        if p_type in {"fire", "ice"}:
            self.shoot_cooldown = 0
        if p_type == "star":
            self.power_timer = FPS * 35
        elif p_type == "fire":
            self.power_timer = FPS * 25
        elif p_type == "ice":
            self.power_timer = FPS * 30
        elif p_type == "mushroom":
            self.power_timer = FPS * 15
        elif p_type == "golden":
            self.power_timer = -1

    def shoot(self, projectiles: list[Projectile]) -> None:
        if not self.active or self.shoot_cooldown > 0:
            return
        if self.power_type == "fire":
            projectiles.append(Projectile(self.rect.centerx, self.rect.centery, self.facing, "fire", self))
            self.shoot_cooldown = int(FPS * 0.5)
        elif self.power_type == "ice":
            projectiles.append(Projectile(self.rect.centerx, self.rect.centery, self.facing, "ice", self))
            self.shoot_cooldown = FPS * 2

    def start_punch(self) -> None:
        if self.active:
            self.punch_timer = PUNCH_DURATION

    def punch_rect(self) -> pygame.Rect | None:
        if not self.active or self.punch_timer <= 0:
            return None

        width = TILE_SIZE
        height = TILE_SIZE

        if not self.on_ground:
            x = self.rect.x + (self.rect.width - width) // 2
            y = self.rect.top - height
        elif self.facing == -1:
            x = self.rect.left - width
            y = self.rect.y + (self.rect.height - height) // 2
        else:
            x = self.rect.right
            y = self.rect.y + (self.rect.height - height) // 2

        return pygame.Rect(x, y, width, height)

    def take_enemy_hit(self, enemy_rect: pygame.Rect) -> str:
        if self.invuln_timer > 0 or self.power_type == "star" or not self.active:
            return "ignore"
        if self.power_type != "none":
            self.power_type = "none"
            self.power_timer = 0
            self.invuln_timer = HIT_INVULN_DURATION
            if self.rect.centerx <= enemy_rect.centerx:
                self.rect.right = enemy_rect.left - 2
            else:
                self.rect.left = enemy_rect.right + 2
            self.x = float(self.rect.x)
            self.vy = min(self.vy, -6.0)
            self.on_ground = False
            return "power_lost"
        return "lose_life"

    def can_punch_damage_enemy(self) -> bool:
        return self.coins > 0

    def register_punch_damage(self) -> None:
        self.punch_damage_hits += 1
        if self.punch_damage_hits >= 7:
            self.coins = max(0, self.coins - 1)
            self.punch_damage_hits -= 7

    def add_coins(self, amount: int, score_per_coin: int = 50) -> None:
        if amount <= 0:
            return
        previous_coins = self.coins
        self.coins += amount
        self.score += amount * score_per_coin
        gained_lives = (self.coins // EXTRA_LIFE_COIN_STEP) - (previous_coins // EXTRA_LIFE_COIN_STEP)
        if gained_lives > 0:
            self.lives += gained_lives

    def respawn(self) -> None:
        self.reset_physics(self.spawn_x, self.spawn_y)
        self.invuln_timer = RESPAWN_INVULN_DURATION
        self.active = self.lives > 0

    def teleport_to_spawn(self, preserve_power: bool = True, give_invuln: bool = True) -> None:
        saved_power = self.power_type
        saved_timer = self.power_timer
        was_active = self.active
        self.reset_physics(self.spawn_x, self.spawn_y)
        if preserve_power:
            self.power_type = saved_power
            self.power_timer = saved_timer
        else:
            self.power_type = "none"
            self.power_timer = 0
        if give_invuln and self.lives > 0:
            self.invuln_timer = max(self.invuln_timer, RESPAWN_INVULN_DURATION)
        self.active = was_active and self.lives > 0

    def update(self, solid_rects: Iterable[pygame.Rect], move_dir: int, world_width: int) -> None:
        if not self.active:
            return

        self.ceiling_bump = False
        self.ceiling_hit_rect = None

        self.vx = move_dir * MOVE_SPEED
        if move_dir < 0:
            self.facing = -1
        elif move_dir > 0:
            self.facing = 1

        self.x += self.vx
        self.rect.x = round(self.x)
        for solid in solid_rects:
            if self.rect.colliderect(solid):
                if self.vx > 0:
                    self.rect.right = solid.left
                elif self.vx < 0:
                    self.rect.left = solid.right
                self.x = float(self.rect.x)

        self.vy = min(self.vy + self.current_gravity(), MAX_FALL_SPEED)
        self.y += self.vy
        self.rect.y = round(self.y)
        self.on_ground = False
        for solid in solid_rects:
            if self.rect.colliderect(solid):
                if self.vy > 0:
                    self.rect.bottom = solid.top
                    self.on_ground = True
                elif self.vy < 0:
                    overlap_left = max(self.rect.left, solid.left)
                    overlap_right = min(self.rect.right, solid.right)
                    hit_width = max(8, overlap_right - overlap_left)
                    self.rect.top = solid.bottom
                    self.ceiling_bump = True
                    self.ceiling_hit_rect = pygame.Rect(overlap_left, solid.bottom - 10, hit_width, 12)
                self.y = float(self.rect.y)
                self.vy = 0
                break

        if self.rect.left < 0:
            self.rect.left = 0
            self.x = float(self.rect.x)
        if self.rect.right > world_width:
            self.rect.right = world_width
            self.x = float(self.rect.x)

        if self.invuln_timer > 0:
            self.invuln_timer -= 1
        if self.punch_timer > 0:
            self.punch_timer -= 1
        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= 1

        if self.power_timer > 0:
            self.power_timer -= 1
            if self.power_timer == 0:
                self.power_type = "none"

    def draw(self, screen: pygame.Surface, camera_x: int) -> None:
        if not self.active:
            return

        draw_x = self.rect.x - self.HITBOX_X
        draw_y = self.rect.y - self.HITBOX_Y

        if self.power_type != "none":
            glow = pygame.Surface((TILE_SIZE + 10, TILE_SIZE + 10), pygame.SRCALPHA)
            color = (255, 220, 90, 90)
            if self.power_type == "fire":
                color = (255, 100, 0, 90)
            elif self.power_type == "ice":
                color = (0, 200, 255, 90)
            elif self.power_type == "star":
                color = (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255), 150)
            pygame.draw.ellipse(glow, color, glow.get_rect())
            screen.blit(glow, (draw_x - camera_x - 5, draw_y - 5))

        if self.invuln_timer > 0 and (self.invuln_timer // 4) % 2 == 0:
            return

        image = self.image_left if self.facing < 0 else self.image_right
        screen.blit(image, (draw_x - camera_x, draw_y))

        punch_rect = self.punch_rect()
        if punch_rect is not None:
            flash = pygame.Rect(punch_rect.x - camera_x, punch_rect.y, punch_rect.width, punch_rect.height)
            pygame.draw.rect(screen, (255, 243, 150), flash, border_radius=4)
            pygame.draw.rect(screen, (205, 130, 20), flash, 2, border_radius=4)

    def power_display(self) -> str:
        power_str = self.power_type.upper() if self.power_type != "none" else "OFF"
        if self.power_timer > 0:
            power_str += f" ({self.power_timer // FPS}s)"
        return power_str


def choose_block_char() -> str:
    roll = random.random()
    if roll < 0.65:
        return "="
    if roll < 0.95:
        return "#"
    return "?"


def generate_level_data(level_index: int) -> list[str]:
    width = 30 + (level_index * 10)
    lines = ["." * width for _ in range(14)]

    lines[-2] = "#" * width
    lines[-1] = "#" * width

    row = list(lines[-3])
    row[1] = "P"
    row[width - 3] = "F"
    lines[-3] = "".join(row)

    i = 5
    while i < width - 5:
        if random.random() < 0.35:
            gap_width = random.randint(2, 4)
            s1, s2 = list(lines[-2]), list(lines[-1])
            s1[i:i + gap_width] = "." * gap_width
            s2[i:i + gap_width] = "." * gap_width
            lines[-2], lines[-1] = "".join(s1), "".join(s2)
            i += gap_width + random.randint(2, 4)
            continue
        else:
            y = random.randint(5, 10)
            row = list(lines[y])
            length = random.randint(3, 6)
            for j in range(length):
                if i + j < width - 4:
                    row[i + j] = choose_block_char()
            lines[y] = "".join(row)

            if random.random() < 0.5:
                erow = list(lines[-3])
                if erow[i] == ".":
                    erow[i] = "g"
                lines[-3] = "".join(erow)

            if random.random() < 0.3:
                erow = list(lines[y - 1])
                for j in range(length):
                    if i + j < width - 4 and erow[i + j] == ".":
                        erow[i + j] = "o"
                lines[y - 1] = "".join(erow)

        i += random.randint(3, 6)

    return lines


class Level:
    def __init__(self, index: int, assets: dict[str, pygame.Surface]) -> None:
        self.assets = assets
        self.index = index
        self.title = f"Level {index}"

        raw_lines = generate_level_data(index)
        self.height = len(raw_lines)
        self.width = max(len(line) for line in raw_lines)
        lines = [line.ljust(self.width, ".") for line in raw_lines]

        self.tiles: list[Tile] = []
        self.enemies: list[Enemy] = []
        self.power_entities: list[PowerUpEntity] = []
        self.projectiles: list[Projectile] = []
        self.goal: Goal | None = None
        self.spawn = (TILE_SIZE, TILE_SIZE)

        for row_index, line in enumerate(lines):
            for col, char in enumerate(line):
                x = col * TILE_SIZE
                y = row_index * TILE_SIZE
                if char == "#":
                    self.tiles.append(Tile(pygame.Rect(x, y, TILE_SIZE, TILE_SIZE), assets["ground"], "ground"))
                elif char == "=":
                    self.tiles.append(Tile(pygame.Rect(x, y, TILE_SIZE, TILE_SIZE), assets["brick"], "brick"))
                elif char == "?":
                    self.tiles.append(Tile(pygame.Rect(x, y, TILE_SIZE, TILE_SIZE), assets["lucky_box"], "lucky_box"))
                elif char == "o":
                    self.power_entities.append(PowerUpEntity(x, y, "coin", assets["coin"]))
                elif char == "g":
                    self.enemies.append(Enemy(x, y, assets["enemy"]))
                elif char == "P":
                    self.spawn = (x, y)
                elif char == "F":
                    self.goal = Goal(x, y, assets["flag"])

        self.pixel_width = self.width * TILE_SIZE
        self.pixel_height = self.height * TILE_SIZE

        for power in self.power_entities:
            self.configure_entity_behavior(power)

    def solid_rects(self) -> list[pygame.Rect]:
        return [tile.rect for tile in self.tiles]

    def ground_rects(self) -> list[pygame.Rect]:
        return [tile.rect for tile in self.tiles if tile.kind == "ground"]

    def ground_surface_segments(self) -> list[pygame.Rect]:
        ground_positions = {(tile.rect.x, tile.rect.y) for tile in self.tiles if tile.kind == "ground"}
        surface_tiles = [
            tile.rect
            for tile in self.tiles
            if tile.kind == "ground" and (tile.rect.x, tile.rect.y - TILE_SIZE) not in ground_positions
        ]
        surface_tiles.sort(key=lambda rect: (rect.y, rect.x))
        segments: list[pygame.Rect] = []
        for rect in surface_tiles:
            if segments and rect.y == segments[-1].y and rect.x == segments[-1].right:
                segments[-1].width += TILE_SIZE
            else:
                segments.append(pygame.Rect(rect.x, rect.y, TILE_SIZE, TILE_SIZE))
        return segments

    def find_support_tile(self, rect: pygame.Rect, allowed_kinds: set[str] | None = None) -> Tile | None:
        probe_y = rect.bottom + 2
        probe_points = (rect.left + 6, rect.centerx, rect.right - 6)
        for tile in self.tiles:
            if allowed_kinds is not None and tile.kind not in allowed_kinds:
                continue
            if abs(tile.rect.top - rect.bottom) > 4:
                continue
            if any(tile.rect.collidepoint(px, probe_y) for px in probe_points):
                return tile
        return None

    def find_drop_segment(self, spawn_center_x: int, spawn_y: int, entity_width: int) -> tuple[pygame.Rect, float] | None:
        segments = self.ground_surface_segments()
        if not segments:
            return None

        preferred_segments = [segment for segment in segments if segment.top >= spawn_y]
        candidates = preferred_segments or segments

        def target_x_for(segment: pygame.Rect) -> float:
            return float(clamp(
                spawn_center_x - (entity_width // 2),
                segment.left,
                segment.right - entity_width,
            ))

        def horizontal_distance(segment: pygame.Rect) -> float:
            return abs((target_x_for(segment) + entity_width / 2) - spawn_center_x)

        nearby_candidates = [segment for segment in candidates if horizontal_distance(segment) <= TILE_SIZE * 3.5]
        if nearby_candidates:
            best_segment = min(nearby_candidates, key=lambda segment: (-segment.top, horizontal_distance(segment)))
        else:
            best_segment = min(
                candidates,
                key=lambda segment: (
                    horizontal_distance(segment) + abs(segment.top - spawn_y) * 0.65,
                    max(0, segment.top - spawn_y),
                    horizontal_distance(segment),
                ),
            )
        return best_segment, target_x_for(best_segment)

    def configure_entity_drop(self, entity: PowerUpEntity) -> None:
        target = self.find_drop_segment(entity.rect.centerx, entity.rect.bottom, entity.rect.width)
        if target is None:
            return
        segment, target_x = target
        entity.set_safe_drop_target(segment, target_x)

    def configure_entity_behavior(self, entity: PowerUpEntity) -> None:
        if entity.kind == "coin":
            support_tile = self.find_support_tile(entity.rect, {"brick"})
            if support_tile is not None:
                entity.anchor_on_tile(support_tile.rect)
                return
        self.configure_entity_drop(entity)

    def refresh_coin_support(self) -> None:
        for entity in self.power_entities:
            if entity.kind != "coin":
                continue
            support_tile = self.find_support_tile(entity.rect, {"brick"})
            if support_tile is not None:
                entity.anchor_on_tile(support_tile.rect)
            elif entity.anchored:
                entity.anchored = False
                entity.vy = 0.0
                self.configure_entity_drop(entity)

    def visible(self, rect: pygame.Rect, camera_x: int) -> bool:
        return rect.right >= camera_x - TILE_SIZE and rect.left <= camera_x + SCREEN_WIDTH + TILE_SIZE

    def find_spawn_positions(self, player_count: int) -> list[tuple[int, int]]:
        spawn_positions: list[tuple[int, int]] = []
        solid_rects = self.solid_rects()
        for index in range(player_count):
            x = self.spawn[0] + (index * TILE_SIZE)
            y = self.spawn[1]
            candidate = pygame.Rect(x + Player.HITBOX_X, y + Player.HITBOX_Y, Player.HITBOX_W, Player.HITBOX_H)
            attempts = 0
            while any(candidate.colliderect(solid) for solid in solid_rects) and attempts < 8:
                x += TILE_SIZE
                candidate.x = x + Player.HITBOX_X
                attempts += 1
            spawn_positions.append((x, y))
        return spawn_positions

    def spawn_brick_break(self, tile: Tile, effects: list[object]) -> None:
        half = TILE_SIZE // 2
        shards = [
            (pygame.Rect(0, 0, half, half), -2.8, -6.2),
            (pygame.Rect(half, 0, half, half), 2.8, -6.0),
            (pygame.Rect(0, half, half, half), -1.9, -4.7),
            (pygame.Rect(half, half, half, half), 1.9, -4.5),
        ]
        for source_rect, vx, vy in shards:
            effects.append(BrickShard(tile.image, tile.rect.x, tile.rect.y, source_rect, vx, vy))

    def trigger_lucky_box(self, tile: Tile) -> None:
        tile.kind = "used_power"
        tile.image = self.assets["ground"]

        choices = ["star", "fire", "ice", "golden", "coin", "mushroom"]
        weights = [4.5, 10, 15, 15.5, 25, 30]
        chosen = random.choices(choices, weights=weights)[0]

        asset_map = {
            "star": "star",
            "fire": "fireflower",
            "ice": "icef",
            "golden": "gshroom",
            "coin": "coin",
            "mushroom": "shroom",
        }

        spawn_y = tile.rect.top - TILE_SIZE - 8
        entity = PowerUpEntity(tile.rect.x, spawn_y, chosen, self.assets[asset_map[chosen]])
        entity.vy = -3.2 if chosen == "coin" else -2.0
        self.configure_entity_behavior(entity)
        self.power_entities.append(entity)

    def hit_tiles_from_collision(self, hit_rect: pygame.Rect | None) -> bool:
        if hit_rect is None:
            return False
        did_hit = False
        for tile in self.tiles:
            if not tile.rect.colliderect(hit_rect):
                continue
            if tile.kind == "lucky_box":
                self.trigger_lucky_box(tile)
            did_hit = True
        return did_hit

    def hit_tiles_from_punch(self, hit_rect: pygame.Rect | None, effects: list[object]) -> bool:
        if hit_rect is None:
            return False

        did_hit = False
        tile_changed = False
        for tile in list(self.tiles):
            if not tile.rect.colliderect(hit_rect):
                continue
            if tile.kind == "brick":
                self.spawn_brick_break(tile, effects)
                self.tiles.remove(tile)
                did_hit = True
                tile_changed = True
            elif tile.kind == "lucky_box":
                self.trigger_lucky_box(tile)
                did_hit = True
                tile_changed = True
            elif tile.kind in {"ground", "used_power"}:
                did_hit = True

        if tile_changed:
            self.refresh_coin_support()
        return did_hit

    def draw(self, screen: pygame.Surface, camera_x: int, frame_count: int, effects: list[object]) -> None:
        for tile in self.tiles:
            if self.visible(tile.rect, camera_x):
                screen.blit(tile.image, (tile.rect.x - camera_x, tile.rect.y))
        if self.goal and self.visible(self.goal.rect, camera_x):
            self.goal.draw(screen, camera_x, frame_count)
        for power in self.power_entities:
            power.draw(screen, camera_x)
        for effect in effects:
            effect.draw(screen, camera_x)
        for enemy in self.enemies:
            if self.visible(enemy.rect, camera_x):
                enemy.draw(screen, camera_x)
        for proj in self.projectiles:
            proj.draw(screen, camera_x)


class MarioGame:
    MENU_ONE_PLAYER_RECT = pygame.Rect(48, 80, 108, 16)
    MENU_TWO_PLAYER_RECT = pygame.Rect(48, 95, 108, 16)

    def __init__(self, base_dir: Path, start_level: int = 1) -> None:
        pygame.init()
        pygame.display.set_caption("Super Mario Python Game")
        self.windowed_size = (WINDOWED_WIDTH, WINDOWED_HEIGHT)
        self.is_fullscreen = False
        self.window = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        self.screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT)).convert()
        self.clock = pygame.time.Clock()

        self.hud_font = pygame.font.Font(None, 28)
        self.small_font = pygame.font.Font(None, 24)
        self.info_font = pygame.font.Font(None, 40)
        self.title_font = pygame.font.Font(None, 72)

        self.base_dir = base_dir
        self.assets = load_assets(base_dir)
        self.total_levels = 20

        self.frame_count = 0
        self.running = True
        self.start_level = int(clamp(start_level, 1, self.total_levels))
        self.state = "menu"
        self.mode = 1
        self.players: list[Player] = []
        self.player_by_name: dict[str, Player] = {}
        self.level_number = self.start_level
        self.level: Level | None = None
        self.effects: list[object] = []
        self.camera_x = 0
        self.help_timer = FPS * 14
        self.level_banner_timer = 0
        self.input_grace: dict[str, dict[str, int]] = {}
        self.prev_action_state: dict[str, dict[str, bool]] = {}
        self.menu_selection = 1
        self.held_keys: set[int] = set()
        self.key_press_order: dict[int, int] = {}
        self.key_press_counter = 0
        self.fullscreen_button_rect = pygame.Rect(0, 0, FULLSCREEN_BUTTON_SIZE, FULLSCREEN_BUTTON_SIZE)
        self.prev_mouse_pos: tuple[int, int] | None = None
        self.mouse_button_held = {"left": False, "right": False}
        self.luigi_mouse_grace = {"left": 0, "right": 0}
        self.luigi_jump_buffer = 0

    def mario_controls(self) -> ControlScheme:
        if self.mode == 2:
            return ControlScheme(
                left_keys=(pygame.K_LEFT,),
                right_keys=(pygame.K_RIGHT,),
                jump_keys=(pygame.K_UP, pygame.K_SPACE),
                shoot_keys=(pygame.K_LCTRL, pygame.K_RCTRL, pygame.K_SLASH),
                punch_keys=(pygame.K_RSHIFT, pygame.K_RETURN),
            )
        return ControlScheme(
            left_keys=(pygame.K_LEFT, pygame.K_a),
            right_keys=(pygame.K_RIGHT, pygame.K_d),
            jump_keys=(pygame.K_UP, pygame.K_w, pygame.K_SPACE),
            shoot_keys=(pygame.K_f,),
            punch_keys=(pygame.K_LSHIFT,),
        )

    def luigi_controls(self) -> ControlScheme:
        return ControlScheme(
            left_keys=(),
            right_keys=(),
            jump_keys=(pygame.K_SPACE,),
            shoot_keys=(pygame.K_1, pygame.K_KP1),
            punch_keys=(pygame.K_LSHIFT,),
        )

    def current_players(self) -> list[Player]:
        return self.players

    def active_players(self) -> list[Player]:
        return [player for player in self.players if player.active]

    def living_players(self) -> list[Player]:
        return [player for player in self.players if player.lives > 0]

    def refresh_input_tracking(self) -> None:
        self.input_grace = {}
        self.prev_action_state = {}
        for player in self.players:
            key = player.name.lower()
            self.input_grace[key] = {"left": 0, "right": 0, "jump": 0, "shoot": 0, "punch": 0}
            self.prev_action_state[key] = {"jump": False, "shoot": False, "punch": False}

    def clear_held_inputs(self) -> None:
        self.held_keys.clear()
        self.key_press_order.clear()
        self.key_press_counter = 0
        self.fullscreen_button_rect = pygame.Rect(0, 0, FULLSCREEN_BUTTON_SIZE, FULLSCREEN_BUTTON_SIZE)
        self.prev_mouse_pos: tuple[int, int] | None = None
        self.mouse_button_held = {"left": False, "right": False}
        self.luigi_mouse_grace = {"left": 0, "right": 0}
        self.luigi_jump_buffer = 0
        for prev in self.prev_action_state.values():
            prev["jump"] = False
            prev["shoot"] = False
            prev["punch"] = False

    def register_keydown(self, key: int) -> None:
        if key not in self.held_keys:
            self.key_press_counter += 1
            self.key_press_order[key] = self.key_press_counter
        self.held_keys.add(key)

    def register_keyup(self, key: int) -> None:
        self.held_keys.discard(key)
        self.key_press_order.pop(key, None)

    def key_group_pressed(self, bindings: tuple[int, ...]) -> bool:
        return any(key in self.held_keys for key in bindings)

    def latest_binding_order(self, bindings: tuple[int, ...]) -> int:
        latest = -1
        for key in bindings:
            if key in self.held_keys:
                latest = max(latest, self.key_press_order.get(key, -1))
        return latest

    def set_window_mode(self, fullscreen: bool) -> None:
        if fullscreen:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        self.is_fullscreen = fullscreen

    def toggle_fullscreen(self) -> None:
        if self.is_fullscreen:
            self.set_window_mode(False)
        else:
            current = pygame.display.get_surface()
            if current is not None:
                self.windowed_size = current.get_size()
            self.set_window_mode(True)

    def fullscreen_ui_active(self) -> bool:
        surface = pygame.display.get_surface()
        if surface is None:
            return self.is_fullscreen
        win_w, win_h = surface.get_size()
        desktop_sizes = pygame.display.get_desktop_sizes()
        if not desktop_sizes:
            return self.is_fullscreen
        desk_w, desk_h = desktop_sizes[0]
        return self.is_fullscreen or (win_w >= desk_w - 80 and win_h >= desk_h - 120)

    def get_game_view_rect(self) -> pygame.Rect:
        surface = pygame.display.get_surface()
        if surface is None:
            return pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
        win_w, win_h = surface.get_size()
        scale = min(win_w / SCREEN_WIDTH, win_h / SCREEN_HEIGHT)
        draw_w = max(1, int(SCREEN_WIDTH * scale))
        draw_h = max(1, int(SCREEN_HEIGHT * scale))
        rect = pygame.Rect(0, 0, draw_w, draw_h)
        rect.center = (win_w // 2, win_h // 2)
        return rect

    def screen_to_game_pos(self, mouse_pos: tuple[int, int]) -> tuple[int, int] | None:
        game_rect = self.get_game_view_rect()
        if not game_rect.collidepoint(mouse_pos):
            return None
        rel_x = (mouse_pos[0] - game_rect.x) / game_rect.width
        rel_y = (mouse_pos[1] - game_rect.y) / game_rect.height
        return int(rel_x * SCREEN_WIDTH), int(rel_y * SCREEN_HEIGHT)

    def update_mouse_tracking(self) -> None:
        current_pos = pygame.mouse.get_pos()
        if self.prev_mouse_pos is None:
            self.prev_mouse_pos = current_pos
            return

        self.mouse_button_held["left"], _, self.mouse_button_held["right"] = pygame.mouse.get_pressed(3)

        if self.luigi_mouse_grace["left"] > 0:
            self.luigi_mouse_grace["left"] -= 1
        if self.luigi_mouse_grace["right"] > 0:
            self.luigi_mouse_grace["right"] -= 1
        if self.luigi_jump_buffer > 0:
            self.luigi_jump_buffer -= 1

        dx = current_pos[0] - self.prev_mouse_pos[0]
        dy = current_pos[1] - self.prev_mouse_pos[1]
        self.prev_mouse_pos = current_pos

        if self.mode == 2 and self.state == "playing" and not self.mouse_button_held["left"]:
            if dx >= 2:
                self.luigi_mouse_grace["right"] = INPUT_GRACE_FRAMES
                self.luigi_mouse_grace["left"] = 0
            elif dx <= -2:
                self.luigi_mouse_grace["left"] = INPUT_GRACE_FRAMES
                self.luigi_mouse_grace["right"] = 0

    def update_fullscreen_button_rect(self) -> None:
        surface = pygame.display.get_surface()
        if surface is None:
            return
        win_w, _ = surface.get_size()
        self.fullscreen_button_rect = pygame.Rect(win_w - FULLSCREEN_BUTTON_SIZE - 10, 10, FULLSCREEN_BUTTON_SIZE, FULLSCREEN_BUTTON_SIZE)

    def player_move_dir(self, player: Player) -> int:
        left_raw = self.key_group_pressed(player.controls.left_keys)
        right_raw = self.key_group_pressed(player.controls.right_keys)

        if self.mode == 2 and player.name.lower() == "luigi":
            left_raw = left_raw or self.luigi_mouse_grace["left"] > 0
            right_raw = right_raw or self.luigi_mouse_grace["right"] > 0
            if left_raw and not right_raw:
                return -1
            if right_raw and not left_raw:
                return 1
            if left_raw and right_raw:
                if self.luigi_mouse_grace["left"] > self.luigi_mouse_grace["right"]:
                    return -1
                if self.luigi_mouse_grace["right"] > self.luigi_mouse_grace["left"]:
                    return 1
                return 0
            return 0

        if left_raw and right_raw:
            left_order = self.latest_binding_order(player.controls.left_keys)
            right_order = self.latest_binding_order(player.controls.right_keys)
            if left_order > right_order:
                return -1
            if right_order > left_order:
                return 1
            return 0
        if left_raw:
            return -1
        if right_raw:
            return 1
        return 0

    def build_menu_layout(self) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
        menu_image = self.assets["menu"]
        scale = min(SCREEN_WIDTH / menu_image.get_width(), SCREEN_HEIGHT / menu_image.get_height()) * 0.92
        scaled_size = (
            max(1, int(menu_image.get_width() * scale)),
            max(1, int(menu_image.get_height() * scale)),
        )
        menu_rect = pygame.Rect(0, 0, *scaled_size)
        menu_rect.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 10)

        button_width = max(220, int(menu_rect.width * 0.54))
        button_height = max(38, int(menu_rect.height * 0.085))
        button_x = menu_rect.centerx - button_width // 2
        one_y = menu_rect.y + int(menu_rect.height * 0.60)
        gap = max(16, int(menu_rect.height * 0.03))
        two_y = one_y + button_height + gap

        one_rect = pygame.Rect(button_x, one_y, button_width, button_height)
        two_rect = pygame.Rect(button_x, two_y, button_width, button_height)
        return menu_rect, one_rect, two_rect

    def start_game(self, mode: int) -> None:
        self.mode = 2 if mode == 2 else 1
        self.state = "playing"
        self.level_number = self.start_level
        self.camera_x = 0
        self.effects = []
        self.help_timer = FPS * 14
        self.level_banner_timer = FPS * 2
        self.input_grace = {}
        self.prev_action_state = {}
        self.clear_held_inputs()
        self.load_level(self.level_number)

    def get_player_states(self) -> dict[str, dict[str, object]]:
        return {player.name.lower(): player.save_state() for player in self.players}

    def load_level(self, level_number: int, carry_states: dict[str, dict[str, object]] | None = None) -> None:
        self.level_number = level_number
        self.level = Level(level_number, self.assets)
        spawn_positions = self.level.find_spawn_positions(2 if self.mode == 2 else 1)

        mario = Player("Mario", *spawn_positions[0], self.assets["mario"], self.mario_controls(), (255, 120, 120))
        if carry_states and "mario" in carry_states:
            mario.load_state(carry_states["mario"])

        self.players = [mario]
        if self.mode == 2:
            luigi_spawn = spawn_positions[1] if len(spawn_positions) > 1 else spawn_positions[0]
            luigi = Player("Luigi", *luigi_spawn, self.assets["luigi"], self.luigi_controls(), (120, 255, 160))
            if carry_states and "luigi" in carry_states:
                luigi.load_state(carry_states["luigi"])
            self.players.append(luigi)

        self.player_by_name = {player.name.lower(): player for player in self.players}
        self.refresh_input_tracking()
        self.effects = []
        self.camera_x = 0
        self.level_banner_timer = FPS * 2

    def restart_current_game(self) -> None:
        if self.state == "menu":
            return
        self.start_game(self.mode)

    def advance_level(self) -> None:
        if self.level_number >= self.total_levels:
            self.state = "won"
            return
        carry_states = self.get_player_states()
        self.load_level(self.level_number + 1, carry_states=carry_states)

    def respawn_or_remove_player(self, player: Player) -> None:
        player.lives -= 1
        if player.lives <= 0:
            player.active = False
            player.power_type = "none"
            player.power_timer = 0
        else:
            player.power_type = "none"
            player.power_timer = 0
            player.respawn()
            if self.mode == 2:
                for teammate in self.players:
                    if teammate is player or teammate.lives <= 0:
                        continue
                    teammate.teleport_to_spawn(preserve_power=True, give_invuln=True)

        if not self.living_players():
            self.state = "game_over"

    def defeat_enemy(self, enemy: Enemy, actor: Player | None, score_bonus: int, bounce_player: bool = False,
                     coin_reward: int = 4) -> None:
        if self.level is None or enemy not in self.level.enemies:
            return
        self.level.enemies.remove(enemy)
        draw_x = enemy.rect.x - enemy.HITBOX_X
        draw_y = enemy.rect.y - enemy.HITBOX_Y
        self.effects.append(DefeatEffect(draw_x, draw_y, self.assets["enemy_flat"]))
        if actor is not None:
            actor.score += score_bonus
            actor.add_coins(coin_reward, score_per_coin=0)
            if bounce_player:
                actor.stomp_bounce()

    def handle_punch_hits(self, player: Player, solid_rects: list[pygame.Rect]) -> None:
        punch_rect = player.punch_rect()
        if punch_rect is None or not player.can_punch_damage_enemy() or self.level is None:
            return
        for enemy in list(self.level.enemies):
            if not player.can_punch_damage_enemy():
                break
            if not punch_rect.colliderect(enemy.rect):
                continue
            if enemy.frozen:
                player.register_punch_damage()
                self.defeat_enemy(enemy, player, 150, coin_reward=0)
                continue
            was_defeated = enemy.apply_punch_damage(player.facing, solid_rects)
            if was_defeated or enemy.damage_cooldown == ENEMY_DAMAGE_COOLDOWN:
                player.register_punch_damage()
            if was_defeated:
                self.defeat_enemy(enemy, player, 150, coin_reward=0)

    def handle_power_pickups(self) -> None:
        if self.level is None:
            return
        remaining_powers: list[PowerUpEntity] = []
        for entity in self.level.power_entities:
            collector = next((player for player in self.active_players() if player.rect.colliderect(entity.rect)), None)
            if collector is None:
                remaining_powers.append(entity)
                continue
            if entity.kind == "coin":
                collector.add_coins(1)
            else:
                collector.grant_power(entity.kind)
                collector.score += 100
        self.level.power_entities = remaining_powers

    def handle_enemy_collisions(self) -> None:
        if self.level is None:
            return
        for player in list(self.active_players()):
            if not player.active:
                continue
            for enemy in list(self.level.enemies):
                if not player.rect.colliderect(enemy.rect):
                    continue

                if player.power_type == "star":
                    self.defeat_enemy(enemy, player, 150)
                    continue

                if enemy.frozen:
                    continue

                stomp_depth = player.rect.bottom - enemy.rect.top
                centered_on_enemy = enemy.rect.left - 6 <= player.rect.centerx <= enemy.rect.right + 6
                if player.vy > 0 and stomp_depth < 18 and centered_on_enemy:
                    self.defeat_enemy(enemy, player, 100, bounce_player=True)
                    continue

                hit_result = player.take_enemy_hit(enemy.rect)
                if hit_result == "lose_life":
                    self.respawn_or_remove_player(player)
                    break

    def handle_projectile_hits(self) -> None:
        if self.level is None:
            return
        for proj in list(self.level.projectiles):
            if not proj.active:
                continue
            for enemy in list(self.level.enemies):
                if not proj.rect.colliderect(enemy.rect):
                    continue
                proj.active = False
                if proj.p_type == "fire":
                    self.defeat_enemy(enemy, proj.owner, 100)
                elif proj.p_type == "ice":
                    enemy.freeze()
                break

    def handle_goal_and_void(self) -> None:
        if self.level is None:
            return
        if self.level.goal:
            for player in self.active_players():
                if player.rect.colliderect(self.level.goal.rect):
                    if self.mode == 2:
                        for teammate in self.players:
                            if teammate.lives <= 0:
                                teammate.lives = 1
                                teammate.active = True
                                teammate.power_type = "none"
                                teammate.power_timer = 0
                    self.advance_level()
                    return
        for player in list(self.active_players()):
            if player.rect.top > self.level.pixel_height:
                self.respawn_or_remove_player(player)

    def enforce_two_player_visibility(self, previous_positions: dict[str, tuple[float, float]]) -> None:
        if self.mode != 2 or len(self.active_players()) < 2:
            return
        players = self.active_players()
        left_player = min(players, key=lambda p: p.rect.centerx)
        right_player = max(players, key=lambda p: p.rect.centerx)

        visible_width = SCREEN_WIDTH - 2 * CAMERA_PLAYER_MARGIN
        current_gap = right_player.rect.centerx - left_player.rect.centerx
        if current_gap <= visible_width:
            return

        prev_left_x = previous_positions[left_player.name.lower()][0]
        prev_right_x = previous_positions[right_player.name.lower()][0]

        if left_player.x < prev_left_x:
            left_player.x = prev_left_x
            left_player.rect.x = round(left_player.x)
        if right_player.x > prev_right_x:
            right_player.x = prev_right_x
            right_player.rect.x = round(right_player.x)

    def update_camera(self) -> None:
        if self.level is None:
            return
        active_players = self.active_players()
        if not active_players:
            return

        world_max = max(0, self.level.pixel_width - SCREEN_WIDTH)
        if len(active_players) == 1:
            player = active_players[0]
            self.camera_x = int(clamp(player.rect.centerx - SCREEN_WIDTH // 2, 0, world_max))
            return

        desired = sum(player.rect.centerx for player in active_players) / len(active_players) - SCREEN_WIDTH / 2
        lower_bound = max(player.rect.right + CAMERA_PLAYER_MARGIN - SCREEN_WIDTH for player in active_players)
        upper_bound = min(player.rect.left - CAMERA_PLAYER_MARGIN for player in active_players)
        lower_bound = max(0, lower_bound)
        upper_bound = min(world_max, upper_bound)

        if lower_bound <= upper_bound:
            self.camera_x = int(clamp(desired, lower_bound, upper_bound))
        else:
            self.camera_x = int(clamp(self.camera_x, 0, world_max))

    def update(self) -> None:
        if self.state != "playing" or self.level is None:
            return

        solid_rects = self.level.solid_rects()
        previous_positions = {player.name.lower(): (player.x, player.y) for player in self.players}

        for player in self.active_players():
            player.update(solid_rects, self.player_move_dir(player), self.level.pixel_width)

        self.enforce_two_player_visibility(previous_positions)

        for player in self.active_players():
            if player.punch_timer > 0:
                self.level.hit_tiles_from_punch(player.punch_rect(), self.effects)
                solid_rects = self.level.solid_rects()
                self.handle_punch_hits(player, solid_rects)

        for player in self.active_players():
            if player.ceiling_hit_rect is not None:
                self.level.hit_tiles_from_collision(player.ceiling_hit_rect)

        solid_rects = self.level.solid_rects()
        ground_rects = self.level.ground_rects()

        for enemy in self.level.enemies:
            enemy.update(solid_rects)
        for power in self.level.power_entities:
            power.update(solid_rects, ground_rects)
        for proj in self.level.projectiles:
            proj.update(solid_rects)
        self.level.projectiles = [proj for proj in self.level.projectiles if proj.active]

        for effect in self.effects:
            effect.update()
        self.effects = [effect for effect in self.effects if getattr(effect, "timer", 0) > 0]

        self.handle_power_pickups()
        self.handle_enemy_collisions()
        self.handle_projectile_hits()
        self.handle_goal_and_void()
        self.update_camera()

        if self.level_banner_timer > 0:
            self.level_banner_timer -= 1
        if self.help_timer > 0:
            self.help_timer -= 1

    def draw_background(self) -> None:
        bg = self.assets["background"]
        offset_x = -((self.camera_x // 4) % TILE_SIZE)
        for x in range(offset_x - TILE_SIZE, SCREEN_WIDTH + TILE_SIZE, TILE_SIZE):
            for y in range(0, SCREEN_HEIGHT, TILE_SIZE):
                self.screen.blit(bg, (x, y))

    def draw_hud(self) -> None:
        panel = pygame.Surface((SCREEN_WIDTH, 54), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 125))
        self.screen.blit(panel, (0, 0))

        left_text = f"Level {self.level_number}/{self.total_levels}  -  Level {self.level_number}"
        draw_text(self.screen, self.hud_font, left_text, 16, 8)

        if self.mode == 1:
            mario = self.player_by_name["mario"]
            right_text = (
                f"Coins: {mario.coins}   Score: {mario.score}   Lives: {mario.lives}   Power: {mario.power_display()}"
            )
            right_image = self.hud_font.render(right_text, True, (255, 255, 255))
            right_shadow = self.hud_font.render(right_text, True, (0, 0, 0))
            rx = SCREEN_WIDTH - right_image.get_width() - 16
            self.screen.blit(right_shadow, (rx + 2, 10))
            self.screen.blit(right_image, (rx, 8))
            return

        mario = self.player_by_name["mario"]
        luigi = self.player_by_name["luigi"]
        mario_text = (
            f"MARIO  C:{mario.coins}  S:{mario.score}  L:{mario.lives}  P:{mario.power_display()}"
        )
        luigi_text = (
            f"LUIGI  C:{luigi.coins}  S:{luigi.score}  L:{luigi.lives}  P:{luigi.power_display()}"
        )
        draw_text(self.screen, self.small_font, mario_text, 18, 28, mario.hud_color)
        luigi_image = self.small_font.render(luigi_text, True, luigi.hud_color)
        luigi_shadow = self.small_font.render(luigi_text, True, (0, 0, 0))
        rx = SCREEN_WIDTH - luigi_image.get_width() - 18
        self.screen.blit(luigi_shadow, (rx + 2, 30))
        self.screen.blit(luigi_image, (rx, 28))

    def draw_banner(self) -> None:
        if self.state == "playing" and self.level_banner_timer > 0:
            overlay = pygame.Surface((SCREEN_WIDTH, 90), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 110))
            self.screen.blit(overlay, (0, 72))
            center_text(self.screen, self.info_font, f"Level {self.level_number}", 100)

        if self.help_timer <= 0 or self.state != "playing":
            return

        hint_panel = pygame.Surface((SCREEN_WIDTH, 46), pygame.SRCALPHA)
        hint_panel.fill((0, 0, 0, 105))
        self.screen.blit(hint_panel, (0, SCREEN_HEIGHT - 46))

        if self.mode == 1:
            hint = "1P  Move: A/D or Arrows   Jump: W/Up/Space   Punch: Left Shift   Shoot: F"
        else:
            hint = "Mario: Arrows + Right Shift/Ctrl   Luigi: mouse left/right, right click jump, Left Shift punch, 1 shoot   Space: both jump"
        center_text(self.screen, self.small_font, hint, SCREEN_HEIGHT - 34)

    def draw_overlay(self) -> None:
        if self.state not in {"game_over", "won"}:
            return
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        if self.state == "won":
            center_text(self.screen, self.title_font, "You cleared all 20 levels!", 220, (255, 240, 120))
            if self.mode == 1:
                mario = self.player_by_name["mario"]
                center_text(self.screen, self.info_font, f"Final score: {mario.score}   Coins: {mario.coins}", 320)
            else:
                mario = self.player_by_name["mario"]
                luigi = self.player_by_name["luigi"]
                center_text(self.screen, self.info_font, f"Mario {mario.score}  |  Luigi {luigi.score}", 320)
            center_text(self.screen, self.info_font, "Press Enter to return to menu", 370)
        else:
            center_text(self.screen, self.title_font, "Game Over", 230, (255, 180, 180))
            center_text(self.screen, self.info_font, "Press Enter to return to menu", 340)

    def draw_menu(self) -> None:
        self.screen.fill((40, 40, 70))
        menu_image = self.assets["menu"]
        menu_rect, one_rect, two_rect = self.build_menu_layout()
        scaled_menu = pygame.transform.scale(menu_image, menu_rect.size)
        self.screen.blit(scaled_menu, menu_rect.topleft)

        mouse_pos = pygame.mouse.get_pos()
        button_specs = [
            (1, one_rect, "1 PLAYER GAME"),
            (2, two_rect, "2 PLAYER GAME"),
        ]
        for mode, rect, label in button_specs:
            hovered = rect.collidepoint(mouse_pos)
            selected = self.menu_selection == mode
            fill = (0, 0, 0, 115)
            if hovered:
                fill = (255, 255, 120, 95)
                self.menu_selection = mode
            elif selected:
                fill = (255, 220, 80, 70)

            panel = pygame.Surface(rect.size, pygame.SRCALPHA)
            panel.fill(fill)
            self.screen.blit(panel, rect.topleft)
            border_color = (255, 245, 170) if (hovered or selected) else (255, 255, 255)
            pygame.draw.rect(self.screen, border_color, rect, 3, border_radius=8)
            center_text(self.screen, self.info_font, label, rect.y + max(4, rect.height // 6), (255, 255, 255))

        center_text(self.screen, self.hud_font, "Click a mode, or use Up/Down and Enter", SCREEN_HEIGHT - 80)
        center_text(self.screen, self.small_font, "Keyboard shortcuts: press 1 or 2", SCREEN_HEIGHT - 50)

    def draw(self) -> None:
        if self.state == "menu":
            self.draw_menu()
            return

        self.draw_background()
        if self.level is not None:
            self.level.draw(self.screen, self.camera_x, self.frame_count, self.effects)
        for player in self.players:
            player.draw(self.screen, self.camera_x)
        self.draw_hud()
        self.draw_banner()
        self.draw_overlay()

    def draw_fullscreen_button(self) -> None:
        self.update_fullscreen_button_rect()
        rect = self.fullscreen_button_rect
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill((0, 0, 0, 145))
        self.window.blit(panel, rect.topleft)
        pygame.draw.rect(self.window, (255, 255, 255), rect, 2, border_radius=8)
        inset = 10
        if self.fullscreen_ui_active():
            pygame.draw.line(self.window, (255, 255, 255), (rect.left + inset, rect.top + inset + 8), (rect.left + inset, rect.top + inset), 2)
            pygame.draw.line(self.window, (255, 255, 255), (rect.left + inset, rect.top + inset), (rect.left + inset + 8, rect.top + inset), 2)
            pygame.draw.line(self.window, (255, 255, 255), (rect.right - inset - 8, rect.top + inset), (rect.right - inset, rect.top + inset), 2)
            pygame.draw.line(self.window, (255, 255, 255), (rect.right - inset, rect.top + inset), (rect.right - inset, rect.top + inset + 8), 2)
            pygame.draw.line(self.window, (255, 255, 255), (rect.left + inset, rect.bottom - inset - 8), (rect.left + inset, rect.bottom - inset), 2)
            pygame.draw.line(self.window, (255, 255, 255), (rect.left + inset, rect.bottom - inset), (rect.left + inset + 8, rect.bottom - inset), 2)
            pygame.draw.line(self.window, (255, 255, 255), (rect.right - inset - 8, rect.bottom - inset), (rect.right - inset, rect.bottom - inset), 2)
            pygame.draw.line(self.window, (255, 255, 255), (rect.right - inset, rect.bottom - inset - 8), (rect.right - inset, rect.bottom - inset), 2)
        else:
            inner = rect.inflate(-16, -16)
            pygame.draw.rect(self.window, (255, 255, 255), inner, 2)

    def present_frame(self) -> None:
        surface = pygame.display.get_surface()
        if surface is None:
            return
        self.window = surface
        self.window.fill((30, 30, 52))
        game_rect = self.get_game_view_rect()
        if game_rect.size != (SCREEN_WIDTH, SCREEN_HEIGHT):
            scaled = pygame.transform.smoothscale(self.screen, game_rect.size)
            self.window.blit(scaled, game_rect.topleft)
        else:
            self.window.blit(self.screen, game_rect.topleft)
        self.draw_fullscreen_button()

    def handle_menu_click(self, mouse_pos: tuple[int, int]) -> None:
        _, one_rect, two_rect = self.build_menu_layout()
        if one_rect.collidepoint(mouse_pos):
            self.start_game(1)
        elif two_rect.collidepoint(mouse_pos):
            self.start_game(2)

    def handle_mouse_click(self, mouse_pos: tuple[int, int]) -> None:
        self.update_fullscreen_button_rect()
        if self.fullscreen_button_rect.collidepoint(mouse_pos):
            self.toggle_fullscreen()
            return
        game_pos = self.screen_to_game_pos(mouse_pos)
        if game_pos is None:
            return
        if self.state == "menu":
            self.handle_menu_click(game_pos)

    def handle_keydown(self, event: pygame.event.Event) -> None:
        if self.state == "menu":
            if event.key == pygame.K_1:
                self.start_game(1)
            elif event.key == pygame.K_2:
                self.start_game(2)
            elif event.key in (pygame.K_UP, pygame.K_w, pygame.K_LEFT, pygame.K_a):
                self.menu_selection = 1
            elif event.key in (pygame.K_DOWN, pygame.K_s, pygame.K_RIGHT, pygame.K_d):
                self.menu_selection = 2
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start_game(self.menu_selection)
            return

        if event.key == pygame.K_r and self.state == "playing":
            carry_states = self.get_player_states()
            self.load_level(self.level_number, carry_states=carry_states)
            return

        if event.key == pygame.K_RETURN and self.state in {"game_over", "won"}:
            self.state = "menu"
            return

        if self.state != "playing":
            return

    def process_action_inputs(self) -> None:
        if self.state != "playing" or self.level is None:
            return

        for player in self.players:
            key_name = player.name.lower()
            prev = self.prev_action_state.setdefault(key_name, {"jump": False, "shoot": False, "punch": False})
            if not player.active:
                prev["jump"] = False
                prev["shoot"] = False
                prev["punch"] = False
                continue

            jump_held = self.key_group_pressed(player.controls.jump_keys)
            punch_held = self.key_group_pressed(player.controls.punch_keys)
            shoot_held = self.key_group_pressed(player.controls.shoot_keys)

            if self.mode == 2 and player.name.lower() == "luigi":
                jump_held = jump_held or self.mouse_button_held["right"] or self.luigi_jump_buffer > 0

            if jump_held and not prev["jump"]:
                player.jump()
                if self.mode == 2 and player.name.lower() == "luigi":
                    self.luigi_jump_buffer = 0
            if punch_held and not prev["punch"]:
                player.start_punch()
            if shoot_held and (not prev["shoot"] or player.shoot_cooldown <= 0):
                player.shoot(self.level.projectiles)

            prev["jump"] = jump_held
            prev["punch"] = punch_held
            prev["shoot"] = shoot_held

    def run(self, max_frames: int | None = None, screenshot_path: Path | None = None) -> int:
        screenshot_saved = False
        if screenshot_path is not None:
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)

        while self.running:
            self.update_mouse_tracking()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.WINDOWFOCUSLOST:
                    self.clear_held_inputs()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_F11:
                        self.toggle_fullscreen()
                        continue
                    if event.key == pygame.K_RETURN and (event.mod & pygame.KMOD_ALT):
                        self.toggle_fullscreen()
                        continue
                    self.register_keydown(event.key)
                    self.handle_keydown(event)
                elif event.type == pygame.KEYUP:
                    self.register_keyup(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        self.handle_mouse_click(event.pos)
                    elif event.button == 3 and self.mode == 2 and self.state == "playing":
                        self.luigi_jump_buffer = max(self.luigi_jump_buffer, INPUT_GRACE_FRAMES + 1)

            self.process_action_inputs()
            self.update()
            self.draw()

            if screenshot_path is not None and not screenshot_saved:
                pygame.image.save(self.window, str(screenshot_path))
                screenshot_saved = True

            self.present_frame()
            pygame.display.flip()
            self.clock.tick(FPS)
            self.frame_count += 1
            if max_frames is not None and self.frame_count >= max_frames:
                break
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Mario-style platformer.")
    parser.add_argument(
        "--start-level",
        type=int,
        default=1,
        help="Start at a specific level number (1-20).",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    game = MarioGame(base_dir=base_dir, start_level=args.start_level)
    try:
        return game.run()
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
