# OpenShorts Studio: AI Highlights & Auto-Clipper

An automated, hardware-accelerated studio engine for converting long livestream footage (1–4+ hours) into viral 9:16 Shorts, Reels, and TikToks with split-screen webcam framing, Topaz-style clarity upscaling, and dynamic karaoke subtitles.

---

## 🚀 1-Click Quick Start (Run Locally on Any Desktop)

OpenShorts Studio is 100% self-contained and portable. It requires **no technical setup**, zero AI assistance, and runs completely offline once models are present.

### How to Run:
1. **Double-click `run.bat` (or `start.bat`)**
   - Automatically detects your Python environment (or creates an isolated `.venv`).
   - Auto-verifies and installs all required dependencies.
   - Runs pre-flight diagnostics for FFmpeg, Whisper-CLI, models, and hardware encoders.
   - Automatically opens your web browser to **[http://localhost:8000](http://localhost:8000)**.
2. **Optional: Create a Desktop Shortcut**
   - Double-click `create_desktop_shortcut.bat`.
   - A convenient desktop shortcut icon named **"OpenShorts Studio"** will be created directly on your Windows Desktop for 1-click launching!

### Hardware Acceleration (Zero-Config):
- **NVIDIA GPU**: Automatically uses `h264_nvenc` with NVMM memory buffers for ~100+ FPS export speed.
- **Intel Graphics (QuickSync)**: Automatically uses `h264_qsv` with MFX surface acceleration.
- **AMD GPU**: Automatically uses `h264_amf`.
- **CPU Fallback**: If no discrete GPU is found or an encoder driver fails, it automatically falls back to multi-core CPU `libx264` without crashing or interrupting your export queue.

---

## 📸 Studio Showcase & Features

````carousel
![In-Card Video Position & Panning Controls](/C:/Users/apsin/.gemini/antigravity/brain/d9e2819f-df12-4455-afbb-dbec68e0d6e6/gameplay_pan_controls_verified.png)
<!-- slide -->
![Live 9:16 Canvas with Left Shift Framing](/C:/Users/apsin/.gemini/antigravity/brain/d9e2819f-df12-4455-afbb-dbec68e0d6e6/gameplay_pan_canvas_verified.png)
<!-- slide -->
![Exported Video with MrBeast Styled Subtitles & Resized Gameplay](/C:/Users/apsin/.gemini/antigravity/brain/d9e2819f-df12-4455-afbb-dbec68e0d6e6/export_styled_modal_verified.png)
<!-- slide -->
![Burnt Karaoke Subtitles Verification Frame](/C:/Users/apsin/.gemini/antigravity/brain/d9e2819f-df12-4455-afbb-dbec68e0d6e6/subtitles_mrbeast_verified.jpg)
<!-- slide -->
![Words Shown at a Time & Whisper Model Selector](/C:/Users/apsin/.gemini/antigravity/brain/d9e2819f-df12-4455-afbb-dbec68e0d6e6/subtitles_words_and_preset_verified.png)
<!-- slide -->
![Background Blur Strength Presets & Smooth Range](/C:/Users/apsin/.gemini/antigravity/brain/d9e2819f-df12-4455-afbb-dbec68e0d6e6/blur_controls_verified.png)
````

OpenShorts Studio is running locally at **[http://localhost:8000](http://localhost:8000)**.

---

## 1. Centered Gameplay Card Sizing, In-Card Positioning & Framing

> [!TIP]
> You now have full creative control over both the gameplay card dimensions on the canvas AND the exact positioning/panning of the video inside the card.

Under **Tab 2: Template > Centered Gameplay Card Sizing & Framing**:
- **Continuous Card Dimensions**:
  - **Card Width**: Scale from `600px` up to `1080px` (full-bleed width).
  - **Card Height**: Scale from `350px` up to `900px`.
  - **Lock 16:9 Aspect Ratio**: Automatically syncs height to maintain widescreen proportions.
- **Card Placement on Canvas**:
  - **Vertical Position (Y)**: Slide vertically between `400px` and `1100px`.
  - **Center Y**: Instantly snaps the card to `(1920 - H) / 2`.
- **In-Card Video Position (Pan & Frame)**:
  - **Horizontal Position (Pan X)**: Shift video left or right inside the card (`-100%` Left to `+100%` Right). Dynamic readout displays `Center`, `30% Left`, `40% Right`.
  - **Vertical Position (Pan Y)**: Shift video up or down inside the card (`-100%` Up to `+100%` Down). Dynamic readout displays `Center`, `20% Up`, `30% Down`.
  - **Nudge Arrow Buttons** (`◀`, `▶`, `▲`, `▼`): Fine-tune framing by 5% increments.
  - **Center Video Reset**: Snaps both Pan X and Pan Y back to optical `(0%, 0%)`.
  - **Framing Presets**:
    - `Center Action`: Optical center.
    - `Left Shift (-40%)`: Focuses on left-side action or streamer webcams in gameplay.
    - `Right Shift (+40%)`: Focuses on right-side action.
    - `Top/HUD (-30%)`: Focuses on upper minimap, health bars, and HUD elements.
    - `Bottom Action (+30%)`: Focuses on weapon crosshairs and lower gameplay.
- **Smart Framing Zoom Assist**:
  - Automatically ensures framing headroom (`1.15x`–`1.25x`) when panning so video movement is smooth without letterbox gaps.

---

## 2. High-Accuracy Whisper Token Synchronization

> [!IMPORTANT]
> Subtitle transcription uses full Whisper BPE token timestamps (`-ojf`), eliminating timing jitter and uneven time-splitting.

- **True Millisecond Word Timestamps**: Subtitle word start and end offsets are extracted directly from Whisper's acoustic neural alignment.
- **Local Models**:
  - **Fast English (`tiny.en`)**: High accuracy with rapid 2–3s inference per clip.
  - **Deep Neural (`base`)**: Deep multi-language accuracy for accented speech or noisy game audio.

---

## 3. "Words Shown at a Time" (Per-Screen Chunking)

- **Instant Chunking**: Select `1 Word (Punchy)`, `2 Words`, `3 Words (Viral Sweet-Spot)`, `4 Words`, or `Full Phrase`.
- **Re-Group Active Subtitles Button**: Instantly re-chunks existing transcripts without re-transcribing.

---

## 4. Vibrant Subtitle Styling & Templates

- **MrBeast**: Sunburst Yellow (`#FFE600`) with Neon Lime (`#00FF66`) highlight and 6px stroke.
- **Hormozi**: Crisp White (`#FFFFFF`) with Electric Gold (`#FFDE00`) highlight and 5px stroke.
- **Neon Cyber Glow**: Electric Cyan (`#00F5FF`) with Hot Magenta (`#FF007F`) highlight.
- **Fire Red Alert**, **Box Pill**, and **Clean Sky**.

---

## 5. Global Batch Synchronization & Background Blur

- **Apply to All**: Broadcasts webcam crop, gameplay card dimensions, framing pan, zoom level, background blur radius, and subtitle styling across all loaded clips in 1 click.
- **Adjustable Background Blur**: Fast Gaussian-equivalent bokeh from `0px` to `80px`.
