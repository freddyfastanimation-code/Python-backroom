from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.graphics import Rectangle, Color, Line, Ellipse
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.config import Config
import math
import random

# ==================== AUTO LANDSCAPE ====================
Config.set('graphics', 'orientation', 'landscape')

# ==================== KONFIGURASI ====================
MAP_SIZE = 21
CELL_SIZE = 64
FOV = math.pi / 3
NUM_RAYS = 50
MAX_DEPTH = 600
PLAYER_SPEED = 5
ROT_SPEED = 0.08

# ==================== WARNA BACKROOMS ====================
WALL_NORMAL = (0.72, 0.68, 0.42)
WALL_WET = (0.55, 0.52, 0.30)
WALL_MOLD = (0.35, 0.40, 0.25)
WALL_STAIN = (0.60, 0.55, 0.35)
WALL_DARK = (0.45, 0.42, 0.22)
FLOOR = (0.38, 0.35, 0.28)
CEILING = (0.85, 0.82, 0.65)
DOOR = (0.5, 0.45, 0.35)

# ==================== GENERATE MAZE ====================
def generate_maze(size):
    if size % 2 == 0:
        size += 1
    grid = [[1 for _ in range(size)] for _ in range(size)]

    def carve(x, y):
        grid[y][x] = 0
        dirs = [(0, -2), (2, 0), (0, 2), (-2, 0)]
        random.shuffle(dirs)
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if 1 <= nx < size - 1 and 1 <= ny < size - 1 and grid[ny][nx] == 1:
                grid[y + dy // 2][x + dx // 2] = 0
                carve(nx, ny)

    carve(1, 1)

    for _ in range(size * 2):
        x = random.randint(2, size - 3)
        y = random.randint(2, size - 3)
        if grid[y][x] == 1:
            neighbors = sum(1 for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)] if grid[y+dy][x+dx] == 0)
            if neighbors >= 2:
                grid[y][x] = 0

    grid[size - 2][size - 2] = 2

    wall_types = {}
    doors = []
    for y, row in enumerate(grid):
        for x, cell in enumerate(row):
            if cell == 1:
                r = random.random()
                if r < 0.5:
                    wall_types[(x, y)] = 'normal'
                elif r < 0.65:
                    wall_types[(x, y)] = 'wet'
                elif r < 0.78:
                    wall_types[(x, y)] = 'stain'
                elif r < 0.88:
                    wall_types[(x, y)] = 'mold'
                else:
                    wall_types[(x, y)] = 'dark'

                if random.random() < 0.25:
                    for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
                        nx, ny = x+dx, y+dy
                        if 0 <= nx < size and 0 <= ny < size and grid[ny][nx] == 0:
                            doors.append((x, y, dx, dy))
                            break

    return grid, wall_types, doors

# ==================== PLAYER ====================
class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.angle = 0
        self.won = False

    def can_move(self, new_x, new_y, grid):
        margin = 10
        for dx, dy in [(-margin, -margin), (margin, -margin), (-margin, margin), (margin, margin)]:
            mx = int((new_x + dx) / CELL_SIZE)
            my = int((new_y + dy) / CELL_SIZE)
            if not (0 <= mx < len(grid[0]) and 0 <= my < len(grid)):
                return False
            if grid[my][mx] == 1:
                return False
        return True

    def move(self, direction, grid):
        new_x = self.x + math.cos(self.angle) * direction * PLAYER_SPEED
        new_y = self.y + math.sin(self.angle) * direction * PLAYER_SPEED
        if self.can_move(new_x, self.y, grid):
            self.x = new_x
        if self.can_move(self.x, new_y, grid):
            self.y = new_y

    def rotate(self, direction):
        self.angle += direction * ROT_SPEED

# ==================== RAYCASTER ====================
class Raycaster:
    def cast(self, player, grid, wall_types, doors, sw, sh):
        walls = []
        for i in range(NUM_RAYS):
            ray_angle = player.angle - FOV / 2 + (i / NUM_RAYS) * FOV
            for depth in range(5, MAX_DEPTH, 10):
                tx = player.x + math.cos(ray_angle) * depth
                ty = player.y + math.sin(ray_angle) * depth
                col = int(tx / CELL_SIZE)
                row = int(ty / CELL_SIZE)
                if 0 <= col < len(grid[0]) and 0 <= row < len(grid):
                    cell = grid[row][col]
                    if cell in [1, 2]:
                        depth_fix = depth * math.cos(player.angle - ray_angle)
                        wall_h = min(sh, (CELL_SIZE * sh) / (depth_fix + 0.001))
                        dist_fog = max(0.15, 1 - depth / MAX_DEPTH)
                        is_door = any(d[0] == col and d[1] == row for d in doors)
                        if cell == 2:
                            color = (0.5 * dist_fog, 0.6 * dist_fog, 0.4 * dist_fog)
                        elif is_door:
                            color = (DOOR[0] * dist_fog, DOOR[1] * dist_fog, DOOR[2] * dist_fog)
                        else:
                            wtype = wall_types.get((col, row), 'normal')
                            base = {'normal': WALL_NORMAL, 'wet': WALL_WET, 'stain': WALL_STAIN, 'mold': WALL_MOLD, 'dark': WALL_DARK}.get(wtype, WALL_NORMAL)
                            color = (base[0] * dist_fog, base[1] * dist_fog, base[2] * dist_fog)
                        walls.append({'x': i * (sw / NUM_RAYS), 'w': sw / NUM_RAYS + 1, 'h': wall_h, 'color': color, 'is_door': is_door})
                        break
        return walls

# ==================== PETA ====================
class Peta(Widget):
    def __init__(self, player, grid, **kwargs):
        super().__init__(**kwargs)
        self.player = player
        self.grid = grid
        self.scale = 4
        Clock.schedule_interval(self.draw, 1/5)

    def draw(self, dt):
        self.canvas.clear()
        with self.canvas:
            Color(0.08, 0.08, 0.06)
            Rectangle(pos=self.pos, size=self.size)
            for y in range(0, len(self.grid), 2):
                for x in range(0, len(self.grid[0]), 2):
                    cell = self.grid[y][x]
                    if cell == 1:
                        Color(0.55, 0.5, 0.32)
                        Rectangle(pos=(self.x + x*self.scale, self.y + y*self.scale), size=(self.scale, self.scale))
                    elif cell == 2:
                        Color(0.4, 0.5, 0.35)
                        Rectangle(pos=(self.x + x*self.scale, self.y + y*self.scale), size=(self.scale, self.scale))
            Color(0.9, 0.15, 0.15)
            px = self.x + (self.player.x / CELL_SIZE) * self.scale
            py = self.y + (self.player.y / CELL_SIZE) * self.scale
            Ellipse(pos=(px-2, py-2), size=(4, 4))

# ==================== GAME SCREEN ====================
class Game3D(Widget):
    def __init__(self, grid, wall_types, doors, **kwargs):
        super().__init__(**kwargs)
        self.grid = grid
        self.wall_types = wall_types
        self.doors = doors
        self.player = Player(CELL_SIZE * 1.5, CELL_SIZE * 1.5)
        self.raycaster = Raycaster()
        Clock.schedule_interval(self.render, 1/20)

    def render(self, dt):
        self.canvas.clear()
        w, h = self.width, self.height
        with self.canvas:
            Color(*CEILING)
            Rectangle(pos=(self.x, self.y + h/2), size=(w, h/2))
            Color(*FLOOR)
            Rectangle(pos=(self.x, self.y), size=(w, h/2))
        walls = self.raycaster.cast(self.player, self.grid, self.wall_types, self.doors, w, h)
        with self.canvas:
            for wall in walls:
                x = self.x + wall['x']
                y = self.y + (h - wall['h']) / 2
                Color(*wall['color'])
                Rectangle(pos=(x, y), size=(wall['w'], wall['h']))
                if wall.get('is_door'):
                    Color(0.3, 0.25, 0.2, 0.5)
                    Line(rectangle=(x, y, wall['w'], wall['h']), width=1)
        mx = int(self.player.x / CELL_SIZE)
        my = int(self.player.y / CELL_SIZE)
        if 0 <= my < len(self.grid) and 0 <= mx < len(self.grid[0]):
            if self.grid[my][mx] == 2:
                self.player.won = True

    def move_forward(self): self.player.move(1, self.grid)
    def move_backward(self): self.player.move(-1, self.grid)
    def turn_left(self): self.player.rotate(-1)
    def turn_right(self): self.player.rotate(1)

# ==================== TOUCH BUTTON ====================
class TouchButton(Button):
    def __init__(self, action_name, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.action_name = action_name
        self.app_ref = app_ref
        self.base_color = kwargs.get('background_color', (0.55, 0.5, 0.35, 1))
        self.active_color = (0.85, 0.8, 0.55, 1)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.background_color = self.active_color
            if self.action_name == 'fwd': self.app_ref.fwd = True
            elif self.action_name == 'bwd': self.app_ref.bwd = True
            elif self.action_name == 'tl': self.app_ref.tl = True
            elif self.action_name == 'tr': self.app_ref.tr = True
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        self.background_color = self.base_color
        if self.action_name == 'fwd': self.app_ref.fwd = False
        elif self.action_name == 'bwd': self.app_ref.bwd = False
        elif self.action_name == 'tl': self.app_ref.tl = False
        elif self.action_name == 'tr': self.app_ref.tr = False
        return super().on_touch_up(touch)

    def on_touch_move(self, touch):
        if not self.collide_point(*touch.pos):
            self.background_color = self.base_color
            if self.action_name == 'fwd': self.app_ref.fwd = False
            elif self.action_name == 'bwd': self.app_ref.bwd = False
            elif self.action_name == 'tl': self.app_ref.tl = False
            elif self.action_name == 'tr': self.app_ref.tr = False
        return super().on_touch_move(touch)

# ==================== MAIN APP ====================
class BackroomsApp(App):
    def build(self):
        Window.clearcolor = (0.05, 0.05, 0.02)
        self.grid, self.wall_types, self.doors = generate_maze(MAP_SIZE)
        self.build_ui()
        return self.root

    def build_ui(self):
        self.root = FloatLayout()
        self.showing_menu = True
        self.build_menu()

    def build_menu(self):
        self.root.clear_widgets()
        menu = FloatLayout()
        with menu.canvas.before:
            Color(0.05, 0.05, 0.02)
            self.menu_bg = Rectangle(pos=menu.pos, size=menu.size)
        menu.bind(pos=self.update_menu_bg, size=self.update_menu_bg)

        title = Label(text='THE BACKROOMS', font_size=dp(36), color=(0.75, 0.7, 0.45, 1), bold=True,
                      pos_hint={'center_x': 0.5, 'top': 0.85}, size_hint=(1, 0.15))
        subtitle = Label(text="If you're not careful and noclip out of reality...", font_size=dp(12),
                         color=(0.5, 0.5, 0.4, 1), pos_hint={'center_x': 0.5, 'top': 0.7}, size_hint=(1, 0.08))

        noise = Widget(size_hint=(1, 0.25), pos_hint={'center_x': 0.5, 'top': 0.6})
        with noise.canvas:
            for _ in range(100):
                x, y = random.randint(0, 800), random.randint(0, 150)
                c = random.choice([(0.6,0.6,0.5), (0.4,0.4,0.3)])
                Color(*c, random.uniform(0.1, 0.3))
                Rectangle(pos=(x, y), size=(random.randint(2,5), random.randint(1,2)))
        menu.add_widget(noise)

        btn_new = Button(text='▶  NEW GAME', font_size=dp(20), background_color=(0.6, 0.55, 0.35, 1),
                         background_normal='', size_hint=(0.6, 0.12), pos_hint={'center_x': 0.5, 'top': 0.35})
        btn_new.bind(on_press=self.start_game)

        help_label = Label(text='👆 Sentuh D-Pad untuk gerak & putar  |  🏁 Cari pintu EXIT', font_size=dp(12),
                           color=(0.55, 0.5, 0.4, 1), pos_hint={'center_x': 0.5, 'top': 0.15}, size_hint=(1, 0.1))

        menu.add_widget(title)
        menu.add_widget(subtitle)
        menu.add_widget(btn_new)
        menu.add_widget(help_label)
        self.root.add_widget(menu)
        self.showing_menu = True

    def update_menu_bg(self, *args):
        self.menu_bg.pos = self.root.pos
        self.menu_bg.size = self.root.size

    def start_game(self, instance):
        self.showing_menu = False
        self.root.clear_widgets()

        # ===== GAME FULL SCREEN 100% =====
        self.game = Game3D(self.grid, self.wall_types, self.doors, size_hint=(1, 1), pos_hint={'x': 0, 'y': 0})
        self.root.add_widget(self.game)

        # ===== PETA (kanan atas) =====
        self.peta = Peta(self.game.player, self.grid, size_hint=(None, None),
                         size=(MAP_SIZE * 4, MAP_SIZE * 4), pos_hint={'right': 0.98, 'top': 0.98})
        self.root.add_widget(self.peta)

        # ===== CONTROLS OVERLAY (bawah, transparan) =====
        controls = FloatLayout(size_hint=(1, 0.25), pos_hint={'x': 0, 'y': 0})

        # D-Pad
        dpad = FloatLayout(size_hint=(0.45, 0.9), pos_hint={'center_x': 0.22, 'center_y': 0.5})
        bs = 0.30

        self.btn_up = TouchButton('fwd', self, text='▲', font_size=dp(26),
                                  background_color=(0.55, 0.5, 0.35, 0.85), background_normal='',
                                  size_hint=(bs, bs), pos_hint={'center_x': 0.5, 'top': 1})
        self.btn_down = TouchButton('bwd', self, text='▼', font_size=dp(26),
                                    background_color=(0.55, 0.5, 0.35, 0.85), background_normal='',
                                    size_hint=(bs, bs), pos_hint={'center_x': 0.5, 'y': 0})
        self.btn_left = TouchButton('tl', self, text='↺', font_size=dp(26),
                                    background_color=(0.55, 0.5, 0.35, 0.85), background_normal='',
                                    size_hint=(bs, bs), pos_hint={'x': 0, 'center_y': 0.5})
        self.btn_right = TouchButton('tr', self, text='↻', font_size=dp(26),
                                     background_color=(0.55, 0.5, 0.35, 0.85), background_normal='',
                                     size_hint=(bs, bs), pos_hint={'right': 1, 'center_y': 0.5})

        dpad.add_widget(self.btn_up)
        dpad.add_widget(self.btn_down)
        dpad.add_widget(self.btn_left)
        dpad.add_widget(self.btn_right)

        # Menu button
        btn_menu = Button(text='🏠\nMENU', font_size=dp(13),
                          background_color=(0.45, 0.4, 0.3, 0.85), background_normal='',
                          size_hint=(0.15, 0.55), pos_hint={'center_x': 0.6, 'center_y': 0.5})
        btn_menu.bind(on_press=self.back_to_menu)

        # Status
        self.status_label = Label(text='Cari jalan ke EXIT!', font_size=dp(11),
                                  color=(0.8, 0.75, 0.6, 1),
                                  pos_hint={'center_x': 0.82, 'center_y': 0.5},
                                  size_hint=(0.25, 0.4))

        controls.add_widget(dpad)
        controls.add_widget(btn_menu)
        controls.add_widget(self.status_label)
        self.root.add_widget(controls)

        # Flags
        self.fwd = False
        self.bwd = False
        self.tl = False
        self.tr = False

        # Game loop
        if hasattr(self, 'game_event') and self.game_event:
            Clock.unschedule(self.game_event)
        self.game_event = Clock.schedule_interval(self.game_loop, 1/30)

    def back_to_menu(self, instance):
        if hasattr(self, 'game_event') and self.game_event:
            Clock.unschedule(self.game_event)
            self.game_event = None
        self.grid, self.wall_types, self.doors = generate_maze(MAP_SIZE)
        self.build_menu()

    def game_loop(self, dt):
        if not hasattr(self, 'game') or self.showing_menu:
            return
        if self.fwd: self.game.move_forward()
        if self.bwd: self.game.move_backward()
        if self.tl: self.game.turn_left()
        if self.tr: self.game.turn_right()
        if hasattr(self, 'status_label') and self.game.player.won:
            self.status_label.text = '🎉 KAMU MENEMUKAN EXIT!'
            self.status_label.color = (0.4, 0.9, 0.4, 1)

if __name__ == '__main__':
    BackroomsApp().run()
