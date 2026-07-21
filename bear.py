"""Desktop Pet Teddy — a fluffy teddy bear in a teal hoodie, on your screen.

Modeled on a real bear: cream fur, dusty-teal hoodie, white vest,
brown stitched nose. Pet him, carry him, let him give you soft advice.

Run silently with:  pythonw bear.py   (or double-click BearPet.vbs)
"""

import ctypes
import json
import math
import random
import threading
import time
import tkinter as tk
import urllib.request

# ---------- palette (from the photo) ----------
TRANS   = '#010203'
FUR     = '#e6e0d0'
FUR_D   = '#d5cdb8'
FUR_L   = '#efe9db'
PAD     = '#e9e2d2'
HOODIE  = '#5d8290'
HOODIE_D = '#4c6d79'
VEST    = '#f0ebdd'
NOSE    = '#7d5236'
STITCH  = '#6d4530'
EYE     = '#1c1a17'
GLINT   = '#f5f2ea'
LINE    = '#8a8272'
SHADOW  = '#141419'
HEART   = '#ff6b8a'
ZZZ     = '#aeb8ff'
BUB_BG  = '#f7f7ee'
BUB_TXT = '#26262e'

W, H = 360, 400
GROUND = H - 12
CX = W // 2
SCALE = 0.5   # overall bear size (1.0 = original)
NAME = 'bboy'

TICK = 33  # ms per frame

ADVICE_URL = 'https://api.adviceslip.com/advice'

FALLBACK_ADVICE = [
    "Hugs fix more than you'd think.",
    "Drink some water, little one.",
    "You're doing better than you think.",
    "Naps are self-care, not laziness.",
    "Be soft. The world has enough sharp edges.",
    "A snack now and then is good for the soul.",
    "It's okay to take today slowly.",
    "Someone is glad you exist. (It's me.)",
    "Stretch your paws every hour or so.",
    "You survived every bad day so far. Full marks.",
    "Warm blankets solve 80% of problems.",
    "Ask for help. Even bears do.",
    "Being loved threadbare is the best kind of worn out.",
]

SOUNDS = ['*happy bear noises*', 'rawr! (friendly)', '*offers hug*',
          '*boop*', 'grumble grumble', '🧡', 'bboy!']


def work_area():
    """Primary monitor work area (excludes taskbar)."""
    class RECT(ctypes.Structure):
        _fields_ = [('l', ctypes.c_long), ('t', ctypes.c_long),
                    ('r', ctypes.c_long), ('b', ctypes.c_long)]
    r = RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)
    return r.l, r.t, r.r, r.b


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class Bear(tk.Tk):
    def __init__(self):
        super().__init__()
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-transparentcolor', TRANS)

        self.canvas = tk.Canvas(self, width=W, height=H, bg=TRANS,
                                highlightthickness=0)
        self.canvas.pack()

        l, t, r, b = work_area()
        self.min_x, self.max_x = float(l), float(r - W)
        self.floor = float(b - H)

        self.x = float(random.randint(int(self.min_x) + 100,
                                      max(int(self.min_x) + 101, int(self.max_x) - 100)))
        self.y = self.floor

        now = time.time()
        self.state = 'idle'
        self.state_until = now + random.uniform(2, 4)
        self.dir = random.choice((-1, 1))
        self.speed = 1.6
        self.phase = 0.0
        self.vy = 0.0

        self.pet_until = 0.0
        self.last_heart = 0.0
        self.stroke_accum = 0.0
        self.last_mouse = None

        self.blink_until = 0.0
        self.next_blink = now + random.uniform(2, 5)
        self.next_zzz = 0.0
        self.particles = []

        self.press_pos = None
        self.grab_dx = self.grab_dy = 0

        self.bubble_text = None
        self.bubble_until = 0.0
        self.next_bubble = now + random.uniform(15, 40)
        self._pending_advice = None

        c = self.canvas
        c.bind('<Motion>', self.on_motion)
        c.bind('<Button-1>', self.on_press)
        c.bind('<B1-Motion>', self.on_drag)
        c.bind('<ButtonRelease-1>', self.on_release)
        c.bind('<Button-3>', self.on_menu)

        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label='Advice 🔮', command=self.request_advice)
        self.menu.add_command(label='Nap time 💤', command=self.force_nap)
        self.menu.add_command(label='Wake up ☀️', command=self.force_wake)
        self.menu.add_separator()
        self.menu.add_command(label=f'Bye {NAME} 🧸', command=self.destroy)

        self.geometry(f'+{int(self.x)}+{int(self.y)}')
        self.say(f"hi, i'm {NAME} :3")
        self.after(TICK, self.tick)

    # ---------- interaction ----------
    def on_motion(self, e):
        if self.state == 'held':
            return
        if self.last_mouse is not None:
            self.stroke_accum += math.hypot(e.x - self.last_mouse[0],
                                            e.y - self.last_mouse[1])
        self.last_mouse = (e.x, e.y)
        if self.stroke_accum > 22:
            self.stroke_accum = 0.0
            now = time.time()
            self.pet_until = now + 1.0
            if self.state == 'sleep':
                self.state = 'idle'
                self.state_until = now + 3
                self.say('*sleepy bear noises*')
            if now - self.last_heart > 0.35:
                self.last_heart = now
                self.particles.append({'type': 'heart',
                                       'x': CX + random.uniform(-35, 35),
                                       'y': GROUND - 240,
                                       'age': 0.0})

    def on_press(self, e):
        self.press_pos = (e.x_root, e.y_root)
        self.grab_dx = e.x_root - self.x
        self.grab_dy = e.y_root - self.y

    def on_drag(self, e):
        if self.press_pos is None:
            return
        if self.state != 'held':
            if math.hypot(e.x_root - self.press_pos[0],
                          e.y_root - self.press_pos[1]) < 8:
                return
            self.state = 'held'
        self.x = clamp(e.x_root - self.grab_dx, self.min_x, self.max_x)
        self.y = clamp(e.y_root - self.grab_dy, 0, self.floor)

    def on_release(self, e):
        self.press_pos = None
        if self.state == 'held':
            if self.y < self.floor - 4:
                self.state = 'fall'
                self.vy = 0.0
            else:
                self.state = 'idle'
                self.state_until = time.time() + random.uniform(2, 4)

    def on_menu(self, e):
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

    def force_nap(self):
        self.state = 'sleep'
        self.state_until = time.time() + random.uniform(40, 90)

    def force_wake(self):
        self.state = 'idle'
        self.state_until = time.time() + random.uniform(2, 4)

    # ---------- advice / speech ----------
    def request_advice(self):
        threading.Thread(target=self._fetch_advice, daemon=True).start()

    def _fetch_advice(self):
        try:
            with urllib.request.urlopen(ADVICE_URL, timeout=4) as r:
                text = json.load(r)['slip']['advice']
        except Exception:
            text = random.choice(FALLBACK_ADVICE)
        self._pending_advice = text

    def say(self, text):
        self.bubble_text = text
        self.bubble_until = time.time() + min(9.0, 3.0 + len(text) * 0.06)
        if self.state == 'sleep':
            self.force_wake()

    # ---------- behavior ----------
    def pick_next(self, now):
        roll = random.random()
        if roll < 0.38:
            self.state = 'walk'
            self.dir = random.choice((-1, 1))
            self.speed = random.uniform(1.1, 1.9)   # bears waddle, slowly
            self.state_until = now + random.uniform(3, 7)
        elif roll < 0.62:
            self.state = 'idle'
            self.state_until = now + random.uniform(3, 6)
        elif roll < 0.76:
            self.state = 'chase'
            self.state_until = now + 7
        else:
            self.state = 'sleep'
            self.state_until = now + random.uniform(20, 50)

    def tick(self):
        now = time.time()
        self.phase += 0.22
        petting = now < self.pet_until

        if now > self.next_blink:
            self.blink_until = now + 0.13
            self.next_blink = now + random.uniform(2.5, 6)

        # speech
        if self._pending_advice is not None:
            self.say(self._pending_advice)
            self._pending_advice = None
        if now > self.next_bubble:
            self.next_bubble = now + random.uniform(90, 240)
            if self.state not in ('sleep', 'held'):
                if random.random() < 0.35:
                    self.say(random.choice(SOUNDS))
                else:
                    self.request_advice()

        st = self.state
        if st == 'idle':
            if not petting and now > self.state_until:
                self.pick_next(now)
        elif st == 'walk':
            if not petting:
                self.x += self.dir * self.speed
                if self.x <= self.min_x or self.x >= self.max_x:
                    self.x = clamp(self.x, self.min_x, self.max_x)
                    self.dir *= -1
                if now > self.state_until:
                    self.state = 'idle'
                    self.state_until = now + random.uniform(2, 5)
        elif st == 'chase':
            if not petting:
                target = clamp(self.winfo_pointerx() - W / 2,
                               self.min_x, self.max_x)
                dx = target - self.x
                if abs(dx) < 24 or now > self.state_until:
                    self.state = 'idle'
                    self.state_until = now + random.uniform(2, 5)
                else:
                    self.dir = 1 if dx > 0 else -1
                    self.x += self.dir * 2.4
        elif st == 'sleep':
            if now > self.next_zzz:
                self.next_zzz = now + 0.9
                self.particles.append({'type': 'zzz',
                                       'x': CX + self.dir * 48,
                                       'y': GROUND - 200,
                                       'age': 0.0})
            if now > self.state_until:
                self.state = 'idle'
                self.state_until = now + random.uniform(2, 4)
        elif st == 'fall':
            self.vy += 2.4
            self.y += self.vy
            if self.y >= self.floor:
                self.y = self.floor
                self.state = 'idle'
                self.state_until = now + random.uniform(2, 4)

        # particles
        dt = TICK / 1000.0
        for p in self.particles:
            p['age'] += dt
            if p['type'] == 'heart':
                p['y'] -= 55 * dt
            else:
                p['y'] -= 30 * dt
                p['x'] += self.dir * 18 * dt
        self.particles = [p for p in self.particles if p['age'] < 1.3]

        self.redraw(now, petting)
        self.geometry(f'+{int(self.x)}+{int(self.y)}')
        self.after(TICK, self.tick)

    # ---------- drawing ----------
    def eye_mode(self, now, petting):
        if self.state == 'sleep':
            return 'closed'
        if petting:
            return 'happy'
        if self.state in ('held', 'fall'):
            return 'wide'
        if now < self.blink_until:
            return 'closed'
        return 'open'

    def pupil_offset(self, hy):
        px = self.winfo_pointerx() - (self.x + CX)
        py = self.winfo_pointery() - (self.y + hy)
        return (clamp(px / 60.0, -3, 3), clamp(py / 90.0, -2, 2))

    def draw_eyes(self, hx, ey, mode, spread=24):
        c = self.canvas
        pdx, pdy = self.pupil_offset(ey) if mode in ('open', 'wide') else (0, 0)
        grow = 1.5 if mode == 'wide' else 0
        for sx in (-spread, spread):
            x = hx + sx
            if mode in ('open', 'wide'):
                c.create_oval(x - 5 - grow + pdx, ey - 5 - grow + pdy,
                              x + 5 + grow + pdx, ey + 5 + grow + pdy,
                              fill=EYE, outline='')
                c.create_oval(x - 1 + pdx, ey - 3 + pdy,
                              x + 2 + pdx, ey + pdy,
                              fill=GLINT, outline='')
            elif mode == 'happy':
                c.create_arc(x - 7, ey - 5, x + 7, ey + 7,
                             start=30, extent=120, style='arc',
                             outline=EYE, width=3)
            else:  # closed
                c.create_arc(x - 7, ey - 8, x + 7, ey + 4,
                             start=200, extent=140, style='arc',
                             outline=EYE, width=2)

    def draw_head(self, hx, hy, now, petting, droop=0):
        """Head centered at (hx, hy). droop lowers it for sleeping."""
        c = self.canvas
        hy += droop
        # ears (behind head)
        for sx in (-1, 1):
            c.create_oval(hx + sx * 56 - 20, hy - 62, hx + sx * 56 + 20, hy - 22,
                          fill=FUR, outline='')
            c.create_oval(hx + sx * 54 - 11, hy - 52, hx + sx * 54 + 11, hy - 30,
                          fill=FUR_D, outline='')
        # head
        c.create_oval(hx - 56, hy - 56, hx + 56, hy + 56, fill=FUR, outline='')
        # muzzle
        c.create_oval(hx - 24, hy + 8, hx + 24, hy + 50, fill=FUR_L, outline='')
        # nose + mouth stitches
        c.create_polygon(hx - 9, hy + 16, hx + 9, hy + 16, hx, hy + 30,
                         fill=NOSE, outline='')
        c.create_line(hx, hy + 30, hx, hy + 37, fill=STITCH, width=2)
        c.create_arc(hx - 12, hy + 30, hx, hy + 44,
                     start=180, extent=180, style='arc',
                     outline=STITCH, width=2)
        c.create_arc(hx, hy + 30, hx + 12, hy + 44,
                     start=180, extent=180, style='arc',
                     outline=STITCH, width=2)
        # eyes
        self.draw_eyes(hx, hy - 10, self.eye_mode(now, petting))

    def draw_sit(self, now, petting, droop=0):
        """Sitting like the photo: legs splayed forward, arms at sides."""
        c, g, cx = self.canvas, GROUND, CX
        breathe = math.sin(self.phase * 0.35) * 2
        c.create_oval(cx - 72, g - 8, cx + 72, g + 4, fill=SHADOW, outline='')
        # legs splayed forward
        for sx in (-1, 1):
            c.create_oval(cx + sx * 72 - 34, g - 50, cx + sx * 72 + 8, g,
                          fill=FUR, outline='')
            c.create_oval(cx + sx * 62 - 18, g - 38, cx + sx * 62 + 14, g - 6,
                          fill=PAD, outline='')
        # body: hoodie
        c.create_oval(cx - 52, g - 132 - breathe, cx + 52, g - 18,
                      fill=HOODIE, outline='')
        # hood bunched at the shoulders
        c.create_oval(cx - 44, g - 146 - breathe, cx + 44, g - 104,
                      fill=HOODIE_D, outline='')
        # white vest front
        c.create_oval(cx - 30, g - 124 - breathe, cx + 30, g - 30,
                      fill=VEST, outline='')
        # zipper hint
        c.create_line(cx, g - 128 - breathe, cx, g - 112, fill=HOODIE_D, width=2)
        # arms: teal sleeves ending in fur paws
        for sx in (-1, 1):
            c.create_oval(cx + sx * 56 - 16, g - 116, cx + sx * 56 + 16, g - 56,
                          fill=HOODIE, outline='')
            c.create_oval(cx + sx * 58 - 14, g - 72, cx + sx * 58 + 14, g - 42,
                          fill=FUR, outline='')
        # head sits on the body
        self.draw_head(cx, g - 188 - breathe, now, petting, droop)

    def draw_walk(self, now, petting):
        """Front-facing waddle: rocks side to side, feet alternate."""
        c, g, cx = self.canvas, GROUND, CX
        rock = math.sin(self.phase)
        sway = rock * 7
        c.create_oval(cx - 60, g - 8, cx + 60, g + 4, fill=SHADOW, outline='')
        # feet (alternating lift)
        for sx, ph in ((-1, 0), (1, math.pi)):
            lift = max(0.0, math.sin(self.phase + ph)) * 7
            c.create_oval(cx + sx * 30 - 22, g - 40 - lift,
                          cx + sx * 30 + 22, g - lift + 2,
                          fill=FUR, outline='')
            c.create_oval(cx + sx * 30 - 13, g - 30 - lift,
                          cx + sx * 30 + 13, g - 6 - lift,
                          fill=PAD, outline='')
        # body
        c.create_oval(cx - 48 + sway * 0.4, g - 168, cx + 48 + sway * 0.4, g - 26,
                      fill=HOODIE, outline='')
        c.create_oval(cx - 40 + sway * 0.5, g - 180, cx + 40 + sway * 0.5, g - 140,
                      fill=HOODIE_D, outline='')
        c.create_oval(cx - 27 + sway * 0.4, g - 160, cx + 27 + sway * 0.4, g - 42,
                      fill=VEST, outline='')
        # arms swing
        for sx in (-1, 1):
            swing = math.sin(self.phase + (0 if sx < 0 else math.pi)) * 5
            c.create_oval(cx + sx * 52 - 15 + sway * 0.5, g - 150 + swing,
                          cx + sx * 52 + 15 + sway * 0.5, g - 92 + swing,
                          fill=HOODIE, outline='')
            c.create_oval(cx + sx * 54 - 13 + sway * 0.5, g - 108 + swing,
                          cx + sx * 54 + 13 + sway * 0.5, g - 80 + swing,
                          fill=FUR, outline='')
        # head rocks a little more than the body
        self.draw_head(cx + sway, g - 232, now, petting)

    def draw_particles(self):
        c = self.canvas
        for p in self.particles:
            fade = 1.0 - p['age'] / 1.3
            if p['type'] == 'heart':
                size = max(6, int(16 * fade))
                c.create_text(p['x'], p['y'], text='♥', fill=HEART,
                              font=('Segoe UI', size, 'bold'))
            else:
                size = max(7, int(9 + p['age'] * 7))
                c.create_text(p['x'], p['y'], text='z', fill=ZZZ,
                              font=('Segoe UI', size, 'bold'))

    def draw_bubble(self, now):
        if not self.bubble_text or now > self.bubble_until:
            return
        c = self.canvas
        by = GROUND - int(262 * SCALE) - 8
        txt = c.create_text(CX, by - 12, text=self.bubble_text,
                            width=W - 60, anchor='s', justify='center',
                            fill=BUB_TXT, font=('Segoe UI', 10))
        x0, y0, x1, y1 = c.bbox(txt)
        x0, y0, x1, y1 = x0 - 12, y0 - 9, x1 + 12, y1 + 9
        r = 12
        rect = c.create_polygon(
            x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r,
            x1, y1 - r, x1, y1, x1 - r, y1, x0 + r, y1,
            x0, y1, x0, y1 - r, x0, y0 + r, x0, y0,
            smooth=True, fill=BUB_BG, outline='#c9c9bd')
        tail = c.create_polygon(CX - 8, y1 - 2, CX + 12, y1 - 2,
                                CX + self.dir * 6, y1 + 14,
                                fill=BUB_BG, outline='')
        c.tag_raise(rect)
        c.tag_raise(tail)
        c.tag_raise(txt)

    def redraw(self, now, petting):
        self.canvas.delete('all')
        if self.state == 'sleep':
            self.draw_sit(now, petting, droop=14)
        elif self.state in ('walk', 'chase') and not petting:
            self.draw_walk(now, petting)
        else:
            self.draw_sit(now, petting)
        self.draw_particles()
        # shrink the whole bear around his feet, then speak at full size
        self.canvas.scale('all', CX, GROUND, SCALE, SCALE)
        self.draw_bubble(now)


if __name__ == '__main__':
    Bear().mainloop()
