You are steering an original Xbox game from boot into gameplay with a gamepad. Title: {title}.
Look at the screenshot {frame}. Decide which screen this is and the next pad input.

Answer with ONE line of JSON and nothing else:
{"state": "<state>", "why": "<one line: what you see>", "action": "<input>", "wait_s": <seconds>}

state is exactly one of:
- intro_video: a pre-rendered movie or attract-mode demo before the title screen. An attract demo can look
  like play, but shows a logo watermark, "PRESS START", or nobody is steering.
- publisher_logo: a studio/publisher logo, or a legal / copyright / federal warning text screen.
- title_screen: the game logo with "Press START", or the first menu shown on top of the logo.
- main_menu: the game's top menu (New Game / Single Player / Options ...).
- submenu: any deeper menu: mode, stage, level, character, car or mission select, options, a status or
  inventory screen, a help/controls page.
- profile_creation: create / select a player profile or save slot, sign-in, without an on-screen keyboard.
- name_entry: an on-screen keyboard or letter grid for typing a name.
- save_load_prompt: a dialog about saving or loading (Yes/No, "no saved games found", "continue without saving").
- controller_prompt: "press A on the controller you will use", controller assignment, "controller disconnected".
- loading: a loading screen, bar, spinner or "Now Loading" card.
- cutscene: an in-game story scene the player does not control (letterbox bars, subtitles, dialogue boxes).
- pause: a menu over a paused game (Resume / Continue / Restart / Quit).
- gameplay: the player is controlling a character, vehicle or cursor in the game world RIGHT NOW. Usually a
  HUD (health, score, timer, speed, minimap). NOT gameplay if a menu, PAUSE box, keyboard, dialog, "Round"
  or "Winner" banner, or "PRESS START" is drawn over the scene.
- results: the end of a round / race / match: a winner, "PERFECT", "K.O.", standings or a score tally.
- game_over: game over, time up, mission failed, continue? countdown.
- black: the screen is black or nearly black.
- unknown: none of these, the emulator is not showing a game (an Android home screen), or the image is garbage.

The small "FPS: NN" text in the top-left corner is drawn by the emulator on every frame. It is not the
game's HUD and says nothing about the state. A scene with no game HUD, no menu and nobody visibly steering
right after boot is usually an intro_video (attract demo), not gameplay.

action is one pad input or a short comma-separated sequence: A, B, X, Y, START, BACK, LT, RT,
DPAD_UP, DPAD_DOWN, DPAD_LEFT, DPAD_RIGHT, LSTICK_UP, LSTICK_DOWN, LSTICK_LEFT, LSTICK_RIGHT; or "wait".
Pick the input that gets into play fastest with default settings. wait_s is how long to wait before the next
screenshot (1-30).
