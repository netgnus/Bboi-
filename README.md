# Desktop Pets 🐈‍⬛🧸

Little companions that live on your screen. Pure Python/tkinter — no dependencies.

- **Cat** — double-click `CatPet.vbs`
- **bboy** the teddy — double-click `BearPet.vbs` (drawn from a photo of the real bear: cream fur, teal hoodie, white vest). He waddles front-facing with a rock-and-sway walk, sits with his legs splayed just like the real one, introduces himself on launch, and gives noticeably warmer advice when offline. Size is the `SCALE` constant at the top of `bear.py`.

They can run at the same time. Everything below applies to both.

## What it does

- Wanders along the bottom of your screen, sits, and watches your cursor (its eyes follow the mouse)
- Sometimes runs over to your cursor
- **Pet it**: stroke it with the mouse — happy face + hearts
- **Carry it**: click and drag it anywhere; drop it and it falls back to the ground
- Falls asleep on its own (Zzz…); petting wakes it up (it goes "mrrp?")
- **Chat with bboy** (bear only): click him → a text box opens → he replies in his speech bubble. Uses the Claude Code CLI as his brain if installed (`npm install -g @anthropic-ai/claude-code`, then log in once with `claude`); without it he gives cozy brainless replies.
- **Timers** (bear only): right-click → Timer, or type `timer 10m tea` in chat. Formats: `10`, `10m`, `90s`, `1h30m`, optional label. When it's up he bounces, beeps, and yells — click him to shush. Right-click shows time remaining.
- **Gives advice** in speech bubbles — real advice from [adviceslip.com](https://api.adviceslip.com) when online, unhinged cat wisdom when offline. It speaks up on its own every few minutes, or ask via the menu. Occasionally it just meows.
- **Right-click** for the menu: Advice / Nap time / Wake up / Bye

## Start with Windows (optional)

1. Press `Win+R`, type `shell:startup`, press Enter
2. Right-click drag `CatPet.vbs` into that folder → "Create shortcut here"
