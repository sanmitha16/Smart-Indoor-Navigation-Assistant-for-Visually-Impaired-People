"""How the user starts the two modes.

On the Pi: two push buttons (optional, you can use voice only).
    left  button  (GPIO 17)  Reading mode
    right button  (GPIO 27)  Object mode
    Press  = start the mode (the action runs when the button is let go)
    Hold for 1.5 seconds = repeat the last answer
    Press while the device is speaking = stop speaking (handled in app.py)

On the laptop (or any time you type in the terminal):
    r            Reading mode
    o            Object mode          o keys   (or: find keys)   looks for keys
    x            repeat the last answer
    s            stop talking / stop a search
    q            quit

Test the wiring on its own:  python inputs.py
"""
PINS = {"read": 17, "object": 27}      # BCM numbers
HOLD_SECONDS = 1.5


def _make_callbacks(name, handlers):
    """Two zero-argument functions for one button. Kept argument-free on purpose: gpiozero may pass the
    button itself to a callback that accepts an argument."""
    held = {"yes": False}

    def on_held():
        held["yes"] = True
        handlers["repeat"]()

    def on_released():
        if held["yes"]:
            held["yes"] = False         # this release ends a long press, do not start the mode
            return
        handlers[name]()

    return on_held, on_released


def setup_gpio(handlers):
    """Use the real buttons on the Pi. Returns None on a laptop (no GPIO), so the keyboard is used."""
    try:
        from gpiozero import Button
        buttons = {n: Button(p, pull_up=True, bounce_time=0.05, hold_time=HOLD_SECONDS) for n, p in PINS.items()}
    except Exception as e:
        print("GPIO not available, using keyboard:", e)
        return None
    for name, b in buttons.items():
        b.when_held, b.when_released = _make_callbacks(name, handlers)
    return buttons


def keyboard_loop(handlers):
    aliases = {"read": "r", "object": "o", "find": "o", "repeat": "x", "stop": "s", "quit": "q"}
    print("r = read    o = object (o keys = look for keys)    x = repeat    s = stop    q = quit")
    while True:
        try:
            line = input("> ").strip()
        except EOFError:                 # no terminal (for example when started automatically at boot)
            break
        cmd, _, rest = line.partition(" ")
        cmd = aliases.get(cmd.lower(), cmd.lower())
        rest = rest.strip()
        if cmd == "q":
            break
        elif cmd == "r":
            handlers["read"]()
        elif cmd == "o":
            handlers["object"](rest or None)
        elif cmd == "x":
            handlers["repeat"]()
        elif cmd == "s":
            if "stop" in handlers:
                handlers["stop"]()
        elif cmd:
            print("  (use r, o, x, s or q)")


if __name__ == "__main__":
    # Wiring test: press each button, hold one for 1.5 s.
    from signal import pause
    test_handlers = {
        "read": lambda: print("READ button pressed"),
        "object": lambda: print("OBJECT button pressed"),
        "repeat": lambda: print("REPEAT (button held)"),
    }
    if setup_gpio(test_handlers):
        print("Press the buttons. Ctrl+C to stop.")
        pause()