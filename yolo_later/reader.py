"""Text layer. Watches the camera for text, asks the user, and hands the picture to Gemini on "yes".

  text found and steady for ~1 s  ->  "Text detected. Do you want me to read it? Say yes or no."
  yes  -> Gemini reads it (ask.run_mode("read"))        no / silence -> stays quiet for a while

The yes/no comes from handlers["yes"] / handlers["no"]. Today those are the keys y and n.
Later the voice recogniser (Vosk) calls the same two functions, so nothing else changes.

The answer timer starts only AFTER the question has been spoken, and the question is never
asked while the device is still talking (for example reading out a long answer).
"""
import socket, threading, time
from speech import ANSWER
from text_trigger import has_text

ONLINE_HOST = ("generativelanguage.googleapis.com", 443)


def online(timeout=1.5):
    try:
        socket.create_connection(ONLINE_HOST, timeout=timeout).close()
        return True
    except OSError:
        return False


class TextReader:
    def __init__(self, cam, speaker, poll=0.4, stable_frames=3, answer_timeout=15,
                 cooldown_yes=20, cooldown_no=30, check_online=online, run_read=None):
        self.cam, self.speaker = cam, speaker
        self.poll, self.stable_frames = poll, stable_frames
        self.answer_timeout = answer_timeout
        self.cooldown_yes, self.cooldown_no = cooldown_yes, cooldown_no
        self.check_online = check_online
        self.run_read = run_read or self._default_read
        self.pending = False            # a question has been asked and not answered yet
        self.deadline = None            # set when the question has finished playing
        self.quiet_until = 0
        self.streak = 0
        self.lock = threading.Lock()
        self._online = (0, False)       # (time checked, result), refreshed every 20 s

    def _default_read(self):
        import ask
        ask.run_mode("read", self.speaker)

    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def _is_online(self):
        t, ok = self._online
        if time.time() - t > 20:
            ok = self.check_online()
            self._online = (time.time(), ok)
        return ok

    def _speaker_busy(self):
        idle = getattr(self.speaker, "idle", None)
        return bool(idle) and not idle()

    def _question_spoken(self):
        with self.lock:
            if self.pending:
                self.deadline = time.time() + self.answer_timeout

    def _loop(self):
        while True:
            time.sleep(self.poll)
            now = time.time()
            with self.lock:
                if self.pending:
                    if self.deadline and now > self.deadline:    # no answer: same as "no", say nothing
                        self.pending = False
                        self.deadline = None
                        self.quiet_until = now + self.cooldown_no
                        self.streak = 0
                    continue
                if now < self.quiet_until:
                    continue
            if self._speaker_busy():                              # do not talk over another answer
                continue
            ok, frame = self.cam.read()
            if not ok:
                continue
            self.streak = self.streak + 1 if has_text(frame) else 0
            if self.streak >= self.stable_frames and self._is_online():
                with self.lock:
                    self.pending = True
                    self.deadline = None                          # the timer starts after the question is spoken
                    self.streak = 0
                self.speaker.say("Text detected. Do you want me to read it? Say yes or no.",
                                 ANSWER, done=self._question_spoken)

    def yes(self):
        with self.lock:
            if not self.pending:
                print("  (no question is waiting, so 'yes' was ignored)", flush=True)
                return
            self.pending = False
            self.deadline = None
        print("  reading the text with Gemini...", flush=True)
        threading.Thread(target=self._read_then_rest, daemon=True).start()

    def _read_then_rest(self):
        try:
            self.run_read()
        finally:
            with self.lock:
                self.quiet_until = time.time() + self.cooldown_yes    # counted from the end of the reading

    def no(self):
        with self.lock:
            if not self.pending:
                print("  (no question is waiting, so 'no' was ignored)", flush=True)
                return
            self.pending = False
            self.deadline = None
            self.quiet_until = time.time() + self.cooldown_no
        self.speaker.say("Okay", ANSWER)