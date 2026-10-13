import platform, queue, subprocess, threading, time

CRITICAL, GUARDIAN, ANSWER = 0, 1, 2     # lower number = higher priority


class Speaker:
    """One voice for the whole program. Everything that wants to talk goes through say()."""

    def __init__(self):
        self.q = queue.PriorityQueue()
        self.n = 0
        self.proc = None
        self.lock = threading.Lock()
        self.now_priority = 99
        threading.Thread(target=self._worker, daemon=True).start()

    def say(self, text, priority=ANSWER, max_age=None):
        """max_age: drop the message if it waited longer than this many seconds (stale alerts)."""
        self.n += 1
        self.q.put((priority, self.n, time.time(), max_age, text))
        if priority == CRITICAL:             # cut off lower-priority speech that is playing now
            with self.lock:
                if self.proc and self.proc.poll() is None and self.now_priority > CRITICAL:
                    self.proc.terminate()

    def _cmd(self, text):
        if platform.system() == "Linux":
            return ["espeak-ng", "-s", "150", text]
        safe = text.replace("'", "")
        return ["powershell", "-NoProfile", "-Command",
                "Add-Type -AssemblyName System.Speech; "
                f"(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{safe}')"]

    def _worker(self):
        while True:
            priority, _, t, max_age, text = self.q.get()
            if max_age is not None and time.time() - t > max_age:
                continue                     # stale alert, skip it
            self.now_priority = priority
            print("SPEAK:", text, flush=True)
            try:
                with self.lock:
                    self.proc = subprocess.Popen(self._cmd(text))
                self.proc.wait()
            except Exception as e:           # e.g. espeak-ng not installed: keep running
                print("Speech error:", e, flush=True)
            self.now_priority = 99
