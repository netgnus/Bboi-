"""Desktop Pet Cat — a little black cat that lives on your screen.

Pet it by stroking it with the mouse (hearts!), pick it up and drop it,
right-click for a menu. No dependencies — pure tkinter.

Run silently with:  pythonw cat.py   (or double-click CatPet.vbs)
"""

import ctypes
import json
import math
import random
import threading
import time
import tkinter as tk
import urllib.request

# ---------- palette ----------
TRANS   = '#010203'   # transparent color key
BODY    = '#23232b'
BODY_D  = '#18181f'
BODY_L  = '#33333f'
SHADOW  = '#141419'
PINK    = '#f2a0b5'
EYE     = '#a8e05f'
DARK    = '#0d0d11'
LINE    = '#cdd2e0'
WHISKER = '#8d93a8'
HEART   = '#ff6b8a'
ZZZ     = '#aeb8ff'
BUB_BG  = '#f7f7ee'
BUB_TXT = '#26262e'

W, H = 340, 330
GROUND = H - 12
CX = W // 2

TICK = 33  # ms per frame

ADVICE_URL = 'https://api.adviceslip.com/advice'

FALLBACK_ADVICE = [
    "Knock it off the table. You know you want to.",
    "Take a nap. Then take another one.",
    "If it fits, you sits.",
    "Ignore them for hours, then demand attention at 3am.",
    "Stretch before doing absolutely nothing.",
    "The red dot is a lie, but chase it anyway.",
    "Never let them see where you hid the hair tie.",
    "Stare at the wall. It builds mystery.",
    "Drink from the glass, never the bowl.",
    "A closed door is a personal insult. Act accordingly.",
    "Bite the hand that pets you. Gently. Probably.",
    "You miss 100% of the naps you don't take.",
    "Be the chaos you wish to see in the world.",
    "Sit on the keyboard. The email can wait.",
]

MEOWS = ['meow', 'mrrp?', 'prrrr...', 'mew!', 'mrrow', ':3']


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


class Cat(tk.Tk):
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
        self.speed = 2.0
        self.phase = 0.0
        self.vy = 0.0

        self.pet_until = 0.0
        self.last_heart = 0.0
        self.stroke_accum = 0.0
        self.last_mouse = None

        self.blink_until = 0.0
        self.next_blink = now + random.uniform(2, 5)
        self.next_zzz = 0.0
        self.particles = []   # dicts: type, x, y, age

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
        self.menu.add_command(label='Bye 👋', command=self.destroy)

        self.geometry(f'+{int(self.x)}+{int(self.y)}')
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
                self.say('mrrp?')
            if now - self.last_heart > 0.35:
                self.last_heart = now
                self.particles.append({'type': 'heart',
                                       'x': CX + random.uniform(-30, 30),
                                       'y': GROUND - 130,
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
        if roll < 0.42:
            self.state = 'walk'
            self.dir = random.choice((-1, 1))
            self.speed = random.uniform(1.6, 2.6)
            self.state_until = now + random.uniform(3, 7)
        elif roll < 0.62:
            self.state = 'idle'
            self.state_until = now + random.uniform(2, 5)
        elif roll < 0.78:
            self.state = 'chase'
            self.state_until = now + 6
        else:
            self.state = 'sleep'
            self.state_until = now + random.uniform(18, 45)

    def tick(self):
        now = time.time()
        self.phase += 0.28
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
                    self.say(random.choice(MEOWS))
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
                    self.x += self.dir * 3.2
        elif st == 'sleep':
            if now > self.next_zzz:
                self.next_zzz = now + 0.9
                self.particles.append({'type': 'zzz',
                                       'x': CX + self.dir * 38,
                                       'y': GROUND - 68,
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

    def pupil_offset(self):
        px = self.winfo_pointerx() - (self.x + CX)
        py = self.winfo_pointery() - (self.y + GROUND - 100)
        return (clamp(px / 50.0, -3, 3), clamp(py / 80.0, -2, 2))

    def draw_eyes(self, hx, ey, mode, spread=13, size=6):
        c = self.canvas
        pdx, pdy = self.pupil_offset() if mode in ('open', 'wide') else (0, 0)
        grow = 2 if mode == 'wide' else 0
        for sx in (-spread, spread):
            x = hx + sx
            if mode in ('open', 'wide'):
                c.create_oval(x - size - grow, ey - size - 1 - grow,
                              x + size + grow, ey + size + 1 + grow,
                              fill=EYE, outline='')
                pw = 2 if mode == 'open' else 3
                c.create_oval(x - pw + pdx, ey - size + 2 + pdy,
                              x + pw + pdx, ey + size - 2 + pdy,
                              fill=DARK, outline='')
            elif mode == 'happy':
                c.create_arc(x - 7, ey - 5, x + 7, ey + 7,
                             start=30, extent=120, style='arc',
                             outline=LINE, width=3)
            else:  # closed
                c.create_arc(x - 7, ey - 8, x + 7, ey + 4,
                             start=200, extent=140, style='arc',
                             outline=LINE, width=3)

    def draw_muzzle(self, hx, ny, happy):
        c = self.canvas
        c.create_polygon(hx - 4, ny - 2, hx + 4, ny - 2, hx, ny + 4,
                         fill=PINK, outline='')
        if happy:
            c.create_arc(hx - 5, ny + 2, hx + 5, ny + 12,
                         start=180, extent=180, style='chord',
                         fill=PINK, outline='')
        else:
            c.create_arc(hx - 7, ny + 1, hx + 1, ny + 8,
                         start=180, extent=180, style='arc',
                         outline=WHISKER, width=2)
            c.create_arc(hx - 1, ny + 1, hx + 7, ny + 8,
                         start=180, extent=180, style='arc',
                         outline=WHISKER, width=2)

    def draw_whiskers(self, hx, wy):
        c = self.canvas
        for s in (-1, 1):
            c.create_line(hx + s * 28, wy, hx + s * 50, wy - 4,
                          fill=WHISKER, width=1)
            c.create_line(hx + s * 28, wy + 6, hx + s * 50, wy + 8,
                          fill=WHISKER, width=1)

    def draw_sit(self, now, petting):
        c, g, cx, d = self.canvas, GROUND, CX, self.dir
        wag = math.sin(self.phase * 0.5) * 7
        c.create_oval(cx - 42, g - 6, cx + 42, g + 4, fill=SHADOW, outline='')
        # tail
        c.create_line(cx + d * 26, g - 20, cx + d * 46, g - 8,
                      cx + d * 56, g - 30 + wag,
                      smooth=True, width=11, capstyle='round', fill=BODY)
        # body + head
        c.create_oval(cx - 36, g - 72, cx + 36, g, fill=BODY, outline='')
        hy = g - 100
        # ears
        c.create_polygon(cx - 30, hy - 10, cx - 26, hy - 42, cx - 6, hy - 24,
                         fill=BODY, outline='')
        c.create_polygon(cx + 30, hy - 10, cx + 26, hy - 42, cx + 6, hy - 24,
                         fill=BODY, outline='')
        c.create_polygon(cx - 25, hy - 16, cx - 23, hy - 34, cx - 12, hy - 23,
                         fill=PINK, outline='')
        c.create_polygon(cx + 25, hy - 16, cx + 23, hy - 34, cx + 12, hy - 23,
                         fill=PINK, outline='')
        c.create_oval(cx - 33, hy - 30, cx + 33, hy + 32, fill=BODY, outline='')
        # face
        self.draw_eyes(cx, hy - 2, self.eye_mode(now, petting))
        self.draw_muzzle(cx, hy + 12, petting)
        self.draw_whiskers(cx, hy + 8)
        # front paws
        c.create_oval(cx - 22, g - 13, cx - 2, g + 1, fill=BODY_L, outline='')
        c.create_oval(cx + 2, g - 13, cx + 22, g + 1, fill=BODY_L, outline='')

    def draw_walk(self, now, petting):
        c, g, cx, d = self.canvas, GROUND, CX, self.dir
        bob = math.sin(self.phase) * 2.5
        c.create_oval(cx - 46, g - 6, cx + 46, g + 4, fill=SHADOW, outline='')
        # tail
        tx = cx - d * 36
        c.create_line(tx, g - 44 + bob, tx - d * 12, g - 60 + bob,
                      tx - d * 16, g - 80 + bob + math.sin(self.phase * 0.7) * 5,
                      smooth=True, width=9, capstyle='round', fill=BODY)
        # far legs
        for hip, ph in ((cx + d * 18, math.pi), (cx - d * 22, 0)):
            fx = hip + d * math.sin(self.phase + ph) * 13
            c.create_line(hip, g - 30 + bob, fx, g - 2,
                          width=9, capstyle='round', fill=BODY_D)
        # body
        c.create_oval(cx - 44, g - 60 + bob, cx + 34, g - 18 + bob,
                      fill=BODY, outline='')
        # near legs
        for hip, ph in ((cx + d * 18, 0), (cx - d * 22, math.pi)):
            fx = hip + d * math.sin(self.phase + ph) * 13
            c.create_line(hip, g - 30 + bob, fx, g - 2,
                          width=9, capstyle='round', fill=BODY)
        # head
        hx, hy = cx + d * 36, g - 72 + bob
        c.create_polygon(hx - d * 20, hy - 12, hx - d * 13, hy - 38,
                         hx - d * 1, hy - 20, fill=BODY, outline='')
        c.create_polygon(hx + d * 4, hy - 20, hx + d * 13, hy - 38,
                         hx + d * 21, hy - 10, fill=BODY, outline='')
        c.create_oval(hx - 24, hy - 24, hx + 24, hy + 24, fill=BODY, outline='')
        self.draw_eyes(hx + d * 4, hy - 4,
                       self.eye_mode(now, petting), spread=10, size=5)
        # nose + whiskers at the front
        nx = hx + d * 4
        self.draw_muzzle(nx, hy + 8, petting)
        self.draw_whiskers(nx, hy + 5)

    def draw_sleep(self):
        c, g, cx, d = self.canvas, GROUND, CX, self.dir
        breathe = math.sin(self.phase * 0.25) * 2
        c.create_oval(cx - 50, g - 6, cx + 50, g + 4, fill=SHADOW, outline='')
        c.create_oval(cx - 46, g - 44 - breathe, cx + 46, g,
                      fill=BODY, outline='')
        c.create_line(cx - d * 44, g - 12, cx - d * 8, g - 4,
                      cx + d * 26, g - 8,
                      smooth=True, width=9, capstyle='round', fill=BODY_L)
        hx, hy = cx + d * 18, g - 36
        c.create_polygon(hx - 20, hy - 14, hx - 15, hy - 32, hx - 2, hy - 18,
                         fill=BODY, outline='')
        c.create_polygon(hx + 20, hy - 14, hx + 15, hy - 32, hx + 2, hy - 18,
                         fill=BODY, outline='')
        c.create_oval(hx - 24, hy - 20, hx + 24, hy + 26, fill=BODY, outline='')
        for sx in (-11, 11):
            c.create_arc(hx + sx - 6, hy - 8, hx + sx + 6, hy + 4,
                         start=200, extent=140, style='arc',
                         outline=LINE, width=2)
        c.create_polygon(hx - 3, hy + 8, hx + 3, hy + 8, hx, hy + 13,
                         fill=PINK, outline='')

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
        by = GROUND - 176  # bubble bottom edge (just above the ears)
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
            self.draw_sleep()
        elif self.state in ('walk', 'chase') and not petting:
            self.draw_walk(now, petting)
        else:
            self.draw_sit(now, petting)
        self.draw_particles()
        self.draw_bubble(now)


if __name__ == '__main__':
    Cat().mainloop()
