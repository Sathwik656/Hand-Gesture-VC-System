<div align="center">

# Hand Gesture Virtual Control System
### *Real-Time Gesture-Driven System Control with a Sci-Fi HUD Dashboard*

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16.2.6-000000?style=for-the-badge&logo=next.js&logoColor=white)](https://nextjs.org/)
[![MediaPipe](https://img.shields.io/badge/MediaPipe-0.10.14-0097A7?style=for-the-badge&logo=google&logoColor=white)](https://mediapipe.dev/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.10-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge)]()

<br/>

> **Control your entire computer — volume, mouse, screenshots, and more — using nothing but your hand gestures, streamed live to a real-time sci-fi HUD dashboard.**

---

</div>

## Table of Contents

- [Project Overview](#-project-overview)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Gesture Reference](#-gesture-reference)
- [System Architecture](#-system-architecture)
- [ML Pipeline](#-ml-pipeline)
- [Flask Backend API](#-flask-backend-api)
- [Next.js Frontend Dashboard](#-nextjs-frontend-dashboard)
- [Installation & Usage](#-installation--usage)

---

## Project Overview

The **Hand Gesture Virtual Control System** is an end-to-end computer vision application that lets you control your PC using only hand gestures detected through a standard webcam. It uses **Google MediaPipe** for real-time hand landmark detection, a custom **rule-based gesture classifier**, and a robust action engine to execute system commands — all streamed live to a **Next.js sci-fi HUD dashboard**.

### How It Works

```
Webcam → OpenCV Capture → MediaPipe Landmarks → GestureClassifier
    → GestureConfirmer (N-frame buffer) → ActionHandler → System Action
                                ↓
                    Flask API  (/api/video_feed  &  /api/status)
                                ↓
                    Next.js Dashboard  (150ms polling)
```

1. OpenCV captures each frame from the webcam at up to **60 FPS** at **1280×720**.
2. MediaPipe processes the frame and extracts **21 normalized 3D hand landmarks**.
3. The `GestureClassifier` maps landmark geometry to one of **10 gestures** using rule-based finger extension and distance checks.
4. The `GestureConfirmer` requires **3 consecutive identical frames** before committing to a gesture, eliminating flicker.
5. The `ActionHandler` dispatches the confirmed gesture to the correct system action (volume, click, screenshot, etc.), respecting per-gesture **cooldown timers**.
6. The processed frame (with a real-time HUD overlay) is MJPEG-streamed by Flask to the browser.
7. The Next.js dashboard polls `/api/status` every **150 ms** to display gesture name, mode, FPS, and a live interaction log.

---

## Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| **Python** | 3.12+ | Core backend language |
| **Flask** | 3.x | REST API & MJPEG video streaming |
| **Flask-CORS** | Latest | Cross-origin requests from Next.js |
| **MediaPipe** | 0.10.14 | Real-time hand landmark detection |
| **OpenCV** | 4.10.0 | Webcam capture, frame processing & HUD rendering |
| **PyAutoGUI** | 3.1.2 | Mouse control, clicks & screenshots |
| **pynput** | 2.0.9 | Low-level input event simulation |
| **pycaw / comtypes** | Latest | Windows system volume control |
| **NumPy** | Latest | Numerical geometry operations |
| **Pillow** | Latest | Screenshot capture support |
| **Next.js** | 16.2.6 | Real-time sci-fi HUD frontend |
| **React** | 19.2.4 | UI component framework |
| **TypeScript** | 5.x | Type-safe frontend development |
| **Tailwind CSS** | 4.x | Utility-first dashboard styling |
| **lucide-react** | 1.16.0 | Sci-fi icon set for the HUD |

---

## Project Structure

```bash
Task4 - Hand gesture recognition/
│
├── 📂 ML-System/                        # Python Backend
│   ├── main.py                          # Core gesture engine (842 lines)
│   │   ├── class GestureClassifier      # Rule-based landmark → gesture mapping
│   │   ├── class GestureConfirmer       # N-frame confirmation buffer
│   │   ├── class ActionHandler          # Gesture → system action dispatcher
│   │   ├── class VolumeController       # Cross-platform volume API (Win/Mac/Linux)
│   │   ├── class LandmarkSmoother       # EMA + rolling average cursor smoother
│   │   ├── class HUDRenderer            # OpenCV on-screen overlay renderer
│   │   ├── class AppState               # Centralized runtime state (dataclass)
│   │   └── class GestureServer          # Flask-compatible streaming wrapper
│   │
│   ├── app.py                           # Flask application & route definitions
│   ├── util.py                          # Geometry helpers (angle, distance)
│   └── requirements.txt                 # Python dependencies
│
└── 📂 frontend/                         # Next.js Frontend Dashboard
    ├── 📂 src/app/
    │   ├── page.tsx                     # Main sci-fi HUD dashboard component
    │   ├── layout.tsx                   # Root layout with global styles
    │   └── globals.css                  # Glassmorphic HUD CSS
    ├── package.json
    ├── next.config.ts
    └── tsconfig.json
```

---

## Gesture Reference

The system recognizes **10 distinct hand gestures**, each mapped to a specific system action:

| Gesture | Detection Logic | System Action |
|---|---|---|
| **Thumbs Up** | All 4 fingers curled, thumb tip clearly above MCP | Increase Volume (+5%) |
| **Thumbs Down** | All 4 fingers curled, thumb tip clearly below MCP | Decrease Volume (-5%) |
| **Index Finger Up** | Only index finger extended | Move Mouse Cursor |
| **Peace Sign** | Index + middle extended, ring + pinky curled | Take Screenshot |
| **Open Palm** | All 4 fingers + thumb extended | Pause / Resume Hand Tracking |
---

## System Architecture

### Backend Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        GestureServer                        │
│                                                             │
│   cv2.VideoCapture(0) ──► process_frame() ──► MJPEG Stream │
│          1280×720 @ 60fps                                   │
│                                                             │
│   ┌──────────────┐  ┌──────────────────┐  ┌─────────────┐  │
│   │  MediaPipe   │  │ GestureClassifier│  │GestureConfi-│  │
│   │  Hands (21   │─►│ (rule-based,     │─►│rmer (N=3    │  │
│   │  landmarks)  │  │ geometry checks) │  │frames)      │  │
│   └──────────────┘  └──────────────────┘  └──────┬──────┘  │
│                                                   │         │
│   ┌──────────────────────────────────────────────►│         │
│   │              ActionHandler                    ▼         │
│   │   Volume │ Click │ Screenshot │ Cursor │ Drag │ Mode    │
│   └─────────────────────────────────────────────────────────┘
│                                                             │
│   Flask Routes:  /api/video_feed  │  /api/status           │
└─────────────────────────────────────────────────────────────┘
```

### Frontend Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Next.js Dashboard                        │
│                                                             │
│  ┌────────────┐  ┌────────────────────┐  ┌──────────────┐  │
│  │ Left Panel │  │   Center Panel     │  │ Right Panel  │  │
│  │            │  │                    │  │              │  │
│  │ Core Vitals│  │  MJPEG Video Feed  │  │  Action Log  │  │
│  │  - FPS     │  │  (live stream from │  │  (HUD msgs   │  │
│  │  - Mode    │  │   Flask backend)   │  │   polled @   │  │
│  │  - Gesture │  │                    │  │   150ms)     │  │
│  │            │  │  Sci-fi reticle    │  │              │  │
│  │ System     │  │  overlay + corners │  │              │  │
│  │  State     │  │  scanline effect   │  │              │  │
│  │  - Engine  │  │                    │  │              │  │
│  │  - Cursor  │  │                    │  │              │  │
│  └────────────┘  └────────────────────┘  └──────────────┘  │
│                                                             │
│          Polling: GET /api/status  every 150ms              │
└─────────────────────────────────────────────────────────────┘
```

---

## ML Pipeline

### 1. Hand Landmark Detection — MediaPipe

MediaPipe's `Hands` solution detects and tracks **21 3D landmarks** per hand in real time with no model training required:

```python
mp.solutions.hands.Hands(
    static_image_mode        = False,
    max_num_hands            = 1,
    model_complexity         = 1,        # Full model for accuracy
    min_detection_confidence = 0.75,
    min_tracking_confidence  = 0.70,
)
```

### 2. Cursor Smoothing — Dual-Layer Filter

Raw landmark coordinates are smoothed using a **rolling average + EMA pipeline** to eliminate jitter:

```python
class LandmarkSmoother:
    # 1. Rolling average over last N=5 frames
    ax = mean(buffer[-5:])
    # 2. Exponential Moving Average (α = 0.20) on top
    ex += (ax - ex) * 0.20
```

This produces fluid cursor motion while remaining responsive to intentional direction changes.

### 3. Rule-Based Gesture Classification

The `GestureClassifier` uses pure geometry on landmark coordinates — **no ML model, no training data required**:

```python
# Finger extension: tip Y < PIP Y  (lower Y = higher on screen)
finger_up = landmark[tip].y < landmark[pip].y

# Pinch distance: normalized Euclidean distance
pinch_d = math.hypot(lm[4].x - lm[8].x, lm[4].y - lm[8].y)

# Example: Thumbs Up
if up_count == 0 and thumb_tip.y < thumb_mcp.y < thumb_ip.y:
    return Gesture.THUMBS_UP
```

### 4. Gesture Confirmation Buffer

To eliminate false triggers from brief misclassifications, a **3-frame confirmation buffer** is used:

```python
class GestureConfirmer:
    # Gesture must appear in 3 consecutive frames to be "confirmed"
    if consecutive_count >= CONFIRM_FRAMES:
        stable_gesture = current_gesture
```

### 5. Cooldown System

Each gesture has an independent cooldown timer to prevent unintended repeated triggers:

```python
COOLDOWN = {
    Gesture.THUMBS_UP   : 0.80,   # seconds
    Gesture.PEACE_SIGN  : 1.20,   # longer — screenshot is a heavy action
    Gesture.OK_SIGN     : 0.40,   # shorter — clicks need to be responsive
    ...
}
```

---

## Flask Backend API

### Route Map

```
GET  /api/video_feed  →  MJPEG stream of processed webcam frames
GET  /api/status      →  JSON snapshot of current system state
```

### `/api/status` Response Format

```json
{
  "gesture":         "Thumbs Up",
  "gesture_raw":     "THUMBS_UP",
  "mode":            "Normal Mode",
  "tracking_paused": false,
  "cursor_frozen":   false,
  "fps":             58,
  "hud_msgs":        ["Volume +5"]
}
```

### `/api/video_feed`

Returns a `multipart/x-mixed-replace` MJPEG stream. The processed frames include:

- **MediaPipe hand skeleton** overlay (joints + connections)
- **Gesture label** with color-coded HUD bar (top-left)
- **Live FPS counter** (top-right)
- **Interaction mode** indicator
- **Pinch proximity gauge** (bottom-right)
- **HUD action messages** (bottom-left, auto-expire after 1–2 seconds)
- **Drag-and-drop border** animation when dragging is active

---

## Next.js Frontend Dashboard

The frontend is a **sci-fi HUD dashboard** built with Next.js 16, React 19, TypeScript, and Tailwind CSS v4.

### Key UI Panels

| Panel | Location | Contents |
|---|---|---|
| **Core Vitals** | Left | Live FPS, interaction mode, latest gesture label |
| **System State** | Left (lower) | Engine status (Active/Paused), cursor lock state |
| **Video Feed** | Center | MJPEG stream with scanline & reticle overlay, corner brackets, REC indicator |
| **Action Log** | Right | Time-stamped log of every HUD action event (last 20, newest first) |

### Real-Time Data Flow

```typescript
// Fast polling loop — 150ms interval
const fetchStatus = async () => {
  const res  = await fetch("http://localhost:5000/api/status");
  const data = await res.json();
  setStatus(data);

  // Diff HUD messages to generate new log entries
  const newMsgs = data.hud_msgs.filter(msg => !lastHudMsgsRef.current.includes(msg));
  setLogs(prev => [...newLogEntries, ...prev].slice(0, 20));
};
setInterval(fetchStatus, 150);
```

### Dashboard Aesthetic

- **Dark base** — `#030b14` deep space background
- **Cyan accent** — `#06b6d4` glows, borders, and text highlights
- **Glassmorphic panels** — semi-transparent cards with backdrop blur
- **Scanline effect** — animated CRT scanline on the video feed
- **Corner bracket** decorations on the camera viewport
- **Font** — monospace throughout for the terminal/HUD feel

---

## Installation & Usage

### Prerequisites

- Python 3.10+
- Node.js 18+ & npm
- A working webcam

---

### 1 — Clone the Repository

```bash
git clone https://github.com/Sathwik656/PRODIGY_ML_04.git
cd "Task4 - Hand gesture recognition"
```

---

### 2 — Set Up the Python Backend

```bash
cd ML-System

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate       # Windows
source venv/bin/activate      # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Windows volume control (optional but recommended)
pip install pycaw comtypes
```

> **Note (Windows):** `pycaw` enables direct Windows Core Audio API integration for smooth volume control. Without it, the system falls back to keyboard media keys.

---

### 3 — Start the Flask Backend

```bash
# From inside ML-System/
python app.py
```

The backend starts at **`http://localhost:5000`**. You should see your webcam activate immediately.

---

### 4 — Set Up & Run the Frontend Dashboard

Open a **second terminal**:

```bash
cd frontend
npm install
npm run dev
```

Open your browser at **`http://localhost:3000`**

---

### Running the Backend in Standalone Mode (No Dashboard)

You can also run the gesture engine as a standalone OpenCV window without the web dashboard:

```bash
cd ML-System
python main.py
```

Press **`Q`** to quit.

---

### Quick Gesture Guide

| What you want to do | Show this gesture |
|---|---|
| Turn volume up | Point thumb up, curl all fingers |
| Turn volume down | Point thumb down, curl all fingers |
| Move the mouse | Raise only your index finger |
| Take a screenshot | Raise index + middle finger |
| Pause all gesture control | Open palm flat |

---

<div align="center">

[![GitHub](https://img.shields.io/badge/GitHub-Follow-black?style=flat-square&logo=github)](https://github.com/Sathwik656)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat-square&logo=linkedin)](https://linkedin.com/in/sathwik677)

*If you found this project helpful, please consider giving it a star on GitHub!*

</div>
