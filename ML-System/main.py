"""
╔══════════════════════════════════════════════════════════════════════════╗
║          HAND GESTURE VIRTUAL CONTROL SYSTEM  v2.0                      ║
║          MediaPipe · OpenCV · PyAutoGUI · pycaw / osascript             ║
╠══════════════════════════════════════════════════════════════════════════╣
║  GESTURES                                                                ║
║  ─────────────────────────────────────────────────────────────────────  ║
║  👍 Thumbs Up       → Increase System Volume                            ║
║  👎 Thumbs Down     → Decrease System Volume                            ║
║  ☝️  Index Finger Up → Move Mouse Cursor                                 ║
║  👌 OK Sign         → Left Mouse Click                                  ║
║  ✌️  Peace Sign      → Take Screenshot                                   ║
║  🤘 Rock Sign       → Toggle Interaction Mode                           ║
║  🖐️  Open Palm      → Pause / Resume Hand Tracking                      ║
║  ✊ Closed Fist     → Stop Cursor Movement (freeze)                     ║
║  4️⃣  Four Fingers   → Reset Cursor to Screen Center                     ║
║  🤏 Pinch & Hold   → Drag-and-Drop (hold = drag, release = drop)       ║
║                                                                          ║
║  Press  Q  to quit                                                       ║
╚══════════════════════════════════════════════════════════════════════════╝

Dependencies (install once):
    pip install opencv-python mediapipe pyautogui pillow

Volume control (optional, auto-detected):
    Windows : pip install pycaw comtypes
    macOS   : built-in  (uses osascript, no extra package)
    Linux   : uses amixer (usually pre-installed)
"""

# ──────────────────────────────────────────────────────────────────────────
# Standard library
# ──────────────────────────────────────────────────────────────────────────
import cv2
import mediapipe as mp
import pyautogui
import time
import math
import platform
import subprocess
import sys
import logging
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

# Optional screenshot
try:
    from PIL import ImageGrab  # noqa: F401 – used by pyautogui internally
except ImportError:
    pass

# ──────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("GestureCtrl")

# ──────────────────────────────────────────────────────────────────────────
# PyAutoGUI global settings
# ──────────────────────────────────────────────────────────────────────────
pyautogui.FAILSAFE = False
pyautogui.PAUSE    = 0


###############################################################################
# ENUMS & CONSTANTS
###############################################################################

class Gesture(Enum):
    NONE         = auto()
    THUMBS_UP    = auto()
    THUMBS_DOWN  = auto()
    INDEX_UP     = auto()
    OK_SIGN      = auto()
    PEACE_SIGN   = auto()
    ROCK_SIGN    = auto()
    OPEN_PALM    = auto()
    CLOSED_FIST  = auto()
    FOUR_FINGERS = auto()
    PINCH        = auto()


class InteractionMode(Enum):
    NORMAL   = "Normal Mode"
    GAMING   = "Gaming Mode"
    DRAWING  = "Drawing Mode"


# ─── Tuning constants (edit freely) ───────────────────────────────────────

# Camera / screen mapping
CAM_MARGIN_X     = 0.12   # fraction of frame width  to crop on each side
CAM_MARGIN_Y     = 0.12   # fraction of frame height to crop on each side
SCREEN_W, SCREEN_H = pyautogui.size()

# Cursor smoothing  (lower → smoother but laggier)
SMOOTHING_EMA    = 0.20   # exponential moving average factor
LANDMARK_HISTORY = 5      # rolling average over N frames

# Pinch / OK detection
PINCH_CLOSE      = 0.055  # normalised dist — pinch starts
PINCH_OPEN       = 0.080  # normalised dist — pinch ends (hysteresis)
OK_THRESH        = 0.055  # thumb-index distance for OK sign

# Gesture cooldowns (seconds) — prevents accidental re-triggers
COOLDOWN: dict[Gesture, float] = {
    Gesture.THUMBS_UP   : 0.80,
    Gesture.THUMBS_DOWN : 0.80,
    Gesture.OK_SIGN     : 0.40,
    Gesture.PEACE_SIGN  : 1.20,
    Gesture.ROCK_SIGN   : 1.00,
    Gesture.FOUR_FINGERS: 0.80,
    Gesture.OPEN_PALM   : 0.60,
    Gesture.CLOSED_FIST : 0.50,
}
DEFAULT_COOLDOWN = 0.35

# Volume step per gesture trigger (0-100 scale)
VOLUME_STEP = 5

# Drag-and-drop
DRAG_START_HOLD  = 0.30   # seconds pinch must be held to start dragging

# Gesture confirmation — gesture must be stable for N consecutive frames
CONFIRM_FRAMES   = 3

# Visual overlay
OVERLAY_ALPHA    = 0.45   # HUD panel opacity
HUD_DURATION     = 1.0    # seconds a HUD message stays visible


###############################################################################
# VOLUME CONTROL  (cross-platform)
###############################################################################

class VolumeController:
    """Thin wrapper around OS-specific volume APIs."""

    def __init__(self):
        self._os      = platform.system()
        self._volume  = self._pycaw = None
        self._init_platform()

    # ── init ──────────────────────────────────────────────────────────────
    def _init_platform(self):
        if self._os == "Windows":
            try:
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                self._volume = cast(interface, POINTER(IAudioEndpointVolume))
                log.info("Volume: Windows/pycaw ready")
            except Exception as e:
                log.warning(f"Volume: pycaw unavailable ({e}) — using keyboard fallback")
        elif self._os == "Darwin":
            log.info("Volume: macOS/osascript ready")
        elif self._os == "Linux":
            log.info("Volume: Linux/amixer ready")

    # ── public API ────────────────────────────────────────────────────────
    def change(self, delta: int):
        """delta > 0 increases volume, delta < 0 decreases."""
        try:
            if self._os == "Windows" and self._volume:
                self._change_windows(delta)
            elif self._os == "Darwin":
                self._change_macos(delta)
            elif self._os == "Linux":
                self._change_linux(delta)
            else:
                self._keyboard_fallback(delta)
        except Exception as e:
            log.warning(f"Volume change failed: {e}")
            self._keyboard_fallback(delta)

    def _change_windows(self, delta: int):
        current = self._volume.GetMasterVolumeLevelScalar()
        new_vol  = max(0.0, min(1.0, current + delta / 100.0))
        self._volume.SetMasterVolumeLevelScalar(new_vol, None)

    def _change_macos(self, delta: int):
        # Get current volume, clamp, set
        result  = subprocess.run(
            ["osascript", "-e", "output volume of (get volume settings)"],
            capture_output=True, text=True
        )
        current = int(result.stdout.strip()) if result.returncode == 0 else 50
        new_vol = max(0, min(100, current + delta))
        subprocess.run(
            ["osascript", "-e", f"set volume output volume {new_vol}"],
            check=False
        )

    def _change_linux(self, delta: int):
        sign = "+" if delta > 0 else "-"
        subprocess.run(
            ["amixer", "-D", "pulse", "sset", "Master", f"{abs(delta)}%{sign}"],
            capture_output=True, check=False
        )

    @staticmethod
    def _keyboard_fallback(delta: int):
        key = "volumeup" if delta > 0 else "volumedown"
        steps = abs(delta) // VOLUME_STEP
        for _ in range(max(1, steps)):
            pyautogui.press(key)


###############################################################################
# LANDMARK SMOOTHER
###############################################################################

class LandmarkSmoother:
    """Combines rolling-average and exponential-moving-average smoothing."""

    def __init__(self, history: int = LANDMARK_HISTORY):
        self._buf: deque = deque(maxlen=history)
        self._ex: Optional[float] = None
        self._ey: Optional[float] = None

    def update(self, x: float, y: float) -> tuple[float, float]:
        # 1. Rolling average
        self._buf.append((x, y))
        ax = sum(p[0] for p in self._buf) / len(self._buf)
        ay = sum(p[1] for p in self._buf) / len(self._buf)
        # 2. EMA on top
        if self._ex is None:
            self._ex, self._ey = ax, ay
        self._ex += (ax - self._ex) * SMOOTHING_EMA
        self._ey += (ay - self._ey) * SMOOTHING_EMA
        return self._ex, self._ey

    def reset(self):
        self._buf.clear()
        self._ex = self._ey = None


###############################################################################
# GESTURE CLASSIFIER
###############################################################################

class GestureClassifier:
    """
    Pure function — given MediaPipe landmarks, returns a Gesture enum.
    All geometry helpers are static methods to keep logic testable.
    """

    # Landmark indices (MediaPipe hand)
    WRIST       = 0
    THUMB_CMC   = 1;  THUMB_MCP  = 2;  THUMB_IP  = 3;  THUMB_TIP  = 4
    INDEX_MCP   = 5;  INDEX_PIP  = 6;  INDEX_DIP = 7;  INDEX_TIP  = 8
    MIDDLE_MCP  = 9;  MIDDLE_PIP = 10; MIDDLE_DIP= 11; MIDDLE_TIP = 12
    RING_MCP    = 13; RING_PIP   = 14; RING_DIP  = 15; RING_TIP   = 16
    PINKY_MCP   = 17; PINKY_PIP  = 18; PINKY_DIP = 19; PINKY_TIP  = 20

    # ── helpers ────────────────────────────────────────────────────────────
    @staticmethod
    def _dist(a, b) -> float:
        return math.hypot(a.x - b.x, a.y - b.y)

    @staticmethod
    def _finger_up(lm, tip: int, pip: int) -> bool:
        """True when a finger tip is above its PIP joint (extended)."""
        return lm[tip].y < lm[pip].y

    @staticmethod
    def _thumb_up(lm) -> bool:
        """Thumb extended upward: tip is clearly above the MCP joint."""
        return lm[4].y < lm[3].y < lm[2].y

    @staticmethod
    def _thumb_down(lm) -> bool:
        """Thumb pointing clearly downward: tip below MCP joint."""
        return lm[4].y > lm[3].y > lm[2].y

    # ── main classifier ────────────────────────────────────────────────────
    def classify(self, lm) -> Gesture:
        C = GestureClassifier

        # Finger extension flags (index, middle, ring, pinky)
        idx_up    = C._finger_up(lm, 8,  6)
        mid_up    = C._finger_up(lm, 12, 10)
        ring_up   = C._finger_up(lm, 16, 14)
        pinky_up  = C._finger_up(lm, 20, 18)
        thumb_up  = C._thumb_up(lm)
        thumb_dn  = C._thumb_down(lm)

        up_count  = sum([idx_up, mid_up, ring_up, pinky_up])

        # Pinch distance (thumb ↔ index)
        pinch_d   = C._dist(lm[4], lm[8])

        # ── Thumbs Up: all 4 fingers curled, thumb clearly pointing up ─────
        if up_count == 0 and thumb_up:
            return Gesture.THUMBS_UP

        # ── Thumbs Down: all 4 fingers curled, thumb clearly pointing down ─
        if up_count == 0 and thumb_dn:
            return Gesture.THUMBS_DOWN

        # ── Closed fist: all 4 fingers curled, thumb neither up nor down ──
        #    (thumb is tucked sideways across the palm — not clearly up/down)
        if up_count == 0 and not thumb_up and not thumb_dn:
            return Gesture.CLOSED_FIST

        # ── Open palm: all 4 fingers AND thumb clearly up ──────────────────
        if up_count == 4 and thumb_up:
            return Gesture.OPEN_PALM

        # ── Four fingers: all 4 fingers up, thumb NOT pointing upward ──────
        #    Thumb is naturally at the side — not thumb_up is the right guard
        if up_count == 4 and not thumb_up:
            return Gesture.FOUR_FINGERS

        # ── Peace sign: index + middle only ───────────────────────────────
        if idx_up and mid_up and not ring_up and not pinky_up:
            return Gesture.PEACE_SIGN

        # ── Rock sign: index + pinky, middle + ring down ──────────────────
        if idx_up and pinky_up and not mid_up and not ring_up:
            return Gesture.ROCK_SIGN

        # ── OK sign: thumb + index form a small circle, others extended ────
        if pinch_d < OK_THRESH and mid_up and ring_up:
            return Gesture.OK_SIGN

        # ── Pinch: thumb + index close, others curled ─────────────────────
        if pinch_d < PINCH_CLOSE and not mid_up and not ring_up:
            return Gesture.PINCH

        # ── Index only: cursor control ─────────────────────────────────────
        if idx_up and not mid_up and not ring_up and not pinky_up:
            return Gesture.INDEX_UP

        return Gesture.NONE


###############################################################################
# APPLICATION STATE
###############################################################################

@dataclass
class AppState:
    # Interaction mode & tracking pause
    mode          : InteractionMode = InteractionMode.NORMAL
    tracking_paused: bool = False
    cursor_frozen : bool = False

    # Cursor EMA position
    cursor_x      : float = field(default_factory=lambda: SCREEN_W / 2)
    cursor_y      : float = field(default_factory=lambda: SCREEN_H / 2)

    # Gesture confirmation
    candidate_gesture : Gesture = Gesture.NONE
    confirm_count     : int     = 0

    # Gesture cooldowns  {gesture: last_trigger_time}
    last_trigger  : dict = field(default_factory=dict)

    # Drag state
    is_dragging   : bool  = False
    pinch_held_since: float = 0.0

    # HUD messages  (text, expire_time)
    hud_msgs      : list  = field(default_factory=list)

    # Pinch open/close state (hysteresis)
    pinch_active  : bool  = False

    # Smoothers per-landmark
    index_smooth  : LandmarkSmoother = field(default_factory=LandmarkSmoother)
    thumb_smooth  : LandmarkSmoother = field(default_factory=LandmarkSmoother)

    # Volume controller
    volume_ctrl   : VolumeController = field(default_factory=VolumeController)

    # Modes cycling list
    _mode_cycle   : list = field(default_factory=lambda: list(InteractionMode))
    _mode_idx     : int  = 0

    def push_hud(self, text: str, duration: float = HUD_DURATION):
        expire = time.time() + duration
        # replace existing same-text entry or append
        self.hud_msgs = [m for m in self.hud_msgs if m[0] != text]
        self.hud_msgs.append((text, expire))
        # keep only last 3 messages
        self.hud_msgs = self.hud_msgs[-3:]

    def active_hud_msgs(self) -> list[str]:
        now = time.time()
        self.hud_msgs = [m for m in self.hud_msgs if m[1] > now]
        return [m[0] for m in self.hud_msgs]

    def cooldown_ok(self, g: Gesture) -> bool:
        cd   = COOLDOWN.get(g, DEFAULT_COOLDOWN)
        last = self.last_trigger.get(g, 0.0)
        return (time.time() - last) >= cd

    def mark_trigger(self, g: Gesture):
        self.last_trigger[g] = time.time()

    def cycle_mode(self):
        self._mode_idx = (self._mode_idx + 1) % len(self._mode_cycle)
        self.mode = self._mode_cycle[self._mode_idx]


###############################################################################
# GESTURE ACTION HANDLER
###############################################################################

class ActionHandler:
    """Maps confirmed gestures to system actions."""

    def __init__(self, state: AppState):
        self.state = state

    def dispatch(self, gesture: Gesture, lm) -> None:
        s = self.state

        # ── Open palm: toggle tracking pause ──────────────────────────────
        if gesture == Gesture.OPEN_PALM:
            if s.cooldown_ok(gesture):
                s.tracking_paused = not s.tracking_paused
                status = "Paused" if s.tracking_paused else "Resumed"
                s.push_hud(f"🖐  Tracking {status}", 1.5)
                log.info(f"Tracking {status}")
                s.mark_trigger(gesture)
            return

        if s.tracking_paused:
            return  # all other actions gated

        # ── Closed fist: freeze / unfreeze cursor ─────────────────────────
        if gesture == Gesture.CLOSED_FIST:
            if s.cooldown_ok(gesture):
                s.cursor_frozen = not s.cursor_frozen
                label = "Frozen ✊" if s.cursor_frozen else "Unfrozen"
                s.push_hud(f"Cursor {label}")
                log.info(f"Cursor {label}")
                s.mark_trigger(gesture)
            return

        if s.cursor_frozen:
            if gesture in (Gesture.INDEX_UP, Gesture.PINCH, Gesture.FOUR_FINGERS):
                s.push_hud("Cursor frozen — fist to unfreeze", 0.5)
                return
            # Allow non-movement gestures (screenshots, volume, clicks) to continue

        # ── Thumbs up/down: volume ────────────────────────────────────────
        if gesture == Gesture.THUMBS_UP:
            if s.cooldown_ok(gesture):
                s.volume_ctrl.change(+VOLUME_STEP)
                s.push_hud(f"🔊 Volume +{VOLUME_STEP}")
                s.mark_trigger(gesture)

        elif gesture == Gesture.THUMBS_DOWN:
            if s.cooldown_ok(gesture):
                s.volume_ctrl.change(-VOLUME_STEP)
                s.push_hud(f"🔈 Volume -{VOLUME_STEP}")
                s.mark_trigger(gesture)

        # ── OK sign: left click ───────────────────────────────────────────
        elif gesture == Gesture.OK_SIGN:
            if s.cooldown_ok(gesture):
                pyautogui.click()
                s.push_hud("👌 Click")
                s.mark_trigger(gesture)

        # ── Peace sign: screenshot ────────────────────────────────────────
        elif gesture == Gesture.PEACE_SIGN:
            if s.cooldown_ok(gesture):
                self._take_screenshot()
                s.mark_trigger(gesture)

        # ── Rock sign: toggle mode ────────────────────────────────────────
        elif gesture == Gesture.ROCK_SIGN:
            if s.cooldown_ok(gesture):
                s.cycle_mode()
                s.push_hud(f"🤘 {s.mode.value}")
                log.info(f"Mode: {s.mode.value}")
                s.mark_trigger(gesture)

        # ── Four fingers: reset cursor ────────────────────────────────────
        elif gesture == Gesture.FOUR_FINGERS:
            if s.cooldown_ok(gesture):
                cx, cy = SCREEN_W // 2, SCREEN_H // 2
                s.cursor_x, s.cursor_y = float(cx), float(cy)
                pyautogui.moveTo(cx, cy, duration=0.12)
                s.push_hud("4️⃣  Cursor Reset")
                s.mark_trigger(gesture)

        # ── Index up: move cursor ─────────────────────────────────────────
        elif gesture == Gesture.INDEX_UP:
            self._move_cursor(lm)

        # ── Pinch: drag and drop ──────────────────────────────────────────
        elif gesture == Gesture.PINCH:
            self._handle_drag(lm)

        # Handle pinch release (back to non-pinch) → drop
        if gesture != Gesture.PINCH and s.is_dragging:
            pyautogui.mouseUp()
            s.is_dragging = False
            s.push_hud("🤏 Drop")
            log.info("Drag released")

    # ── Cursor movement ────────────────────────────────────────────────────
    def _move_cursor(self, lm):
        s = self.state
        sx, sy = s.index_smooth.update(lm[8].x, lm[8].y)
        tx, ty = self._remap(sx, sy)
        s.cursor_x += (tx - s.cursor_x) * SMOOTHING_EMA
        s.cursor_y += (ty - s.cursor_y) * SMOOTHING_EMA
        pyautogui.moveTo(int(s.cursor_x), int(s.cursor_y))

    # ── Drag and drop ──────────────────────────────────────────────────────
    def _handle_drag(self, lm):
        s = self.state
        sx, sy = s.index_smooth.update(lm[8].x, lm[8].y)
        tx, ty = self._remap(sx, sy)
        s.cursor_x += (tx - s.cursor_x) * SMOOTHING_EMA
        s.cursor_y += (ty - s.cursor_y) * SMOOTHING_EMA
        cx, cy = int(s.cursor_x), int(s.cursor_y)

        if not s.is_dragging:
            if s.pinch_held_since == 0.0:
                s.pinch_held_since = time.time()
            elif (time.time() - s.pinch_held_since) >= DRAG_START_HOLD:
                pyautogui.mouseDown()
                s.is_dragging = True
                s.push_hud("🤏 Dragging…")
                log.info("Drag started")
        else:
            pyautogui.moveTo(cx, cy)

    # ── Screenshot helper ──────────────────────────────────────────────────
    def _take_screenshot(self):
        fname = time.strftime("screenshot_%Y%m%d_%H%M%S.png")
        try:
            img = pyautogui.screenshot()
            img.save(fname)
            self.state.push_hud(f"✌️  Screenshot: {fname}", 2.0)
            log.info(f"Screenshot saved: {fname}")
        except Exception as e:
            log.warning(f"Screenshot failed: {e}")
            self.state.push_hud("Screenshot failed", 1.5)

    # ── Coordinate remapping ────────────────────────────────────────────────
    @staticmethod
    def _remap(nx: float, ny: float) -> tuple[int, int]:
        ax = max(CAM_MARGIN_X, min(1 - CAM_MARGIN_X, nx))
        ay = max(CAM_MARGIN_Y, min(1 - CAM_MARGIN_Y, ny))
        rx = (ax - CAM_MARGIN_X) / (1 - 2 * CAM_MARGIN_X)
        ry = (ay - CAM_MARGIN_Y) / (1 - 2 * CAM_MARGIN_Y)
        return int(rx * SCREEN_W), int(ry * SCREEN_H)


###############################################################################
# OVERLAY / HUD RENDERER
###############################################################################

# Gesture display names
GESTURE_LABELS: dict[Gesture, str] = {
    Gesture.NONE        : "—",
    Gesture.THUMBS_UP   : "👍 Thumbs Up",
    Gesture.THUMBS_DOWN : "👎 Thumbs Down",
    Gesture.INDEX_UP    : "☝  Index Up",
    Gesture.OK_SIGN     : "👌 OK Sign",
    Gesture.PEACE_SIGN  : "✌  Peace",
    Gesture.ROCK_SIGN   : "🤘 Rock",
    Gesture.OPEN_PALM   : "🖐  Open Palm",
    Gesture.CLOSED_FIST : "✊ Fist",
    Gesture.FOUR_FINGERS: "4️  Four Fingers",
    Gesture.PINCH       : "🤏 Pinch",
}

# Gesture → HUD bar colour (BGR)
GESTURE_COLORS: dict[Gesture, tuple] = {
    Gesture.THUMBS_UP   : (60, 220, 60),
    Gesture.THUMBS_DOWN : (60, 60, 220),
    Gesture.INDEX_UP    : (200, 200, 60),
    Gesture.OK_SIGN     : (60, 220, 200),
    Gesture.PEACE_SIGN  : (160, 60, 220),
    Gesture.ROCK_SIGN   : (220, 120, 60),
    Gesture.OPEN_PALM   : (180, 180, 180),
    Gesture.CLOSED_FIST : (80, 80, 220),
    Gesture.FOUR_FINGERS: (60, 180, 220),
    Gesture.PINCH       : (220, 80, 160),
}
DEFAULT_COLOR = (180, 180, 180)


class HUDRenderer:
    """Draws the on-screen overlay onto an OpenCV frame."""

    @staticmethod
    def _put(frame, text: str, pos: tuple, scale=0.75,
             color=(220, 220, 220), thickness=2):
        cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX,
                    scale, (10, 10, 10), thickness + 2, cv2.LINE_AA)
        cv2.putText(frame, text, pos, cv2.FONT_HERSHEY_SIMPLEX,
                    scale, color, thickness, cv2.LINE_AA)

    @classmethod
    def draw(cls, frame, state: AppState, gesture: Gesture, fps: float):
        h, w = frame.shape[:2]

        # ── Semi-transparent top bar ───────────────────────────────────────
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 72), (20, 20, 30), -1)
        cv2.addWeighted(overlay, OVERLAY_ALPHA, frame, 1 - OVERLAY_ALPHA, 0, frame)

        # Gesture label
        g_color = GESTURE_COLORS.get(gesture, DEFAULT_COLOR)
        g_label = GESTURE_LABELS.get(gesture, "?")
        cls._put(frame, g_label, (14, 40), scale=0.95, color=g_color, thickness=2)

        # FPS
        fps_color = (60, 220, 60) if fps >= 24 else (60, 80, 220)
        cls._put(frame, f"FPS {fps:4.0f}", (w - 130, 40), color=fps_color)

        # Mode + pause indicator
        mode_str = state.mode.value
        if state.tracking_paused:
            mode_str += "  [ PAUSED ]"
        cls._put(frame, mode_str, (14, 65), scale=0.58, color=(180, 180, 100))

        # Drag indicator
        if state.is_dragging:
            cv2.rectangle(frame, (0, 0), (w, h), (0, 50, 200), 3)
            cls._put(frame, "DRAGGING", (w // 2 - 70, h - 20),
                     scale=0.85, color=(100, 200, 255), thickness=2)

        # ── HUD messages (bottom-left) ─────────────────────────────────────
        msgs = state.active_hud_msgs()
        for i, msg in enumerate(reversed(msgs)):
            y = h - 20 - i * 32
            cls._put(frame, msg, (14, y), scale=0.75, color=(240, 220, 100))

        # ── Pinch proximity gauge ──────────────────────────────────────────
        # (drawn separately in process_frame to have pinch_d in scope)


###############################################################################
# GESTURE CONFIRMATION BUFFER
###############################################################################

class GestureConfirmer:
    """Requires N consecutive identical frames before declaring a gesture."""

    def __init__(self, n: int = CONFIRM_FRAMES):
        self._n       = n
        self._current = Gesture.NONE
        self._count   = 0
        self._stable  = Gesture.NONE

    def update(self, raw: Gesture) -> Gesture:
        if raw == self._current:
            self._count += 1
        else:
            self._current = raw
            self._count   = 1

        if self._count >= self._n:
            self._stable = self._current

        return self._stable


###############################################################################
# MAIN PIPELINE
###############################################################################

def build_hands_detector():
    return mp.solutions.hands.Hands(
        static_image_mode        = False,
        max_num_hands            = 1,
        model_complexity         = 1,
        min_detection_confidence = 0.75,
        min_tracking_confidence  = 0.70,
    )


def process_frame(frame, detector, classifier, confirmer,
                  handler, hud, state: AppState,
                  fps_buf: deque) -> None:
    """Full per-frame pipeline."""
    now = time.time()

    # ── 1. MediaPipe inference ─────────────────────────────────────────────
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgb.flags.writeable = False
    result = detector.process(rgb)
    rgb.flags.writeable = True

    # ── 2. Draw landmarks ─────────────────────────────────────────────────
    mp_drawing = mp.solutions.drawing_utils
    mp_styles  = mp.solutions.drawing_styles
    mp_hands   = mp.solutions.hands

    gesture = Gesture.NONE
    if result.multi_hand_landmarks:
        for hl in result.multi_hand_landmarks:
            mp_drawing.draw_landmarks(
                frame, hl, mp_hands.HAND_CONNECTIONS,
                mp_styles.get_default_hand_landmarks_style(),
                mp_styles.get_default_hand_connections_style(),
            )
        lm = result.multi_hand_landmarks[0].landmark

        # Classify → confirm → act
        raw_gesture = classifier.classify(lm)
        gesture     = confirmer.update(raw_gesture)

        # Reset pinch_held_since if not pinching
        if gesture != Gesture.PINCH:
            state.pinch_held_since = 0.0

        handler.dispatch(gesture, lm)

        # Pinch gauge
        h, w = frame.shape[:2]
        pd    = math.hypot(lm[4].x - lm[8].x, lm[4].y - lm[8].y)
        bar_max = 0.15
        fill   = int((1 - min(pd / bar_max, 1.0)) * 110)
        bar_color = (0, 100, 255) if gesture == Gesture.PINCH else (0, 220, 100)
        cv2.rectangle(frame, (w - 140, h - 32), (w - 20, h - 16), (50, 50, 50), -1)
        cv2.rectangle(frame, (w - 140, h - 32), (w - 140 + fill, h - 16), bar_color, -1)
        HUDRenderer._put(frame, "Pinch", (w - 140, h - 36),
                          scale=0.5, color=(160, 160, 160))
    else:
        # No hand — reset smoothers & drag
        state.index_smooth.reset()
        state.thumb_smooth.reset()
        if state.is_dragging:
            pyautogui.mouseUp()
            state.is_dragging = False
        confirmer.update(Gesture.NONE)

    # ── 3. FPS ─────────────────────────────────────────────────────────────
    fps_buf.append(time.time())
    # keep only last 60 timestamps
    while fps_buf and fps_buf[0] < now - 1.0:
        fps_buf.popleft()
    fps = len(fps_buf)

    # ── 4. HUD overlay ────────────────────────────────────────────────────
    hud.draw(frame, state, gesture, fps)


class GestureServer:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            log.error("Cannot open camera. Check webcam connection.")
            sys.exit(1)

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS,          60)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)

        self.detector   = build_hands_detector()
        self.classifier = GestureClassifier()
        self.confirmer  = GestureConfirmer()
        self.state      = AppState()
        self.handler    = ActionHandler(self.state)
        self.hud        = HUDRenderer()
        self.fps_buf    : deque = deque(maxlen=120)

        self.current_gesture = Gesture.NONE
        self.current_fps = 0

    def generate_frames(self):
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    time.sleep(0.05)
                    continue

                frame = cv2.flip(frame, 1)

                process_frame(frame, self.detector, self.classifier, self.confirmer,
                              self.handler, self.hud, self.state, self.fps_buf)
                
                self.current_gesture = self.confirmer._stable
                self.current_fps = len(self.fps_buf)

                ret, buffer = cv2.imencode('.jpg', frame)
                frame_bytes = buffer.tobytes()

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        except GeneratorExit:
            pass
        except Exception as e:
            log.error(f"Frame generation error: {e}")

    def get_status(self):
        return {
            "gesture": GESTURE_LABELS.get(self.current_gesture, "?"),
            "gesture_raw": self.current_gesture.name,
            "mode": self.state.mode.value,
            "tracking_paused": self.state.tracking_paused,
            "cursor_frozen": self.state.cursor_frozen,
            "fps": self.current_fps,
            "hud_msgs": self.state.active_hud_msgs()
        }

    def close(self):
        if self.state.is_dragging:
            pyautogui.mouseUp()
        self.cap.release()
        self.detector.close()

if __name__ == "__main__":
    # If run standalone, fallback to local window mode
    server = GestureServer()
    window_name = "Hand Gesture Control"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    try:
        while True:
            ret, frame = server.cap.read()
            if not ret: continue
            frame = cv2.flip(frame, 1)
            process_frame(frame, server.detector, server.classifier, server.confirmer,
                          server.handler, server.hud, server.state, server.fps_buf)
            cv2.imshow(window_name, frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        server.close()
        cv2.destroyAllWindows()