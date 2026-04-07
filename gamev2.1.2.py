#!/usr/bin/env python3
"""A Mario-style platformer with 20 levels, directional punches, and dynamic lucky boxes."""
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
    surf = pygame.Surface(size)
    surf.fill(color)
    pygame.draw.rect(surf, (0, 0, 0), surf.get_rect(), 2)
    return surf


def load_image_or_fallback(path: Path, size: tuple[int, int], fallback_color: tuple[int, int, int]) -> pygame.Surface:
    if not path.exists():
        return create_fallback_image(fallback_color, size)
    try:
        image = pygame.image.load(str(path)).convert_alpha()
        return pygame.transform.scale(image, size)
    except Exception:
        return create_fallback_image(fallback_color, size)


def load_assets(base_dir: Path) -> dict[str, pygame.Surface]:
    coin_size = int(TILE_SIZE * 0.72)
    return {
        "background": load_image_or_fallback(base_dir / "0.png", (TILE_SIZE, TILE_SIZE), (100, 150, 255)),
        "brick": load_image_or_fallback(base_dir / "1.png", (TILE_SIZE, TILE_SIZE), (150, 75, 0)),
        "ground": load_image_or_fallback(base_dir / "2.png", (TILE_SIZE, TILE_SIZE), (50, 150, 50)),
        "enemy": load_image_or_fallback(base_dir / "3.png", (TILE_SIZE, TILE_SIZE), (200, 0, 0)),
        "coin": load_image_or_fallback(base_dir / "4.png", (coin_size, coin_size), (255, 255, 0)),
        "player": load_image_or_fallback(base_dir / "5.png", (TILE_SIZE, TILE_SIZE), (0, 0, 255)),
        "flag": load_image_or_fallback(base_dir / "6.png", (TILE_SIZE, TILE_SIZE), (0, 255, 0)),
        "enemy_flat": load_image_or_fallback(base_dir / "death.png", (TILE_SIZE, TILE_SIZE), (100, 0, 0)),
        "lucky_box": load_image_or_fallback(base_dir / "power box.jpg", (TILE_SIZE, TILE_SIZE), (255, 200, 0)),
        "fireflower": load_image_or_fallback(base_dir / "fireflower.png", (TILE_SIZE, TILE_SIZE), (255, 100, 0)),
        "icef": load_image_or_fallback(base_dir / "icef.png", (TILE_SIZE, TILE_SIZE), (0, 255, 255)),
        "shroom": load_image_or_fallback(base_dir / "shroom.png", (TILE_SIZE, TILE_SIZE), (255, 50, 50)),
        "star": load_image_or_fallback(base_dir / "star.png", (TILE_SIZE, TILE_SIZE), (255, 255, 100)),
        "gshroom": load_image_or_fallback(base_dir / "gshroom.jpg", (TILE_SIZE, TILE_SIZE), (200, 180, 50)),
    }


@dataclass
class Tile:
    rect: pygame.Rect
    image: pygame.Surface
    kind: str


class Projectile:
    def __init__(self, x: float, y: float, direction: int, p_type: str) -> None:
        self.x = x
        self.y = y
        self.vx = 8.0 * direction
        self.vy = 0.0
        self.p_type = p_type
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

    def set_safe_drop_target(self, segment_rect: pygame.Rect, target_x: float) -> None:
        self.drop_target_x = float(target_x)
        self.drop_target_top = segment_rect.top
        self.drop_bounds = (segment_rect.left, segment_rect.right)
        self.guided_drop = True
        if self.speed != 0:
            if self.drop_target_x < self.x - 2:
                self.direction = -1
            elif self.drop_target_x > self.x + 2:
                self.direction = 1

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


class Coin:
    def __init__(self, x: int, y: int, image: pygame.Surface, phase: float) -> None:
        self.image = image
        self.phase = phase
        offset_x = (TILE_SIZE - image.get_width()) // 2
        offset_y = (TILE_SIZE - image.get_height()) // 2
        self.draw_x = x + offset_x
        self.draw_y = y + offset_y
        self.rect = pygame.Rect(
            self.draw_x + 4,
            self.draw_y + 4,
            image.get_width() - 8,
            image.get_height() - 8,
        )

    def draw(self, screen: pygame.Surface, camera_x: int, frame_count: int) -> None:
        bob = int(math.sin(frame_count * 0.13 + self.phase) * 4)
        screen.blit(self.image, (self.draw_x - camera_x, self.draw_y + bob))


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

    def freeze(self) -> None:
        self.frozen = True
        self.frozen_timer = FPS * 10

    def update(self, solid_rects: Iterable[pygame.Rect]) -> None:
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
        else:
            image = self.image if self.direction >= 0 else self.flipped_image
            screen.blit(image, (draw_x - camera_x, draw_y))


class Player:
    HITBOX_X = 5
    HITBOX_Y = 4
    HITBOX_W = TILE_SIZE - 10
    HITBOX_H = TILE_SIZE - 4

    def __init__(self, spawn_x: int, spawn_y: int, image: pygame.Surface) -> None:
        self.image_right = image
        self.image_left = pygame.transform.flip(image, True, False)
        self.facing = 1

        self.power_type = "none"
        self.power_timer = 0
        self.shoot_cooldown = 0

        self.invuln_timer = 0
        self.punch_timer = 0
        self.ceiling_bump = False
        self.reset(spawn_x, spawn_y)

    def reset(self, spawn_x: int, spawn_y: int) -> None:
        current_invuln = getattr(self, "invuln_timer", 0)
        current_shoot_cooldown = getattr(self, "shoot_cooldown", 0)
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
        self.power_type = "none"
        self.power_timer = 0
        self.invuln_timer = current_invuln
        self.shoot_cooldown = current_shoot_cooldown

    def current_gravity(self) -> float:
        if self.power_type in ["golden", "mushroom", "star"]:
            if self.vy <= 0:
                return POWER_GRAVITY_ASCEND
            return POWER_GRAVITY_DESCEND
        return GRAVITY

    def jump(self) -> None:
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
        if self.shoot_cooldown > 0:
            return
        if self.power_type == "fire":
            projectiles.append(Projectile(self.rect.centerx, self.rect.centery, self.facing, "fire"))
            self.shoot_cooldown = int(FPS * 0.5)
        elif self.power_type == "ice":
            projectiles.append(Projectile(self.rect.centerx, self.rect.centery, self.facing, "ice"))
            self.shoot_cooldown = FPS * 2

    def start_punch(self) -> None:
        self.punch_timer = PUNCH_DURATION

    def punch_rect(self) -> pygame.Rect | None:
        if self.punch_timer <= 0:
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
        if self.invuln_timer > 0 or self.power_type == "star":
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

    def update(self, solid_rects: Iterable[pygame.Rect], keys: pygame.key.ScancodeWrapper, world_width: int) -> None:
        self.ceiling_bump = False
        move_dir = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            move_dir -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            move_dir += 1

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
                    self.rect.top = solid.bottom
                    self.ceiling_bump = True
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

    s = list(lines[-3])
    s[1] = "P"
    lines[-3] = "".join(s)

    s = list(lines[-3])
    s[width - 3] = "F"
    lines[-3] = "".join(s)

    i = 5
    while i < width - 5:
        if random.random() < 0.35:
            gap_width = random.randint(2, 3)
            s1, s2 = list(lines[-2]), list(lines[-1])
            s1[i:i + gap_width] = "." * gap_width
            s2[i:i + gap_width] = "." * gap_width
            lines[-2], lines[-1] = "".join(s1), "".join(s2)
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

        for row, line in enumerate(lines):
            for col, char in enumerate(line):
                x = col * TILE_SIZE
                y = row * TILE_SIZE
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
            self.configure_entity_drop(power)

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
            target_center_x = target_x_for(segment) + (entity_width / 2)
            return abs(target_center_x - spawn_center_x)

        nearby_candidates = [
            segment for segment in candidates
            if horizontal_distance(segment) <= TILE_SIZE * 3.5
        ]
        if nearby_candidates:
            best_segment = min(nearby_candidates, key=lambda segment: (-segment.top, horizontal_distance(segment)))
        else:
            def candidate_score(segment: pygame.Rect) -> tuple[float, float, float]:
                dx = horizontal_distance(segment)
                dy = abs(segment.top - spawn_y)
                vertical_bonus = max(0, segment.top - spawn_y)
                return (dx + dy * 0.65, vertical_bonus, dx)

            best_segment = min(candidates, key=candidate_score)

        return best_segment, target_x_for(best_segment)

    def configure_entity_drop(self, entity: PowerUpEntity) -> None:
        target = self.find_drop_segment(entity.rect.centerx, entity.rect.bottom, entity.rect.width)
        if target is None:
            return
        segment, target_x = target
        entity.set_safe_drop_target(segment, target_x)

    def visible(self, rect: pygame.Rect, camera_x: int) -> bool:
        return rect.right >= camera_x - TILE_SIZE and rect.left <= camera_x + SCREEN_WIDTH + TILE_SIZE

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
        self.configure_entity_drop(entity)
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
        for tile in list(self.tiles):
            if not tile.rect.colliderect(hit_rect):
                continue
            if tile.kind == "brick":
                self.spawn_brick_break(tile, effects)
                self.tiles.remove(tile)
                did_hit = True
            elif tile.kind == "lucky_box":
                self.trigger_lucky_box(tile)
                did_hit = True
            elif tile.kind in {"ground", "used_power"}:
                did_hit = True
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
    def __init__(self, base_dir: Path, start_level: int = 1) -> None:
        pygame.init()
        pygame.display.set_caption("Super Mario Python Game")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()

        self.hud_font = pygame.font.Font(None, 28)
        self.info_font = pygame.font.Font(None, 40)
        self.title_font = pygame.font.Font(None, 72)

        self.base_dir = base_dir
        self.assets = load_assets(base_dir)
        self.total_levels = 20

        self.frame_count = 0
        self.running = True
        self.start_level = int(clamp(start_level, 1, self.total_levels))

        self.reset_game()

    def reset_game(self) -> None:
        self.level_number = self.start_level
        self.score = 0
        self.coins = 0
        self.lives = STARTING_LIVES
        self.effects: list[object] = []
        self.state = "playing"
        self.help_timer = FPS * 14
        self.camera_x = 0
        self.load_level(self.level_number)

    def load_level(self, level_number: int, carry_power: str = "none") -> None:
        self.level_number = level_number
        self.level = Level(level_number, self.assets)
        self.player = Player(*self.level.spawn, self.assets["player"])
        self.player.grant_power(carry_power)
        self.effects = []
        self.camera_x = 0
        self.level_banner_timer = FPS * 2

    def lose_life(self) -> None:
        self.lives -= 1
        if self.lives <= 0:
            self.state = "game_over"
            return
        self.load_level(self.level_number)
        self.player.invuln_timer = RESPAWN_INVULN_DURATION

    def win_level(self) -> None:
        self.score += 500
        if self.level_number >= self.total_levels:
            self.state = "won"
        else:
            self.load_level(self.level_number + 1, carry_power=self.player.power_type)

    def add_coins(self, amount: int, score_per_coin: int = 50) -> None:
        if amount <= 0:
            return
        previous_coins = self.coins
        self.coins += amount
        self.score += amount * score_per_coin
        gained_lives = (self.coins // 12) - (previous_coins // 12)
        if gained_lives > 0:
            self.lives += gained_lives

    def defeat_enemy(self, enemy: Enemy, score_bonus: int, bounce_player: bool = False) -> None:
        if enemy not in self.level.enemies:
            return
        self.level.enemies.remove(enemy)
        draw_x = enemy.rect.x - enemy.HITBOX_X
        draw_y = enemy.rect.y - enemy.HITBOX_Y
        self.effects.append(DefeatEffect(draw_x, draw_y, self.assets["enemy_flat"]))
        self.score += score_bonus
        self.add_coins(4, score_per_coin=0)
        if bounce_player:
            self.player.stomp_bounce()

    def handle_collisions(self) -> None:
        remaining_powers = []
        for p in self.level.power_entities:
            if self.player.rect.colliderect(p.rect):
                if p.kind == "coin":
                    self.add_coins(1)
                else:
                    self.player.grant_power(p.kind)
                    self.score += 100
            else:
                remaining_powers.append(p)
        self.level.power_entities = remaining_powers

        for enemy in list(self.level.enemies):
            if not self.player.rect.colliderect(enemy.rect):
                continue

            if self.player.power_type == "star":
                self.defeat_enemy(enemy, 150)
                continue

            if enemy.frozen:
                hit_rect = self.player.punch_rect()
                if hit_rect and hit_rect.colliderect(enemy.rect):
                    self.defeat_enemy(enemy, 150)
                continue

            stomp_depth = self.player.rect.bottom - enemy.rect.top
            centered_on_enemy = enemy.rect.left - 6 <= self.player.rect.centerx <= enemy.rect.right + 6
            if self.player.vy > 0 and stomp_depth < 18 and centered_on_enemy:
                self.defeat_enemy(enemy, 100, bounce_player=True)
                continue

            hit_result = self.player.take_enemy_hit(enemy.rect)
            if hit_result == "lose_life":
                self.lose_life()
                return
            if hit_result == "power_lost":
                return

        for proj in self.level.projectiles:
            if not proj.active:
                continue
            for enemy in list(self.level.enemies):
                if proj.rect.colliderect(enemy.rect):
                    proj.active = False
                    if proj.p_type == "fire":
                        self.defeat_enemy(enemy, 100)
                    elif proj.p_type == "ice":
                        enemy.freeze()
                    break

        if self.level.goal and self.player.rect.colliderect(self.level.goal.rect):
            self.win_level()
            return

        if self.player.rect.top > self.level.pixel_height:
            self.lose_life()

    def update(self) -> None:
        if self.state != "playing":
            return

        keys = pygame.key.get_pressed()

        solid_rects = self.level.solid_rects()
        self.player.update(solid_rects, keys, self.level.pixel_width)

        if self.player.punch_timer > 0:
            self.level.hit_tiles_from_punch(self.player.punch_rect(), self.effects)

        if self.player.ceiling_bump:
            head_rect = pygame.Rect(self.player.rect.x, self.player.rect.y - 6, self.player.rect.width, 8)
            self.level.hit_tiles_from_collision(head_rect)

        solid_rects = self.level.solid_rects()
        ground_rects = self.level.ground_rects()
        for enemy in self.level.enemies:
            enemy.update(solid_rects)

        for power in self.level.power_entities:
            power.update(solid_rects, ground_rects)

        for proj in self.level.projectiles:
            proj.update(solid_rects)
        self.level.projectiles = [p for p in self.level.projectiles if p.active]

        for effect in self.effects:
            effect.update()
        self.effects = [effect for effect in self.effects if getattr(effect, "timer", 0) > 0]

        self.handle_collisions()

        self.camera_x = int(
            clamp(
                self.player.rect.centerx - SCREEN_WIDTH // 2,
                0,
                max(0, self.level.pixel_width - SCREEN_WIDTH),
            )
        )

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
        panel = pygame.Surface((SCREEN_WIDTH, 44), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 120))
        self.screen.blit(panel, (0, 0))

        left_text = f"Level {self.level_number}/{self.total_levels}  -  {self.level.title}"
        power_str = self.player.power_type.upper() if self.player.power_type != "none" else "OFF"
        if self.player.power_timer > 0: power_str += f" ({self.player.power_timer // FPS}s)"

        right_text = f"Coins: {self.coins}   Score: {self.score}   Lives: {self.lives}   Power: {power_str}"
        draw_text(self.screen, self.hud_font, left_text, 16, 11)
        right_image = self.hud_font.render(right_text, True, (255, 255, 255))
        right_shadow = self.hud_font.render(right_text, True, (0, 0, 0))
        rx = SCREEN_WIDTH - right_image.get_width() - 16
        self.screen.blit(right_shadow, (rx + 2, 13))
        self.screen.blit(right_image, (rx, 11))

    def draw_banner(self) -> None:
        if self.state == "playing" and self.level_banner_timer > 0:
            overlay = pygame.Surface((SCREEN_WIDTH, 90), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 110))
            self.screen.blit(overlay, (0, 72))
            center_text(self.screen, self.info_font, f"Level {self.level_number}: {self.level.title}", 100)
        if self.help_timer > 0 and self.state == "playing":
            hint_panel = pygame.Surface((SCREEN_WIDTH, 38), pygame.SRCALPHA)
            hint_panel.fill((0, 0, 0, 100))
            self.screen.blit(hint_panel, (0, SCREEN_HEIGHT - 38))
            hint = "Move: A/D  Jump: W  Punch: Shift  Shoot: F  Restart: R"
            center_text(self.screen, self.hud_font, hint, SCREEN_HEIGHT - 30)

    def draw_overlay(self) -> None:
        if self.state not in {"game_over", "won"}:
            return
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        if self.state == "won":
            center_text(self.screen, self.title_font, "You cleared all 20 levels!", 220, (255, 240, 120))
            center_text(self.screen, self.info_font, f"Final score: {self.score}   Coins: {self.coins}", 320)
            center_text(self.screen, self.info_font, "Press Enter to play again", 370)
        else:
            center_text(self.screen, self.title_font, "Game Over", 230, (255, 180, 180))
            center_text(self.screen, self.info_font, f"Final score: {self.score}   Coins: {self.coins}", 320)
            center_text(self.screen, self.info_font, "Press Enter to restart", 370)

    def draw(self) -> None:
        self.draw_background()
        self.level.draw(self.screen, self.camera_x, self.frame_count, self.effects)
        self.player.draw(self.screen, self.camera_x)
        self.draw_hud()
        self.draw_banner()
        self.draw_overlay()

    def run(self, max_frames: int | None = None, screenshot_path: Path | None = None) -> int:
        screenshot_saved = False
        if screenshot_path is not None:
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)

        while self.running:
            jump_requested = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_UP, pygame.K_w, pygame.K_SPACE):
                        jump_requested = True
                    elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                        if self.state == "playing":
                            self.player.start_punch()
                    elif event.key == pygame.K_f:
                        if self.state == "playing":
                            self.player.shoot(self.level.projectiles)
                    elif event.key == pygame.K_r:
                        if self.state == "playing":
                            self.load_level(self.level_number)
                    elif event.key == pygame.K_RETURN:
                        if self.state in {"game_over", "won"}:
                            self.start_level = 1
                            self.reset_game()

            if self.state == "playing" and jump_requested:
                self.player.jump()

            self.update()
            self.draw()

            if screenshot_path is not None and not screenshot_saved:
                pygame.image.save(self.screen, str(screenshot_path))
                screenshot_saved = True

            pygame.display.flip()
            self.clock.tick(FPS)
            self.frame_count += 1

            if max_frames is not None and self.frame_count >= max_frames:
                break
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the 20-level Mario-style platformer.")
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