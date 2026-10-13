PROMPTS = {
    "read": "Read all visible text aloud in natural order. If none, say 'No text found'. Be brief.",
    "color": "What is the main color of the object held in front of the camera? If unsure, say 'not sure'.",
    "item": ("Name the main object held in front of the camera in 1 to 4 words. "
             "If it is a food packet, read the product name. "
             "If it is a loose grain or pulse, name it. If unsure, say 'not sure'."),
    # The local YOLO model only knows door, stairs, window, person and wall,
    # so Gemini covers the rest here: lift, escalator, wet floor, sharp objects.
    "scene": ("You are helping a blind person who is walking. The camera is at chest height, looking forward. "
              "In at most two short sentences, mention hazards ahead with rough direction: person, door, "
              "window or glass, stairs or steps, escalator, lift, wet or shiny floor, obstacle, and any knife, "
              "scissors or other sharp object. If the image is too close, blurry, dark, or blocked, say "
              "'View unclear'. If you see no hazard, say 'No hazard seen in this view'."),
}
