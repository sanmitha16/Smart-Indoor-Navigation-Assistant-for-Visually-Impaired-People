PINS = {"read": 17, "color": 27, "item": 22, "scene": 23, "repeat": 24, "pack": 25}  # BCM numbers


def setup_gpio(handlers):
    """Use real buttons on the Pi. Returns None on a laptop (no GPIO), so the keyboard is used instead."""
    try:
        from gpiozero import Button
        buttons = {n: Button(p, pull_up=True, bounce_time=0.05) for n, p in PINS.items()}
    except Exception as e:
        print("GPIO not available, using keyboard:", e)
        return None
    for name, b in buttons.items():
        b.when_pressed = handlers[name]
    return buttons


def keyboard_loop(handlers):
    keys = {"r": "read", "c": "color", "i": "item", "s": "scene", "x": "repeat", "p": "pack"}
    while True:
        try:
            k = input("r=read c=color i=item s=scene x=repeat p=pack q=quit: ").strip().lower()
        except EOFError:                 # no terminal (for example when started automatically at boot)
            break
        if k == "q":
            break
        if k in keys:
            handlers[keys[k]]()