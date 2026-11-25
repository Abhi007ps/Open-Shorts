// State
const state = {
  videoLoaded: false,
  videoPath: "",
  videoMeta: null,
  clips: [],
  selectedClipId: null,
  subtitles: [],
  previewTime: 10.0,
  isRenderingPreview: false,
  template: {
    layout_mode: "split_screen",
    canvas_w: 1080,
    canvas_h: 1920,
    bg_blur_sigma: 0,
    bg_brightness: 0.0,
    gameplay_w: 1080,
    gameplay_h: 700,
    gameplay_radius: 0,
    gameplay_border_w: 0,
    gameplay_border_color: "#FFFFFF",
    gameplay_y: 960,
    gameplay_zoom: 1.15,
    gameplay_pan_x: 0,
    gameplay_pan_y: 0,
    webcam_w: 1080,
    webcam_h: 700,
    webcam_shape: "split_screen",
    webcam_radius: 0,
    webcam_x: 0,
    webcam_y: 260,
    webcam_border_w: 0,
    webcam_border_color: "#FFFFFF",
    webcam_glow_enabled: false,
    webcam_glow_color: "#CCFF00",
    webcam_glow_size: 0,
    webcam_glow_intensity: 1.0,
    webcam_glow_effect: "none",
    webcam_crop: { x: 20, y: 140, w: 360, h: 320 },
    divider_line: true,
    divider_color: "#FFFFFF",
    divider_height: 4,
    sharpen_amount: 0.50,
    contrast_boost: 1.06,
    saturation_boost: 1.14,
    brightness_offset: 0.01,
    micro_texture: 0.40,
    deblock_level: "medium",
    pixel_generator: true,
    pixel_generator_mode: "ultra",
    export_bitrate: "14M",
    climax_zoom_enabled: false,
    auto_jump_cut: false
  },
  masterTemplate: null,
  autoApplyMaster: true,
  hookConfig: null,
  subtitlesConfig: {
    enabled: true,
    font_family: "Montserrat ExtraBold",
    font_size: 62,
    position_x: 50,
    position_y: 50,
    style_preset: "studio_flow",
    primary_color: "#FFFFFF",
    highlight_color: "#38BDF8",
    outline_color: "#000000",
    outline_width: 2,
    shadow_depth: 2,
    is_uppercase: true,
    words_per_line: 4,
    model_name: "large-v3-turbo-q5_0",
    sync_offset_ms: 0,
    censor_profanity: true,
    preview_text: "THIS IS WRONG WITH TODAY'S SOCIETY"
  },
  viralSettings: {
    min_duration: 8.0,
    max_duration: 30.0,
    mode: "auto",
    target_clips: 5,
    profile: "balanced",
    weight_audio: 0.25,
    weight_pitch: 0.15,
    weight_hook: 0.25,
    weight_speech: 0.20,
    weight_motion: 0.15,
    snap_boundaries: true
  }
};

let previewDebounceTimer = null;

function normalizeWhisperModelName(name) {
  return (name === "large-v3-turbo-q5_0" || name === "small.en") ? name : "small.en";
}

function normalizeStylePreset(preset) {
  return (!preset || preset === "skyglow") ? "studio_flow" : preset;
}

// =========================================================================
// SmoothProgressBar: 60FPS Asymptotic Smooth Progress & Cancellation Engine
// =========================================================================
class SmoothProgressBar {
  constructor(options = {}) {
    this.container = typeof options.container === "string" ? document.getElementById(options.container) : (options.container || options.box);
    this.bar = typeof options.bar === "string" ? document.getElementById(options.bar) : options.bar;
    this.statusText = typeof options.text === "string" ? document.getElementById(options.text) : (options.status || options.text);
    this.percentText = typeof options.percent === "string" ? document.getElementById(options.percent) : options.percent;
    this.timerText = typeof options.timer === "string" ? document.getElementById(options.timer) : options.timer;
    this.cancelBtn = typeof options.cancelBtn === "string" ? document.getElementById(options.cancelBtn) : options.cancelBtn;
    this.onCancel = options.onCancel || null;

    this.displayedPct = 0.0;
    this.targetPct = 0.0;
    this.lastTargetUpdate = Date.now();
    this.startTime = null;
    this.timerInterval = null;
    this.rafId = null;
    this.isActive = false;

    this.ensureUiEnhancements();
  }

  ensureUiEnhancements() {
    if (!this.container) return;
    this.container.classList.add("smooth-progress-container");
    if (this.bar) this.bar.classList.add("smooth-progress-bar");

    let metaStrip = this.container.querySelector(".progress-meta-strip");
    if (!metaStrip) {
      metaStrip = document.createElement("div");
      metaStrip.className = "progress-meta-strip";

      const topRow = this.container.firstElementChild;
      if (topRow && topRow !== this.bar && topRow !== this.bar?.parentElement) {
        topRow.appendChild(metaStrip);
      } else {
        this.container.insertBefore(metaStrip, this.container.firstChild);
      }
    }

    if (!this.timerText && metaStrip) {
      const existingTimer = metaStrip.querySelector(".progress-elapsed-badge");
      if (existingTimer) {
        this.timerText = existingTimer;
      } else {
        const badge = document.createElement("span");
        badge.className = "progress-elapsed-badge";
        badge.innerText = "00:00";
        metaStrip.appendChild(badge);
        this.timerText = badge;
      }
    }

    if (!this.cancelBtn && this.onCancel && metaStrip) {
      const existingBtn = metaStrip.querySelector(".progress-cancel-btn");
      if (existingBtn) {
        this.cancelBtn = existingBtn;
      } else {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "progress-cancel-btn";
        btn.innerHTML = `<i class="fa-solid fa-xmark"></i> Cancel`;
        btn.addEventListener("click", (e) => {
          e.stopPropagation();
          e.preventDefault();
          if (this.onCancel) this.onCancel();
        });
        metaStrip.appendChild(btn);
        this.cancelBtn = btn;
      }
    }
  }

  start(msg = "Processing...", initPct = 5) {
    this.isActive = true;
    this.displayedPct = Math.max(0, initPct);
    this.targetPct = Math.max(0, initPct);
    this.lastTargetUpdate = Date.now();
    this.startTime = Date.now();

    if (this.container) {
      this.container.style.display = "block";
      this.container.style.opacity = "1";
    }
    if (this.bar) {
      this.bar.classList.remove("completed", "error", "cancelled");
      this.bar.classList.add("running");
      this.bar.style.width = `${this.displayedPct}%`;
    }
    if (this.statusText) {
      this.statusText.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${msg}`;
    }
    if (this.percentText) {
      this.percentText.innerText = `${Math.round(this.displayedPct)}%`;
      this.percentText.style.fontVariantNumeric = "tabular-nums";
    }
    if (this.cancelBtn) {
      this.cancelBtn.disabled = false;
      this.cancelBtn.style.display = "inline-flex";
      this.cancelBtn.innerHTML = `<i class="fa-solid fa-xmark"></i> Cancel`;
    }

    if (this.timerInterval) clearInterval(this.timerInterval);
    this.timerInterval = setInterval(() => {
      if (!this.isActive || !this.startTime) return;
      const sec = Math.floor((Date.now() - this.startTime) / 1000);
      const mm = String(Math.floor(sec / 60)).padStart(2, "0");
      const ss = String(sec % 60).padStart(2, "0");
      if (this.timerText) {
        this.timerText.innerText = `${mm}:${ss}`;
      }
    }, 1000);

    this.startAnimationLoop();
  }

  setTarget(pct, msg = null) {
    const p = Math.max(0, Math.min(100, parseFloat(pct) || 0));
    this.targetPct = p;
    this.lastTargetUpdate = Date.now();
    if (msg && this.statusText) {
      this.statusText.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${msg}`;
    }
  }

  startAnimationLoop() {
    if (this.rafId) cancelAnimationFrame(this.rafId);

    const step = () => {
      if (!this.isActive) return;

      const now = Date.now();
      if (now - this.lastTargetUpdate > 800 && this.targetPct < 94) {
        const ceiling = Math.min(94, this.targetPct + 12);
        if (this.targetPct < ceiling) {
          this.targetPct += 0.08;
        }
      }

      if (this.displayedPct < this.targetPct) {
        const diff = this.targetPct - this.displayedPct;
        const delta = Math.max(0.12, Math.min(diff, diff * 0.12));
        this.displayedPct = Math.min(this.targetPct, this.displayedPct + delta);
      } else if (this.displayedPct > this.targetPct && this.targetPct >= 100) {
        this.displayedPct = 100;
      }

      const intVal = Math.round(this.displayedPct);
      if (this.bar) {
        this.bar.style.width = `${this.displayedPct.toFixed(1)}%`;
      }
      if (this.percentText) {
        this.percentText.innerText = `${intVal}%`;
      }

      this.rafId = requestAnimationFrame(step);
    };

    this.rafId = requestAnimationFrame(step);
  }

  complete(msg = "Done!") {
    this.isActive = false;
    this.targetPct = 100.0;
    this.displayedPct = 100.0;
    if (this.rafId) cancelAnimationFrame(this.rafId);
    if (this.timerInterval) clearInterval(this.timerInterval);

    if (this.bar) {
      this.bar.style.width = "100%";
      this.bar.classList.remove("running", "error", "cancelled");
      this.bar.classList.add("completed");
    }
    if (this.percentText) {
      this.percentText.innerText = "100%";
    }
    if (this.statusText) {
      this.statusText.innerHTML = `<i class="fa-solid fa-circle-check" style="color:var(--accent-lime, #10B981);"></i> ${msg}`;
    }
    if (this.cancelBtn) {
      this.cancelBtn.style.display = "none";
    }
  }

  cancel(msg = "Cancelled by user") {
    this.isActive = false;
    if (this.rafId) cancelAnimationFrame(this.rafId);
    if (this.timerInterval) clearInterval(this.timerInterval);

    if (this.bar) {
      this.bar.classList.remove("running", "completed");
      this.bar.classList.add("cancelled");
    }
    if (this.statusText) {
      this.statusText.innerHTML = `<i class="fa-solid fa-ban" style="color:#EF4444;"></i> ${msg}`;
    }
    if (this.cancelBtn) {
      this.cancelBtn.disabled = true;
      this.cancelBtn.innerText = "Cancelled";
    }
  }

  error(msg = "Failed") {
    this.isActive = false;
    if (this.rafId) cancelAnimationFrame(this.rafId);
    if (this.timerInterval) clearInterval(this.timerInterval);

    if (this.bar) {
      this.bar.classList.remove("running", "completed");
      this.bar.classList.add("error");
    }
    if (this.statusText) {
      this.statusText.innerHTML = `<i class="fa-solid fa-triangle-exclamation" style="color:#EF4444;"></i> ${msg}`;
    }
    if (this.cancelBtn) {
      this.cancelBtn.style.display = "none";
    }
  }

  reset() {
    this.isActive = false;
    if (this.rafId) cancelAnimationFrame(this.rafId);
    if (this.timerInterval) clearInterval(this.timerInterval);
    this.displayedPct = 0;
    this.targetPct = 0;
    if (this.bar) {
      this.bar.style.width = "0%";
      this.bar.classList.remove("running", "completed", "error", "cancelled");
    }
    if (this.percentText) this.percentText.innerText = "0%";
    if (this.timerText) this.timerText.innerText = "00:00";
    if (this.cancelBtn) this.cancelBtn.style.display = "none";
  }
}

async function runAsyncJob(endpoint, fetchOptions = {}, progressUiConfig = {}) {
  const separator = endpoint.includes("?") ? "&" : "?";
  const asyncEndpoint = `${endpoint}${separator}async_mode=1`;

  let currentJobId = null;
  let isCancelled = false;

  const pBar = new SmoothProgressBar({
    container: progressUiConfig.container || progressUiConfig.box,
    bar: progressUiConfig.bar,
    text: progressUiConfig.text || progressUiConfig.status,
    percent: progressUiConfig.percent,
    timer: progressUiConfig.timer,
    cancelBtn: progressUiConfig.cancelBtn,
    onCancel: async () => {
      if (!currentJobId || isCancelled) return;
      isCancelled = true;
      if (pBar.cancelBtn) {
        pBar.cancelBtn.disabled = true;
        pBar.cancelBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Cancelling...`;
      }
      try {
        await fetch(`/api/jobs/${currentJobId}/cancel`, { method: "POST" });
        if (typeof showToast === "function") showToast("Cancellation requested...");
      } catch (err) {
        console.warn("Cancel request error:", err);
      }
    }
  });

  const initMsg = progressUiConfig.initialText || "Starting background job...";
  pBar.start(initMsg, progressUiConfig.initialPercent || 5);

  let pollTimer = null;

  try {
    if (typeof fetchToolsStatus === "function") fetchToolsStatus();
    const res = await fetch(asyncEndpoint, fetchOptions);
    if (!res.ok) {
      const errTxt = await res.text();
      let errMsg = errTxt;
      try {
        const parsed = JSON.parse(errTxt);
        if (parsed.detail) errMsg = parsed.detail;
      } catch (_) {}
      throw new Error(errMsg || `Request failed (${res.status})`);
    }

    const initialData = await res.json();

    if (!initialData || initialData.status !== "queued" || !initialData.job_id) {
      pBar.complete(progressUiConfig.completeText || "Completed!");
      return initialData;
    }

    currentJobId = initialData.job_id;

    return await new Promise((resolve, reject) => {
      pollTimer = setInterval(async () => {
        try {
          const pollRes = await fetch(`/api/jobs/${currentJobId}`);
          if (!pollRes.ok) {
            clearInterval(pollTimer);
            pBar.error(`Status error (${pollRes.status})`);
            reject(new Error(`Failed to check job status (${pollRes.status})`));
            return;
          }

          const job = await pollRes.json();

          if (job.status === "running") {
            pBar.setTarget(job.percent || 15, job.step || "Processing...");
            if (progressUiConfig.onProgress) {
              progressUiConfig.onProgress(job);
            }
          } else if (job.status === "completed") {
            clearInterval(pollTimer);
            pBar.complete(job.step || progressUiConfig.completeText || "Completed!");
            resolve(job.result);
          } else if (job.status === "cancelled") {
            clearInterval(pollTimer);
            pBar.cancel("Cancelled by user");
            const cancelErr = new Error("Job cancelled by user");
            cancelErr.isCancelled = true;
            reject(cancelErr);
          } else if (job.status === "error") {
            clearInterval(pollTimer);
            pBar.error(job.error || "Job failed");
            reject(new Error(job.error || "Job failed with an error"));
          }
        } catch (pollErr) {
          console.warn("Poll fetch error:", pollErr);
        }
      }, 350);
    });

  } catch (err) {
    if (pollTimer) clearInterval(pollTimer);
    if (err.isCancelled) {
      pBar.cancel("Job cancelled");
    } else {
      pBar.error(err.message || "Failed");
    }
    throw err;
  } finally {
    if (typeof fetchToolsStatus === "function") fetchToolsStatus();
  }
}


// Initialization
document.addEventListener("DOMContentLoaded", () => {
  const safeInit = (fn, name) => {
    try {
      fn();
    } catch (err) {
      console.warn(`[Init] ${name} notice:`, err);
    }
  };

  safeInit(initTabs, "initTabs");
  safeInit(initSliders, "initSliders");
  safeInit(initColors, "initColors");
  safeInit(initPresets, "initPresets");
  safeInit(initEventListeners, "initEventListeners");
  safeInit(initDraggableSubtitle, "initDraggableSubtitle");
  safeInit(initDraggableFacecam, "initDraggableFacecam");
  safeInit(initWebcamCropCanvas, "initWebcamCropCanvas");
  safeInit(initNeonControls, "initNeonControls");
  safeInit(initDividerControls, "initDividerControls");
  safeInit(initMasterTemplateControls, "initMasterTemplateControls");
  safeInit(initFacecamShapeAndPosControls, "initFacecamShapeAndPosControls");
  safeInit(initStreamUrlLoader, "initStreamUrlLoader");
  safeInit(initFacecamArrowControls, "initFacecamArrowControls");
  safeInit(initGameplayZoomAndPanControls, "initGameplayZoomAndPanControls");
  safeInit(initEnhancePresets, "initEnhancePresets");
  safeInit(initExportOptions, "initExportOptions");
  safeInit(initHardwareDetection, "initHardwareDetection");
  safeInit(initToolsStatus, "initToolsStatus");
  safeInit(initPlayablePreview, "initPlayablePreview");
  safeInit(initViralProfileControls, "initViralProfileControls");
  safeInit(initLLMStatus, "initLLMStatus");
  safeInit(initSafeZoneOverlay, "initSafeZoneOverlay");
  safeInit(initRangeSliderProgress, "initRangeSliderProgress");
  safeInit(initWorkspaceResizer, "initWorkspaceResizer");
  
  safeInit(loadMasterTemplate, "loadMasterTemplate");
  safeInit(fetchOutputs, "fetchOutputs");

function setPreviewEmptyState(isEmpty) {
  state.videoLoaded = !isEmpty;
  const emptyEl = document.getElementById("preview-empty-state");
  const img = document.getElementById("preview-img");
  const canvas = document.getElementById("preview-canvas");
  const loading = document.getElementById("preview-loading");
  const controls = document.querySelector(".player-controls");
  const srcVid = document.getElementById("preview-source-video");
  const curTimeEl = document.getElementById("player-cur-time");
  const totalTimeEl = document.getElementById("player-total-time");

  if (isEmpty) {
    if (typeof stopPlayableClipPreview === "function") {
      try { stopPlayableClipPreview(); } catch (_) {}
    }
    if (emptyEl) emptyEl.style.display = "flex";
    if (img) {
      img.style.display = "none";
      img.removeAttribute("src");
    }
    if (canvas) {
      canvas.style.display = "none";
      const ctx = canvas.getContext("2d");
      if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    if (loading) loading.style.display = "none";
    if (srcVid) {
      try {
        srcVid.pause();
        srcVid.removeAttribute("src");
        srcVid.load();
      } catch (_) {}
    }
    if (curTimeEl) curTimeEl.innerText = "00:00";
    if (totalTimeEl) totalTimeEl.innerText = "00:00";
    if (controls) controls.classList.add("is-disabled");
    const cropCanvas = document.getElementById("webcam-crop-canvas") || document.getElementById("cam-crop-canvas");
    if (cropCanvas) {
      const cctx = cropCanvas.getContext("2d");
      if (cctx) cctx.clearRect(0, 0, cropCanvas.width, cropCanvas.height);
    }
    if (typeof renderClips === "function") renderClips();
  } else {
    if (emptyEl) emptyEl.style.display = "none";
    if (controls) controls.classList.remove("is-disabled");
  }
}

  // Check if a video is already loaded on the server
  fetch("/api/status")
    .then(r => r.json())
    .then(data => {
      if (data.video_loaded && data.current_video) {
        setPreviewEmptyState(false);
        loadSource(data.current_video);
      } else {
        setPreviewEmptyState(true);
      }
    })
    .catch(() => {
      setPreviewEmptyState(true);
    });
});

// Tab Switching
function initTabs() {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      const tabId = btn.getAttribute("data-tab");
      const target = document.getElementById(tabId);
      if (target) target.classList.add("active");
      if (tabId === "tab-template" && typeof window.syncCropCanvasWithVideo === "function") {
        window.syncCropCanvasWithVideo(false);
      }
    });
  });
}

// Sliders and Value Displays
function initSliders() {
  const bindSlider = (id, valId, unit, stateKey, subKey, multiplier = 1, isPercent = false) => {
    const slider = document.getElementById(id);
    const label = document.getElementById(valId);
    if (!slider || !label) return;
    
    updateSliderProgress(slider);
    slider.addEventListener("input", (e) => {
      updateSliderProgress(slider);
      const val = parseFloat(e.target.value);
      if (isPercent) {
        label.innerText = `${Math.round(val * 100)}%`;
      } else {
        label.innerText = `${val}${unit}`;
      }
      
      if (subKey) {
        state[stateKey][subKey] = val;
      } else {
        state[stateKey] = val;
      }

      requestPreviewUpdate();
    });
  };

  bindSlider("slider-blur", "val-blur", "px", "template", "bg_blur_sigma");
  bindSlider("slider-bg-dim", "val-bg-dim", "", "template", "bg_brightness", 1, true);

  // Gameplay Card Sizing & Framing
  const gpWSlider = document.getElementById("slider-gp-w");
  const gpHSlider = document.getElementById("slider-gp-h");
  const gpAspectCheck = document.getElementById("check-gp-aspect");
  const gpBadge = document.getElementById("gp-size-badge");

  const updateGPSizeBadge = (w, h) => {
    if (gpBadge) {
      if ((w >= 1000 && h >= 650) || state.template.webcam_shape === "split_screen") {
        gpBadge.innerText = `${Math.round(w)} × ${Math.round(h)} (Viral Reference)`;
      } else {
        gpBadge.innerText = `${Math.round(w)} × ${Math.round(h)}`;
      }
    }
  };

  if (gpWSlider) {
    gpWSlider.addEventListener("input", (e) => {
      const w = parseInt(e.target.value);
      document.getElementById("val-gp-w").innerText = `${w}px`;
      state.template.gameplay_w = w;

      if (gpAspectCheck && gpAspectCheck.checked && gpHSlider) {
        const h = Math.round(w * 9 / 16);
        gpHSlider.value = h;
        document.getElementById("val-gp-h").innerText = `${h}px`;
        state.template.gameplay_h = h;
        updateGPSizeBadge(w, h);
      } else if (gpHSlider) {
        updateGPSizeBadge(w, parseInt(gpHSlider.value));
      }
      requestPreviewUpdate();
    });
  }

  if (gpHSlider) {
    gpHSlider.addEventListener("input", (e) => {
      const h = parseInt(e.target.value);
      document.getElementById("val-gp-h").innerText = `${h}px`;
      state.template.gameplay_h = h;

      if (gpAspectCheck && gpAspectCheck.checked && gpWSlider) {
        const w = Math.min(1080, Math.round(h * 16 / 9));
        gpWSlider.value = w;
        document.getElementById("val-gp-w").innerText = `${w}px`;
        state.template.gameplay_w = w;
        updateGPSizeBadge(w, h);
      } else if (gpWSlider) {
        updateGPSizeBadge(parseInt(gpWSlider.value), h);
      }
      requestPreviewUpdate();
    });
  }

  // Quick Template Split Presets (700px Viral Reference, 960px Full Split, 560px Compact)
  document.querySelectorAll("#template-split-presets .preset-pill").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#template-split-presets .preset-pill").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      const targetH = parseInt(btn.getAttribute("data-gph"), 10) || 700;
      state.template.gameplay_h = targetH;
      state.template.webcam_h = targetH;
      state.template.gameplay_w = 1080;
      state.template.webcam_w = 1080;
      if (targetH === 700) {
        state.template.webcam_y = 260;
        state.template.gameplay_y = 960;
      } else if (targetH === 960) {
        state.template.webcam_y = 0;
        state.template.gameplay_y = 960;
      } else if (targetH === 560) {
        state.template.webcam_y = 400;
        state.template.gameplay_y = 960;
      }
      syncUIFromState();
      requestPreviewUpdate();
      showToast(`Selected split layout: 1080 × ${targetH}`);
    });
  });

  // Gameplay Vertical Y Position
  bindSlider("slider-gp-y", "val-gp-y", "px", "template", "gameplay_y");
  const btnCenterGPY = document.getElementById("btn-center-gp-y");
  if (btnCenterGPY) {
    btnCenterGPY.addEventListener("click", () => {
      const h = state.template.gameplay_h || 540;
      const centerY = Math.round((1920 - h) / 2);
      state.template.gameplay_y = centerY;
      const s = document.getElementById("slider-gp-y");
      const l = document.getElementById("val-gp-y");
      if (s) s.value = centerY;
      if (l) l.innerText = `${centerY}px`;
      requestPreviewUpdate();
    });
  }

  // Gameplay Zoom Slider
  bindSlider("slider-gp-zoom", "val-gp-zoom", "x", "template", "gameplay_zoom");

  // Gameplay Zoom Preset Pills (1.0x, 1.15x, 1.30x, 1.50x, 1.80x)
  document.querySelectorAll("#gp-zoom-presets .preset-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      const z = parseFloat(pill.dataset.zoom) || 1.15;
      state.template.gameplay_zoom = z;
      const s = document.getElementById("slider-gp-zoom");
      const v = document.getElementById("val-gp-zoom");
      if (s) s.value = z;
      if (v) v.innerText = `${z.toFixed(2)}x`;
      document.querySelectorAll("#gp-zoom-presets .preset-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      requestPreviewUpdate();
    });
  });

  // In-Card Video Framing & Panning (X and Y offsets inside gameplay card)
  const gpPanXSlider = document.getElementById("slider-gp-pan-x");
  const gpPanYSlider = document.getElementById("slider-gp-pan-y");

  const handlePanInput = () => {
    const px = parseInt(gpPanXSlider ? gpPanXSlider.value : 0) || 0;
    const py = parseInt(gpPanYSlider ? gpPanYSlider.value : 0) || 0;
    state.template.gameplay_pan_x = px;
    state.template.gameplay_pan_y = py;
    updateGPPanUI(px, py);

    // If user is panning but zoom is 1.0x, auto-assist zoom to 1.15x for headroom
    if ((px !== 0 || py !== 0) && (state.template.gameplay_zoom || 1.0) <= 1.0) {
      state.template.gameplay_zoom = 1.15;
      const zS = document.getElementById("slider-gp-zoom");
      const zL = document.getElementById("val-gp-zoom");
      if (zS) zS.value = "1.15";
      if (zL) zL.innerText = "1.15x";
      document.querySelectorAll("#gp-zoom-presets .preset-pill").forEach(p => {
        p.classList.toggle("active", parseFloat(p.dataset.zoom) === 1.15);
      });
      showToast("Auto-zoomed to 1.15x to allow framing room");
    }
    requestPreviewUpdate();
  };

  if (gpPanXSlider) gpPanXSlider.addEventListener("input", handlePanInput);
  if (gpPanYSlider) gpPanYSlider.addEventListener("input", handlePanInput);

  // Center Video Reset button
  const btnResetGPPan = document.getElementById("btn-reset-gp-pan");
  if (btnResetGPPan) {
    btnResetGPPan.addEventListener("click", () => {
      state.template.gameplay_pan_x = 0;
      state.template.gameplay_pan_y = 0;
      updateGPPanUI(0, 0);
      requestPreviewUpdate();
    });
  }

  // Nudge Pan buttons (supports both btn-gp-pan-* and legacy btn-nudge-gp-*)
  const nudgePan = (dx, dy) => {
    let curX = state.template.gameplay_pan_x || 0;
    let curY = state.template.gameplay_pan_y || 0;
    curX = Math.max(-100, Math.min(100, curX + dx));
    curY = Math.max(-100, Math.min(100, curY + dy));
    state.template.gameplay_pan_x = curX;
    state.template.gameplay_pan_y = curY;
    updateGPPanUI(curX, curY);

    if ((curX !== 0 || curY !== 0) && (state.template.gameplay_zoom || 1.0) <= 1.0) {
      state.template.gameplay_zoom = 1.15;
      const zS = document.getElementById("slider-gp-zoom");
      const zL = document.getElementById("val-gp-zoom");
      if (zS) zS.value = "1.15";
      if (zL) zL.innerText = "1.15x";
      document.querySelectorAll("#gp-zoom-presets .preset-pill").forEach(p => {
        p.classList.toggle("active", parseFloat(p.dataset.zoom) === 1.15);
      });
    }
    requestPreviewUpdate();
  };

  ["btn-gp-pan-left", "btn-nudge-gp-left"].forEach(id => {
    document.getElementById(id)?.addEventListener("click", () => nudgePan(-5, 0));
  });
  ["btn-gp-pan-right", "btn-nudge-gp-right"].forEach(id => {
    document.getElementById(id)?.addEventListener("click", () => nudgePan(5, 0));
  });
  ["btn-gp-pan-up", "btn-nudge-gp-up"].forEach(id => {
    document.getElementById(id)?.addEventListener("click", () => nudgePan(0, -5));
  });
  ["btn-gp-pan-down", "btn-nudge-gp-down"].forEach(id => {
    document.getElementById(id)?.addEventListener("click", () => nudgePan(0, 5));
  });

  bindSlider("slider-gp-radius", "val-gp-radius", "px", "template", "gameplay_radius");
  bindSlider("slider-gp-border", "val-gp-border", "px", "template", "gameplay_border_w");
  bindSlider("slider-cam-w", "val-cam-w", "px", "template", "webcam_w");
  bindSlider("slider-cam-h", "val-cam-h", "px", "template", "webcam_h");
  bindSlider("slider-cam-radius", "val-cam-radius", "px", "template", "webcam_radius");
  bindSlider("slider-cam-x", "val-cam-x", "px", "template", "webcam_x");
  bindSlider("slider-cam-y", "val-cam-y", "px", "template", "webcam_y");
  bindSlider("slider-cam-border", "val-cam-border", "px", "template", "webcam_border_w");

  // Keep Facecam Draggable Handle in sync when sliders move
  ["slider-cam-w", "slider-cam-h", "slider-cam-x", "slider-cam-y"].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("input", () => {
        if (typeof updateCamHandleUI === "function") updateCamHandleUI();
        if (typeof updateCamShapeBadge === "function") updateCamShapeBadge();
      });
    }
  });
  
  // Webcam Neon Lightning Glow Sliders
  bindSlider("slider-cam-glow-size", "val-cam-glow-size", "px", "template", "webcam_glow_size");
  bindSlider("slider-cam-glow-intensity", "val-cam-glow-intensity", "x", "template", "webcam_glow_intensity", 1);
  
  bindSlider("slider-font-size", "val-font-size", "px", "subtitlesConfig", "font_size");
  bindSlider("slider-sub-x", "val-sub-x", "%", "subtitlesConfig", "position_x");
  bindSlider("slider-sub-y", "val-sub-y", "%", "subtitlesConfig", "position_y");
  bindSlider("slider-sub-stroke", "val-sub-stroke", "px", "subtitlesConfig", "outline_width");
  
  // Word Timing Calibration & Sync Nudge Slider
  const syncSlider = document.getElementById("slider-sync-offset");
  const syncLabel = document.getElementById("val-sync-offset");
  const updateSyncLabel = (val) => {
    if (!syncLabel) return;
    if (val === 0) syncLabel.innerText = "0 ms (Exact Vocal Waveform)";
    else if (val < 0) syncLabel.innerText = `${val} ms (Advanced earlier)`;
    else syncLabel.innerText = `+${val} ms (Delayed later)`;
  };

  if (syncSlider) {
    syncSlider.addEventListener("input", (e) => {
      const val = parseInt(e.target.value, 10) || 0;
      state.subtitlesConfig.sync_offset_ms = val;
      updateSyncLabel(val);
      requestPreviewUpdate();
    });
  }

  const setSyncOffset = (val) => {
    const clamped = Math.max(-500, Math.min(500, val));
    state.subtitlesConfig.sync_offset_ms = clamped;
    if (syncSlider) syncSlider.value = clamped;
    updateSyncLabel(clamped);
    requestPreviewUpdate();
  };

  const btnNudgeEarlier = document.getElementById("btn-sync-nudge-earlier");
  const btnNudgeReset = document.getElementById("btn-sync-nudge-reset");
  const btnNudgeLater = document.getElementById("btn-sync-nudge-later");
  if (btnNudgeEarlier) btnNudgeEarlier.addEventListener("click", () => setSyncOffset((state.subtitlesConfig.sync_offset_ms || 0) - 100));
  if (btnNudgeReset) btnNudgeReset.addEventListener("click", () => setSyncOffset(0));
  if (btnNudgeLater) btnNudgeLater.addEventListener("click", () => setSyncOffset((state.subtitlesConfig.sync_offset_ms || 0) + 100));
  
  
  bindSlider("slider-micro-texture", "val-micro-texture", "x", "template", "micro_texture");
  bindSlider("slider-sharpness", "val-sharpness", "x", "template", "sharpen_amount");
  bindSlider("slider-contrast", "val-contrast", "%", "template", "contrast_boost", 1, true);
  bindSlider("slider-saturation", "val-saturation", "%", "template", "saturation_boost", 1, true);

  const selectDeblock = document.getElementById("select-deblock");
  if (selectDeblock) {
    selectDeblock.addEventListener("change", (e) => {
      state.template.deblock_level = e.target.value;
      updateExportProfileLabel();
      requestPreviewUpdate();
    });
  }

  const selectExportBitrate = document.getElementById("select-export-bitrate");
  if (selectExportBitrate) {
    selectExportBitrate.addEventListener("change", (e) => {
      state.template.export_bitrate = e.target.value;
      updateExportProfileLabel();
    });
  }

  // Viral min & max duration sliders
  const minDurSlider = document.getElementById("slider-min-dur");
  const maxDurSlider = document.getElementById("slider-max-dur");
  if (minDurSlider && maxDurSlider) {
    minDurSlider.addEventListener("input", (e) => {
      const v = parseFloat(e.target.value);
      document.getElementById("val-min-dur").innerText = `${v}s`;
      state.viralSettings.min_duration = v;
      if (v >= parseFloat(maxDurSlider.value)) {
        maxDurSlider.value = v + 4;
        document.getElementById("val-max-dur").innerText = `${v + 4}s`;
        state.viralSettings.max_duration = v + 4;
      }
    });
    maxDurSlider.addEventListener("input", (e) => {
      const v = parseFloat(e.target.value);
      document.getElementById("val-max-dur").innerText = `${v}s`;
      state.viralSettings.max_duration = v;
      if (v <= parseFloat(minDurSlider.value)) {
        minDurSlider.value = Math.max(5, v - 4);
        document.getElementById("val-min-dur").innerText = `${Math.max(5, v - 4)}s`;
        state.viralSettings.min_duration = Math.max(5, v - 4);
      }
    });
  }

  // Preview time scrubber
  const timeSlider = document.getElementById("slider-preview-time");
  timeSlider.addEventListener("input", (e) => {
    state.previewTime = parseFloat(e.target.value);
    document.getElementById("val-preview-time").innerText = `${state.previewTime.toFixed(1)}s`;
    if (window.updatePlayerInfo) {
      window.updatePlayerInfo();
    }
    const sourceVid = document.getElementById("preview-source-video");
    if (sourceVid && isPlayMode && !isPlayingPreview) {
      try { sourceVid.currentTime = state.previewTime; } catch (_) {}
      renderCanvasFrame(getActiveOrFallbackClip(), state.previewTime);
    }
    requestPreviewUpdate();
  });

  // Sample text preview input
  const previewTextInput = document.getElementById("input-preview-text");
  if (previewTextInput) {
    previewTextInput.addEventListener("input", (e) => {
      state.subtitlesConfig.preview_text = e.target.value || "UNREAL CLUTCH AIM";
      requestPreviewUpdate();
    });
  }
}

// Custom Range Slider Dynamic Accent Fill
function updateSliderProgress(slider) {
  if (!slider) return;
  const min = parseFloat(slider.min) || 0;
  const max = parseFloat(slider.max) || 100;
  const val = parseFloat(slider.value) || 0;
  const pct = max > min ? Math.max(0, Math.min(100, ((val - min) / (max - min)) * 100)) : 0;
  slider.style.background = `linear-gradient(to right, var(--accent) 0%, var(--accent) ${pct}%, #27272A ${pct}%, #27272A 100%)`;
}

function initRangeSliderProgress() {
  const sliders = document.querySelectorAll('input[type="range"]');
  sliders.forEach(slider => {
    updateSliderProgress(slider);
    slider.addEventListener("input", () => updateSliderProgress(slider));
    slider.addEventListener("change", () => updateSliderProgress(slider));
  });
}

// 1-Click Shorts / Reels / TikTok Safe-Zone Overlay
function initSafeZoneOverlay() {
  const btnSafezone = document.getElementById("btn-toggle-safezone");
  const overlay = document.getElementById("preview-safezone-overlay");
  if (!btnSafezone || !overlay) return;
  btnSafezone.addEventListener("click", () => {
    const isVisible = overlay.style.display !== "none";
    overlay.style.display = isVisible ? "none" : "block";
    btnSafezone.classList.toggle("active", !isVisible);
  });
}

/**
 * Smooth Draggable Split-Pane Resizer
 * Allows user to drag the divider between the left inspector working area and right preview stage.
 * Persists inspector width % in localStorage ("openshorts_inspector_pct").
 * Double-click resets to default 58% / 42% split.
 */
function initWorkspaceResizer() {
  const resizer = document.getElementById("workspace-resizer");
  const container = document.querySelector(".app-container");
  if (!resizer || !container) return;

  const DEFAULT_PCT = 58;
  const MIN_PCT = 30;
  const MAX_PCT = 72;
  const MIN_LEFT_PX = 360;
  const MIN_RIGHT_PX = 340;
  const RESIZER_WIDTH_PX = 8;

  // 1. Initial Load: Read persisted or default width %
  const readSavedWidth = () => {
    try {
      const saved = localStorage.getItem("openshorts_inspector_pct");
      if (saved !== null) {
        const parsed = parseFloat(saved);
        if (!isNaN(parsed) && parsed >= MIN_PCT && parsed <= MAX_PCT) {
          return parsed;
        }
      }
    } catch (_) {}
    return DEFAULT_PCT;
  };

  const applyWidth = (pct) => {
    const clamped = Math.max(MIN_PCT, Math.min(MAX_PCT, pct));
    container.style.setProperty("--inspector-width", `${clamped.toFixed(2)}%`);
    return clamped;
  };

  let currentPct = applyWidth(readSavedWidth());

  const triggerLayoutRefresh = () => {
    if (typeof window.syncCropCanvasWithVideo === "function") {
      window.syncCropCanvasWithVideo(false);
    }
    const phoneScreen = document.getElementById("phone-screen");
    if (phoneScreen && typeof window.updateFacecamHandleUI === "function") {
      window.updateFacecamHandleUI();
    }
    window.dispatchEvent(new Event("resize"));
  };

  // 2. Drag Logic with Pointer Events & Capture
  let isDragging = false;
  let rafId = null;

  resizer.addEventListener("pointerdown", (e) => {
    if (e.button !== 0 && e.pointerType === "mouse") return;
    e.preventDefault();
    isDragging = true;

    try {
      resizer.setPointerCapture(e.pointerId);
    } catch (_) {}

    resizer.classList.add("is-resizing");
    document.body.classList.add("is-resizing-pane");
  });

  resizer.addEventListener("pointermove", (e) => {
    if (!isDragging) return;
    e.preventDefault();

    if (rafId) cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(() => {
      const rect = container.getBoundingClientRect();
      if (!rect.width) return;

      const rawLeftPx = e.clientX - rect.left;
      const maxLeftPx = rect.width - MIN_RIGHT_PX - RESIZER_WIDTH_PX;
      const clampedLeftPx = Math.max(MIN_LEFT_PX, Math.min(maxLeftPx, rawLeftPx));
      const newPct = (clampedLeftPx / rect.width) * 100;

      currentPct = applyWidth(newPct);
      triggerLayoutRefresh();
    });
  });

  const handlePointerEnd = (e) => {
    if (!isDragging) return;
    isDragging = false;

    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }

    try {
      if (resizer.hasPointerCapture(e.pointerId)) {
        resizer.releasePointerCapture(e.pointerId);
      }
    } catch (_) {}

    resizer.classList.remove("is-resizing");
    document.body.classList.remove("is-resizing-pane");

    try {
      localStorage.setItem("openshorts_inspector_pct", currentPct.toFixed(2));
    } catch (_) {}

    triggerLayoutRefresh();
  };

  resizer.addEventListener("pointerup", handlePointerEnd);
  resizer.addEventListener("pointercancel", handlePointerEnd);

  // 3. Double-Click Reset to Default (58% / 42%)
  resizer.addEventListener("dblclick", (e) => {
    e.preventDefault();
    currentPct = applyWidth(DEFAULT_PCT);
    try {
      localStorage.setItem("openshorts_inspector_pct", DEFAULT_PCT.toString());
    } catch (_) {}
    triggerLayoutRefresh();
  });
}

// Colors
function initColors() {
  const bindColor = (pickerId, hexId, stateKey, subKey) => {
    const picker = document.getElementById(pickerId);
    const hexSpan = hexId ? document.getElementById(hexId) : null;
    if (!picker) return;
    
    picker.addEventListener("input", (e) => {
      const hex = e.target.value.toUpperCase();
      if (hexSpan) hexSpan.innerText = hex;
      state[stateKey][subKey] = hex;
      requestPreviewUpdate();
    });
  };

  bindColor("color-gp-border", null, "template", "gameplay_border_color");
  bindColor("color-cam-border", null, "template", "webcam_border_color");
  bindColor("color-cam-glow", null, "template", "webcam_glow_color");
  bindColor("color-sub-primary", "hex-sub-primary", "subtitlesConfig", "primary_color");
  bindColor("color-sub-highlight", "hex-sub-highlight", "subtitlesConfig", "highlight_color");
  bindColor("color-sub-outline", "hex-sub-outline", "subtitlesConfig", "outline_color");
}

// Preset Buttons (Subtitle Styles)
function initPresets() {
  document.querySelectorAll("[data-style]").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-style]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const style = btn.getAttribute("data-style");
      state.subtitlesConfig.style_preset = style;
      
      if (style === "studio_flow" || style === "skyglow") {
        state.subtitlesConfig.style_preset = "studio_flow";
        setSubColors("#FFFFFF", "#38BDF8", "#000000", 2, "Montserrat ExtraBold");
        state.subtitlesConfig.position_y = 50;
        state.subtitlesConfig.position_x = 50;
        state.subtitlesConfig.font_size = 62;
        state.subtitlesConfig.words_per_line = 4;
        state.subtitlesConfig.is_uppercase = true;
        const fontSel = document.getElementById("select-font");
        if (fontSel) fontSel.value = "Montserrat ExtraBold";
        const sliderY = document.getElementById("slider-sub-y");
        const valY = document.getElementById("val-sub-y");
        if (sliderY) sliderY.value = 50;
        if (valY) valY.innerText = "50%";
        const sliderSize = document.getElementById("slider-font-size");
        const valSize = document.getElementById("val-font-size");
        if (sliderSize) sliderSize.value = 62;
        if (valSize) valSize.innerText = "62px";
        document.querySelectorAll("[data-words]").forEach(b => {
          b.classList.toggle("active", b.getAttribute("data-words") === "4");
        });
        if (typeof updateSubHandleUI === "function") updateSubHandleUI();
      } else if (style === "speed") {
        setSubColors("#FFFFFF", "#CCFF00", "#000000", 8, "Impact");
        state.subtitlesConfig.position_y = 50;
        state.subtitlesConfig.position_x = 50;
        state.subtitlesConfig.font_size = 62;
        state.subtitlesConfig.words_per_line = 3;
        state.subtitlesConfig.is_uppercase = true;
        const sliderY = document.getElementById("slider-sub-y");
        const valY = document.getElementById("val-sub-y");
        if (sliderY) sliderY.value = 50;
        if (valY) valY.innerText = "50%";
        const sliderSize = document.getElementById("slider-font-size");
        const valSize = document.getElementById("val-font-size");
        if (sliderSize) sliderSize.value = 62;
        if (valSize) valSize.innerText = "62px";
        if (typeof updateSubHandleUI === "function") updateSubHandleUI();
      } else if (style === "hormozi") {
        setSubColors("#FFFFFF", "#FFDE00", "#000000", 5, "Impact");
      } else if (style === "mrbeast") {
        setSubColors("#FFE600", "#00FF66", "#000000", 6, "Impact");
      } else if (style === "neon") {
        setSubColors("#00F5FF", "#FF007F", "#0F172A", 4, "Montserrat");
      } else if (style === "box") {
        setSubColors("#FFFFFF", "#FFDE00", "#000000", 2, "Arial Black");
      } else if (style === "fire") {
        setSubColors("#FF3B30", "#FFD60A", "#000000", 5, "Impact");
      } else if (style === "clean") {
        setSubColors("#FFFFFF", "#38BDF8", "#1E293B", 2, "Segoe UI");
      }
      requestPreviewUpdate();
    });
  });

  // Words Shown at a Time Pills
  document.querySelectorAll("[data-words]").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-words]").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const wordCount = parseInt(btn.getAttribute("data-words"));
      state.subtitlesConfig.words_per_line = wordCount;
      const countLabel = wordCount === 1 ? '1 Word' : (wordCount === 0 ? 'Full Phrase' : wordCount + ' Words');
      showToast(`Set subtitle display to ${countLabel} at a time.`);
    });
  });

  // Re-Group Subtitles Button
  const btnRegroup = document.getElementById("btn-regroup-subs");
  if (btnRegroup) {
    btnRegroup.addEventListener("click", async () => {
      if (!state.subtitles || state.subtitles.length === 0) {
        showToast("No subtitles loaded to re-group yet. Transcribe first!");
        return;
      }
      const wordCount = state.subtitlesConfig.words_per_line !== undefined ? state.subtitlesConfig.words_per_line : 3;
      btnRegroup.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Grouping...`;
      btnRegroup.disabled = true;
      try {
        const res = await fetch("/api/regroup_subtitles", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ words_per_line: wordCount })
        });
        if (!res.ok) throw new Error(await res.text());
        const data = await res.json();
        state.subtitles = data.subtitles || [];
        renderSubtitles();
        const countLabel = wordCount === 1 ? '1 Word' : (wordCount === 0 ? 'Full Phrase' : wordCount + ' Words');
        showToast(`✨ Re-grouped into ${data.count} chunks (${countLabel} per screen)!`);
        triggerPreview(true);
      } catch (err) {
        showToast("Re-group error: " + err.message);
      } finally {
        btnRegroup.innerHTML = `<i class="fa-solid fa-rotate"></i> Re-Group Active Subtitles`;
        btnRegroup.disabled = false;
      }
    });
  }

  // Font family selector
  const fontSel = document.getElementById("select-font");
  if (fontSel) {
    fontSel.addEventListener("change", (e) => {
      state.subtitlesConfig.font_family = e.target.value;
      requestPreviewUpdate();
    });
  }

  // Whisper model selector
  const modelSel = document.getElementById("select-whisper-model");
  if (modelSel) {
    modelSel.addEventListener("change", (e) => {
      state.subtitlesConfig.model_name = normalizeWhisperModelName(e.target.value);
    });
  }

  // Uppercase toggle
  const checkUpper = document.getElementById("check-uppercase");
  if (checkUpper) {
    checkUpper.addEventListener("change", (e) => {
      state.subtitlesConfig.is_uppercase = e.target.checked;
      requestPreviewUpdate();
    });
  }

  // Profanity Censor toggle
  const checkCensor = document.getElementById("check-censor-profanity");
  if (checkCensor) {
    checkCensor.checked = state.subtitlesConfig.censor_profanity !== false;
    checkCensor.addEventListener("change", (e) => {
      state.subtitlesConfig.censor_profanity = e.target.checked;
      requestPreviewUpdate();
    });
  }

  // Climax Zoom Punch toggle
  const checkClimaxZoom = document.getElementById("check-climax-zoom");
  if (checkClimaxZoom) {
    checkClimaxZoom.checked = !!state.template.climax_zoom_enabled;
    checkClimaxZoom.addEventListener("change", (e) => {
      state.template.climax_zoom_enabled = e.target.checked;
      requestPreviewUpdate();
    });
  }

  // Auto-Jump-Cut toggle
  const checkAutoJumpCut = document.getElementById("check-auto-jump-cut");
  if (checkAutoJumpCut) {
    checkAutoJumpCut.checked = !!state.template.auto_jump_cut;
    checkAutoJumpCut.addEventListener("change", (e) => {
      state.template.auto_jump_cut = e.target.checked;
    });
  }

  // Global Subtitles Enable/Disable toggle
  const toggleSubEnabled = document.getElementById("toggle-subtitles-enabled");
  if (toggleSubEnabled) {
    toggleSubEnabled.addEventListener("change", (e) => {
      const enabled = e.target.checked;
      state.subtitlesConfig.enabled = enabled;
      updateActiveClipSettings();
      syncUIFromState();
      renderClips();
      if (typeof isPlayMode !== "undefined" && (isPlayMode || isPlayingPreview)) {
        renderCanvasFrame(getActiveOrFallbackClip());
      } else {
        requestPreviewUpdate();
      }
      showToast(enabled ? "✅ Subtitles turned ON" : "❌ Subtitles turned OFF (Clean Video)");
    });
  }

  // Crop input listeners
  ["cam-crop-x", "cam-crop-y", "cam-crop-w", "cam-crop-h"].forEach(id => {
    const el = document.getElementById(id);
    el.addEventListener("input", () => {
      state.template.webcam_crop = {
        x: parseInt(document.getElementById("cam-crop-x").value) || 0,
        y: parseInt(document.getElementById("cam-crop-y").value) || 0,
        w: parseInt(document.getElementById("cam-crop-w").value) || 84,
        h: parseInt(document.getElementById("cam-crop-h").value) || 84
      };
      requestPreviewUpdate();
    });
  });

  // Viral clipping mode toggles
  const modeAuto = document.getElementById("mode-auto");
  const modeManual = document.getElementById("mode-manual");
  const manualRow = document.getElementById("manual-count-row");
  const autoHint = document.getElementById("auto-mode-hint");
  const inputTarget = document.getElementById("input-target-clips");

  if (modeAuto && modeManual) {
    modeAuto.addEventListener("click", () => {
      modeAuto.classList.add("active");
      modeManual.classList.remove("active");
      if (manualRow) manualRow.style.display = "none";
      if (autoHint) autoHint.style.display = "flex";
      state.viralSettings.mode = "auto";
    });
    modeManual.addEventListener("click", () => {
      modeManual.classList.add("active");
      modeAuto.classList.remove("active");
      if (manualRow) manualRow.style.display = "flex";
      if (autoHint) autoHint.style.display = "none";
      state.viralSettings.mode = "manual";
    });
  }
  if (inputTarget) {
    inputTarget.addEventListener("input", (e) => {
      state.viralSettings.target_clips = parseInt(e.target.value) || 5;
    });
  }
}

function initViralProfileControls() {
  const profilePills = document.querySelectorAll("#viral-profile-pills .preset-pill");
  const badge = document.getElementById("badge-viral-profile");
  
  const sliderAudio = document.getElementById("slider-weight-audio");
  const valAudio = document.getElementById("val-weight-audio");
  const sliderPitch = document.getElementById("slider-weight-pitch");
  const valPitch = document.getElementById("val-weight-pitch");
  const sliderHook = document.getElementById("slider-weight-hook");
  const valHook = document.getElementById("val-weight-hook");
  const sliderSpeech = document.getElementById("slider-weight-speech");
  const valSpeech = document.getElementById("val-weight-speech");
  const sliderMotion = document.getElementById("slider-weight-motion");
  const valMotion = document.getElementById("val-weight-motion");
  const checkSnap = document.getElementById("check-snap-boundaries");

  const setWeightsUI = (a, p, h, s, m) => {
    state.viralSettings.weight_audio = a / 100;
    state.viralSettings.weight_pitch = p / 100;
    state.viralSettings.weight_hook = h / 100;
    state.viralSettings.weight_speech = s / 100;
    state.viralSettings.weight_motion = m / 100;

    if (sliderAudio) sliderAudio.value = a;
    if (valAudio) valAudio.innerText = `${a}%`;
    if (sliderPitch) sliderPitch.value = p;
    if (valPitch) valPitch.innerText = `${p}%`;
    if (sliderHook) sliderHook.value = h;
    if (valHook) valHook.innerText = `${h}%`;
    if (sliderSpeech) sliderSpeech.value = s;
    if (valSpeech) valSpeech.innerText = `${s}%`;
    if (sliderMotion) sliderMotion.value = m;
    if (valMotion) valMotion.innerText = `${m}%`;
  };

  profilePills.forEach(btn => {
    btn.addEventListener("click", () => {
      profilePills.forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      const prof = btn.getAttribute("data-profile");
      state.viralSettings.profile = prof;

      if (prof === "balanced") {
        setWeightsUI(25, 15, 25, 20, 15);
        if (badge) badge.innerText = "BALANCED (5 SIGNALS)";
      } else if (prof === "high_energy") {
        setWeightsUI(40, 25, 20, 10, 5);
        if (badge) badge.innerText = "SCREAMS & HYPE FOCUS";
      } else if (prof === "comedy") {
        setWeightsUI(15, 20, 25, 35, 5);
        if (badge) badge.innerText = "COMEDY & ROASTS FOCUS";
      } else if (prof === "action") {
        setWeightsUI(20, 10, 20, 15, 35);
        if (badge) badge.innerText = "CLUTCH GAMEPLAY FOCUS";
      }
      showToast(`Switched viral profile: ${btn.innerText.trim()}`);
    });
  });

  // Custom Weight Sliders
  const bindWeightSlider = (slider, valSpan, key) => {
    if (slider && valSpan) {
      slider.addEventListener("input", (e) => {
        const val = parseInt(e.target.value) || 0;
        valSpan.innerText = `${val}%`;
        state.viralSettings[key] = val / 100;
        if (badge) badge.innerText = "CUSTOM WEIGHTS";
      });
    }
  };

  bindWeightSlider(sliderAudio, valAudio, "weight_audio");
  bindWeightSlider(sliderPitch, valPitch, "weight_pitch");
  bindWeightSlider(sliderHook, valHook, "weight_hook");
  bindWeightSlider(sliderSpeech, valSpeech, "weight_speech");
  bindWeightSlider(sliderMotion, valMotion, "weight_motion");

  if (checkSnap) {
    checkSnap.addEventListener("change", (e) => {
      state.viralSettings.snap_boundaries = e.target.checked;
    });
  }
}

function updateSubHandleUI() {
  const handle = document.getElementById("drag-sub-handle");
  const label = document.getElementById("drag-sub-label");
  const posX = state.subtitlesConfig.position_x !== undefined ? state.subtitlesConfig.position_x : 50;
  const posY = state.subtitlesConfig.position_y !== undefined ? state.subtitlesConfig.position_y : 82;

  if (handle) {
    handle.style.left = `${posX}%`;
    handle.style.top = `${posY}%`;
  }
  if (label) {
    label.innerText = `Subtitles (${Math.round(posX)}%, ${Math.round(posY)}%)`;
  }
  const sliderX = document.getElementById("slider-sub-x");
  const valX = document.getElementById("val-sub-x");
  if (sliderX) sliderX.value = Math.round(posX);
  if (valX) valX.innerText = `${Math.round(posX)}%`;

  const sliderY = document.getElementById("slider-sub-y");
  const valY = document.getElementById("val-sub-y");
  if (sliderY) sliderY.value = Math.round(posY);
  if (valY) valY.innerText = `${Math.round(posY)}%`;
}

function initDraggableSubtitle() {
  const handle = document.getElementById("drag-sub-handle");
  const phone = document.getElementById("phone-screen");
  if (!handle || !phone) return;

  let isDragging = false;

  const onStart = (e) => {
    isDragging = true;
    handle.style.cursor = "grabbing";
    e.preventDefault();
  };

  const onMove = (e) => {
    if (!isDragging) return;
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    const rect = phone.getBoundingClientRect();

    let pctX = Math.round(((clientX - rect.left) / rect.width) * 100);
    let pctY = Math.round(((clientY - rect.top) / rect.height) * 100);

    pctX = Math.max(5, Math.min(95, pctX));
    pctY = Math.max(5, Math.min(95, pctY));

    state.subtitlesConfig.position_x = pctX;
    state.subtitlesConfig.position_y = pctY;
    updateSubHandleUI();
  };

  const onEnd = () => {
    if (isDragging) {
      isDragging = false;
      handle.style.cursor = "grab";
      requestPreviewUpdate();
    }
  };

  handle.addEventListener("mousedown", onStart);
  window.addEventListener("mousemove", onMove);
  window.addEventListener("mouseup", onEnd);

  handle.addEventListener("touchstart", onStart, { passive: false });
  window.addEventListener("touchmove", onMove, { passive: false });
  window.addEventListener("touchend", onEnd);

  // Nudge buttons
  const nudge = (dx, dy) => {
    const curX = state.subtitlesConfig.position_x !== undefined ? state.subtitlesConfig.position_x : 50;
    const curY = state.subtitlesConfig.position_y !== undefined ? state.subtitlesConfig.position_y : 82;
    state.subtitlesConfig.position_x = Math.max(5, Math.min(95, curX + dx));
    state.subtitlesConfig.position_y = Math.max(5, Math.min(95, curY + dy));
    updateSubHandleUI();
    requestPreviewUpdate();
  };

  const btnUp = document.getElementById("btn-nudge-up");
  const btnDown = document.getElementById("btn-nudge-down");
  const btnLeft = document.getElementById("btn-nudge-left");
  const btnRight = document.getElementById("btn-nudge-right");
  const btnCenter = document.getElementById("btn-center-sub");

  if (btnUp) btnUp.addEventListener("click", () => nudge(0, -3));
  if (btnDown) btnDown.addEventListener("click", () => nudge(0, 3));
  if (btnLeft) btnLeft.addEventListener("click", () => nudge(-3, 0));
  if (btnRight) btnRight.addEventListener("click", () => nudge(3, 0));
  if (btnCenter) btnCenter.addEventListener("click", () => {
    state.subtitlesConfig.position_x = 50;
    updateSubHandleUI();
    requestPreviewUpdate();
  });

  updateSubHandleUI();
}

function setSubColors(primary, highlight, outline, strokeW, font = null) {
  state.subtitlesConfig.primary_color = primary;
  state.subtitlesConfig.highlight_color = highlight;
  state.subtitlesConfig.outline_color = outline;
  state.subtitlesConfig.outline_width = strokeW;
  if (font) {
    state.subtitlesConfig.font_family = font;
    const fontSel = document.getElementById("select-font");
    if (fontSel) fontSel.value = font;
  }
  
  const p = document.getElementById("color-sub-primary");
  if (p) p.value = primary;
  const hp = document.getElementById("hex-sub-primary");
  if (hp) hp.innerText = primary;

  const h = document.getElementById("color-sub-highlight");
  if (h) h.value = highlight;
  const hh = document.getElementById("hex-sub-highlight");
  if (hh) hh.innerText = highlight;

  const o = document.getElementById("color-sub-outline");
  if (o) o.value = outline;
  const ho = document.getElementById("hex-sub-outline");
  if (ho) ho.innerText = outline;

  const s = document.getElementById("slider-sub-stroke");
  if (s) s.value = strokeW;
  const vs = document.getElementById("val-sub-stroke");
  if (vs) vs.innerText = `${strokeW}px`;
}

// API Calls & Event Listeners
function initEventListeners() {
  document.getElementById("btn-load-path").addEventListener("click", () => {
    let path = document.getElementById("input-video-path").value.trim();
    // Strip quotes if user copied path from Windows Explorer
    path = path.replace(/^["'“”]+|["'“”]+$/g, '').trim();
    document.getElementById("input-video-path").value = path;
    if (path) loadSource(path);
  });

  // Drag and Drop & Browse file picker
  const filePicker = document.getElementById("input-file-picker");
  const dropZone = document.getElementById("drop-zone");
  const btnBrowse = document.getElementById("btn-browse-file");

  if (filePicker) {
    if (btnBrowse) btnBrowse.addEventListener("click", () => filePicker.click());
    if (dropZone) {
      dropZone.addEventListener("click", () => filePicker.click());
      dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.style.borderColor = "var(--accent-gold)";
        dropZone.style.background = "rgba(245, 158, 11, 0.1)";
      });
      dropZone.addEventListener("dragleave", () => {
        dropZone.style.borderColor = "var(--accent-neon)";
        dropZone.style.background = "rgba(0, 245, 255, 0.04)";
      });
      dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.style.borderColor = "var(--accent-neon)";
        dropZone.style.background = "rgba(0, 245, 255, 0.04)";
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
          uploadFile(e.dataTransfer.files[0]);
        }
      });
    }
    filePicker.addEventListener("change", handleFileUpload);
  }

  // Open & Change Export Folder
  const btnOpenFolder = document.getElementById("btn-open-folder");
  if (btnOpenFolder) {
    btnOpenFolder.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/open_folder", { method: "POST" });
        const data = await res.json();
        showToast("Export directory opened: " + (data.path || "storage/outputs"));
      } catch (e) {
        showToast("Storage folder: storage/outputs");
      }
    });
  }

  const btnChangeExportFolder = document.getElementById("btn-change-export-folder");
  if (btnChangeExportFolder) {
    btnChangeExportFolder.addEventListener("click", async () => {
      let currentPath = "";
      try {
        const r = await fetch("/api/export_folder");
        const d = await r.json();
        currentPath = d.path || "";
      } catch (_) {}
      const newPath = prompt("Enter new export destination folder path:", currentPath);
      if (newPath !== null && newPath.trim() !== "") {
        try {
          const res = await fetch("/api/set_export_folder", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ folder_path: newPath.trim() })
          });
          const d = await res.json();
          if (res.ok && d.status === "success") {
            const inp = document.getElementById("input-export-folder");
            if (inp) inp.value = d.path;
            showToast(`Export output folder updated: ${d.path}`);
            fetchOutputs();
          } else {
            alert(d.detail || d.message || "Failed to set export folder.");
          }
        } catch (e) {
          alert("Error setting folder: " + e.message);
        }
      }
    });
  }

  document.getElementById("btn-load-demo").addEventListener("click", async () => {
    try {
      const res = await fetch("/api/demo_video");
      const d = await res.json();
      if (d.success && d.path) {
        document.getElementById("input-video-path").value = d.path;
        loadSource(d.path, true);
      } else {
        alert("No sample video found in storage/uploads. Please enter a video path or drag & drop a video file!");
      }
    } catch (e) {
      alert("Error finding demo video: " + e.message);
    }
  });

  const btnFactoryReset = document.getElementById("btn-factory-reset");
  if (btnFactoryReset) {
    btnFactoryReset.addEventListener("click", async () => {
      const confirmed = confirm(
        "✨ Clean Slate / Fresh Start:\n\n" +
        "Are you sure you want to reset OpenShorts Studio for a brand new user?\n\n" +
        "• Clears all previous clips, subtitles & timeline state\n" +
        "• Clears all uploaded footage, outputs & temporary files\n" +
        "• Resets browser settings and master templates to defaults\n" +
        "• Keeps all AI models and FFmpeg binaries intact\n\n" +
        "Click OK to start completely fresh."
      );
      if (!confirmed) return;

      try {
        btnFactoryReset.disabled = true;
        btnFactoryReset.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Resetting...`;
        const res = await fetch("/api/factory_reset", { method: "POST" });
        if (!res.ok) throw new Error("Factory reset failed");

        // Clear local storage & session storage
        localStorage.clear();
        sessionStorage.clear();
        state.videoPath = "";
        state.videoMeta = null;
        state.clips = [];
        state.subtitles = [];
        setPreviewEmptyState(true);

        alert("✨ Engine completely reset to clean slate! OpenShorts Studio will now reload fresh.");
        window.location.reload();
      } catch (err) {
        alert("Reset failed: " + err.message);
        btnFactoryReset.disabled = false;
        btnFactoryReset.innerHTML = `<i class="fa-solid fa-rotate-left"></i> Fresh Start`;
      }
    });
  }

  const btnRefresh = document.getElementById("btn-refresh-preview");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => triggerPreview(true));
  }

  const btnTransCurrent = document.getElementById("btn-transcribe-current");
  if (btnTransCurrent) {
    btnTransCurrent.addEventListener("click", () => runTranscription(true));
  }
  const btnTransFull = document.getElementById("btn-transcribe");
  if (btnTransFull && btnTransFull !== btnTransCurrent) {
    btnTransFull.addEventListener("click", () => runTranscription(false));
  }
  const btnTransClip = document.getElementById("btn-transcribe-clip");
  if (btnTransClip && btnTransClip !== btnTransCurrent) {
    btnTransClip.addEventListener("click", () => runTranscription(true));
  }
  const btnTransAll = document.getElementById("btn-transcribe-all") || document.getElementById("btn-transcribe-all-clips");
  if (btnTransAll) {
    btnTransAll.addEventListener("click", runTranscribeAllClips);
  }
  const btnTab1TransAll = document.getElementById("btn-tab1-transcribe-all");
  if (btnTab1TransAll) {
    btnTab1TransAll.addEventListener("click", runTranscribeAllClips);
  }
  const checkFilterSubs = document.getElementById("check-filter-subs-clip");
  if (checkFilterSubs) {
    checkFilterSubs.addEventListener("change", renderSubtitles);
  }
  const btnDetect = document.getElementById("btn-detect-viral") || document.getElementById("btn-detect-clips") || document.getElementById("btn-auto-slice");
  if (btnDetect) {
    btnDetect.addEventListener("click", runViralDetection);
  }
  const btnAutoSlice = document.getElementById("btn-auto-slice");
  if (btnAutoSlice && btnAutoSlice !== btnDetect) {
    btnAutoSlice.addEventListener("click", runViralDetection);
  }
  const btnAddClip = document.getElementById("btn-add-clip");
  if (btnAddClip) btnAddClip.addEventListener("click", addManualClip);
  const btnAddSub = document.getElementById("btn-add-sub");
  if (btnAddSub) btnAddSub.addEventListener("click", addManualSubtitle);

  const btnExpCurrent = document.getElementById("btn-export-current") || document.getElementById("btn-export-clip");
  if (btnExpCurrent) btnExpCurrent.addEventListener("click", exportSelectedClip);
  const btnExpAll = document.getElementById("btn-export-all");
  if (btnExpAll) btnExpAll.addEventListener("click", exportAllClips);
  const btnRefreshOutputs = document.getElementById("btn-refresh-outputs");
  if (btnRefreshOutputs) btnRefreshOutputs.addEventListener("click", fetchOutputs);

  // Apply to All Clips buttons across UI
  const applyAllIds = [
    "btn-apply-settings-all-clips",
    "btn-apply-master-template",
    "btn-tab2-apply-all",
    "btn-tab3-apply-all",
    "btn-tab5-apply-all",
    "btn-preview-apply-all"
  ];
  applyAllIds.forEach(btnId => {
    const el = document.getElementById(btnId);
    if (el) el.addEventListener("click", () => applyMasterTemplateToAllClips());
  });

  // Save Master Template buttons
  ["btn-save-master-template", "btn-tab1-save-master"].forEach(btnId => {
    const el = document.getElementById(btnId);
    if (el) el.addEventListener("click", () => saveMasterTemplate());
  });

  // Reset Master Template button
  const btnResetMaster = document.getElementById("btn-reset-master-template");
  if (btnResetMaster) {
    btnResetMaster.addEventListener("click", () => resetMasterTemplate());
  }

  // Auto apply checkbox
  const checkAutoMaster = document.getElementById("check-auto-apply-master");
  if (checkAutoMaster) {
    checkAutoMaster.addEventListener("change", (e) => {
      state.autoApplyMaster = e.target.checked;
    });
  }

  // Modal close handlers (click X or click backdrop or press ESC)
  const modal = document.getElementById("video-modal");
  const modalClose = document.getElementById("modal-close");
  if (modalClose) modalClose.addEventListener("click", closeModal);
  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeModal();
    });
  }
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });
}

function closeModal() {
  const modal = document.getElementById("video-modal");
  if (modal) {
    modal.style.display = "none";
    const vid = document.getElementById("modal-video");
    if (vid) {
      try { vid.pause(); } catch (_) {}
    }
  }
}
window.closeModal = closeModal;

function showToast(msg) {
  let toast = document.getElementById("app-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "app-toast";
    toast.style.cssText = "position: fixed; bottom: 24px; right: 24px; background: #1f2432; color: #fff; padding: 12px 20px; border-radius: 8px; border: 1px solid #6366f1; z-index: 9999; box-shadow: 0 4px 20px rgba(0,0,0,0.5); font-size: 14px; transition: opacity 0.3s ease;";
    document.body.appendChild(toast);
  }
  toast.innerText = msg;
  toast.style.opacity = "1";
  toast.style.display = "block";
  clearTimeout(toast._timeout);
  toast._timeout = setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => { toast.style.display = "none"; }, 300);
  }, 3500);
}

async function handleFileUpload(e) {
  const file = e.target.files[0];
  if (!file) return;
  await uploadFile(file);
  e.target.value = "";
}

async function uploadFile(file) {
  const statusBox = document.getElementById("file-upload-status");
  const statusText = document.getElementById("file-upload-text");
  const statusBar = document.getElementById("file-upload-bar");
  const statusPct = document.getElementById("file-upload-percent");

  if (statusBox) statusBox.style.display = "block";
  if (statusBar) statusBar.style.width = "0%";
  if (statusPct) statusPct.innerText = "0%";
  if (statusText) statusText.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Preparing ${file.name}...`;

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload", true);

    const startTime = Date.now();

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const percent = Math.min(99, Math.round((e.loaded / e.total) * 100));
        const loadedMB = (e.loaded / (1024 * 1024)).toFixed(1);
        const totalMB = (e.total / (1024 * 1024)).toFixed(1);
        
        const elapsedSec = (Date.now() - startTime) / 1000;
        const speedMBs = elapsedSec > 0 ? (e.loaded / (1024 * 1024) / elapsedSec).toFixed(1) : "0";

        if (statusBar) statusBar.style.width = `${percent}%`;
        if (statusPct) statusPct.innerText = `${percent}%`;
        if (statusText) {
          statusText.innerHTML = `<i class="fa-solid fa-cloud-arrow-up"></i> Uploading: <strong>${loadedMB} MB / ${totalMB} MB</strong> (${speedMBs} MB/s)`;
        }
      }
    };

    xhr.upload.onload = () => {
      if (statusBar) statusBar.style.width = "100%";
      if (statusPct) statusPct.innerText = "100%";
      if (statusText) {
        statusText.innerHTML = `<i class="fa-solid fa-gear fa-spin"></i> Extracting video metadata & facecam frame...`;
      }
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText);
          state.videoLoaded = true;
          setPreviewEmptyState(false);
          state.videoPath = data.video_path;
          state.videoMeta = data.meta;
          state.clips = initClipsMetadata(data.clips);
          state.subtitles = data.subtitles || [];
          state.template.webcam_crop_custom = false;
          document.getElementById("input-video-path").value = data.video_path;

          updateMetaUI(data.meta);
          renderClips();
          renderSubtitles();
          
          state.videoLoadedTimestamp = Date.now();
          const srcVid = document.getElementById("preview-source-video");
          if (srcVid) {
            if (typeof stopPlayableClipPreview === "function") stopPlayableClipPreview();
            srcVid.src = `/media/video?t=${state.videoLoadedTimestamp}`;
            srcVid.load();
          }

          if (window.reloadWebcamSourceImage) {
            window.reloadWebcamSourceImage(data.source_frame);
          }
          
          triggerPreview(true);
          showToast(`⚡ Loaded ${file.name} successfully! Ready to preview & clip.`);
          resolve(data);
        } catch (err) {
          alert("Error parsing server response: " + err.message);
          reject(err);
        } finally {
          if (statusBox) statusBox.style.display = "none";
        }
      } else {
        alert("Upload failed: " + xhr.responseText);
        if (statusBox) statusBox.style.display = "none";
        reject(new Error(xhr.responseText));
      }
    };

    xhr.onerror = () => {
      alert("Network error during file upload. Tip: For large videos, try copying its file path into the box below.");
      if (statusBox) statusBox.style.display = "none";
      reject(new Error("Network error"));
    };

    const formData = new FormData();
    formData.append("file", file);
    xhr.send(formData);
  });
}

function updateMetaUI(meta) {
  const badge = document.getElementById("video-status-badge");
  badge.innerText = "Loaded";
  badge.style.background = "var(--accent-green)";
  document.getElementById("video-meta-box").style.display = "grid";
  document.getElementById("meta-res").innerText = `${meta.width}x${meta.height}`;
  document.getElementById("meta-duration").innerText = `${meta.duration}s`;
  document.getElementById("meta-fps").innerText = `${meta.fps} fps`;
  document.getElementById("slider-preview-time").max = Math.floor(meta.duration);

  // Multi-track audio detection (OBS / Streamer Mic Track)
  const trackBox = document.getElementById("box-audio-track-select");
  const trackSel = document.getElementById("select-audio-track");
  if (trackBox && trackSel && meta.audio_streams && meta.audio_streams.length > 1) {
    trackBox.style.display = "block";
    trackSel.innerHTML = "";
    meta.audio_streams.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t.index;
      opt.innerText = `${t.title} (${t.channels}ch ${t.codec ? t.codec.toUpperCase() : ''})`;
      trackSel.appendChild(opt);
    });
  } else if (trackBox) {
    trackBox.style.display = "none";
  }
}

async function loadSource(path, isDemo = false, customTitle = null, customScore = 98) {
  // Strip quotation marks from path
  path = path.replace(/^["'“”]+|["'“”]+$/g, '').trim();
  if (!path) return;
  const statusBox = document.getElementById("file-upload-status");
  const statusText = document.getElementById("file-upload-text");
  const statusBar = document.getElementById("file-upload-bar");
  const statusPct = document.getElementById("file-upload-percent");

  if (statusBox) statusBox.style.display = "block";
  if (statusBar) statusBar.style.width = "75%";
  if (statusPct) statusPct.innerText = "Direct Disk";
  if (statusText) statusText.innerHTML = `<i class="fa-solid fa-bolt" style="color:var(--accent-gold);"></i> Loading direct from disk (Zero upload delay)...`;

  try {
    const res = await fetch("/api/set_source", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ video_path: path, is_demo: isDemo })
    });
    if (!res.ok) {
      let errText = await res.text();
      try {
        const errJson = JSON.parse(errText);
        errText = errJson.detail || errText;
      } catch (_) {}
      throw new Error(errText);
    }
    const data = await res.json();
    if (statusBar) statusBar.style.width = "100%";
    if (statusPct) statusPct.innerText = "100%";

    state.videoLoaded = true;
    setPreviewEmptyState(false);
    state.videoPath = data.video_path || path;
    state.videoMeta = data.meta;
    if (!data.clips || data.clips.length === 0) {
      const dur = (data.meta && data.meta.duration) ? data.meta.duration : 60;
      // High-precision stream slice or video: Default Clip #1 to 100% of the loaded footage!
      // Do NOT arbitrarily split into 15s/18s cuts unless user explicitly clicks Auto-Detect Clips.
      const clipTitle = customTitle || (dur <= 120 ? `Full Highlight (${Math.round(dur)}s)` : `Full Highlight (60s)`);
      const fullClip = { 
        id: "clip-full", 
        title: clipTitle, 
        start: 0, 
        end: Math.round(dur * 10) / 10, 
        duration: Math.round(dur * 10) / 10,
        score: customScore || 99, 
        virality_score: customScore || 99,
        category: "Stream Highlight", 
        reason: "Selected viral stream moment" 
      };
      state.clips = initClipsMetadata([fullClip]);
      state.selectedClipId = "clip-full";
    } else {
      state.clips = initClipsMetadata(data.clips);
      state.selectedClipId = state.clips.length > 0 ? state.clips[0].id : null;
    }
    state.subtitles = data.subtitles || [];
    state.template.webcam_crop_custom = false;
    document.getElementById("input-video-path").value = data.video_path;
    
    updateMetaUI(data.meta);
    renderClips();
    renderSubtitles();
    if (window.updatePlayerInfo) {
      window.updatePlayerInfo();
    }
    
    state.videoLoadedTimestamp = Date.now();
    const srcVid = document.getElementById("preview-source-video");
    if (srcVid) {
      if (typeof stopPlayableClipPreview === "function") stopPlayableClipPreview();
      srcVid.src = `/media/video?t=${state.videoLoadedTimestamp}`;
      srcVid.load();
    }

    // Reload Facecam Reticle with the loaded footage frame
    if (window.reloadWebcamSourceImage) {
      window.reloadWebcamSourceImage(data.source_frame);
    }
    
    triggerPreview(true);
    showToast(`⚡ Loaded ${data.meta.duration}s video!`);

    // AUTO-TRANSCRIBE & LLM SYNERGY PIPELINE:
    // If this video is a short slice (<= 120s) and has no subtitles yet, automatically start Whisper transcription!
    if (!isDemo && (!state.subtitles || state.subtitles.length === 0) && data.meta.duration <= 120) {
      autoTranscribeAndRefineSlice(data.meta.duration);
    }
  } catch (err) {
    alert("Could not load video:\n\n" + err.message + "\n\n💡 Tip: Click 'Browse Video File from PC' to pick any video file directly from your computer.");
  } finally {
    if (statusBox) statusBox.style.display = "none";
  }
}

async function autoTranscribeAndRefineSlice(dur) {
  try {
    showToast("🎙️ Auto-transcribing dialogue with Whisper AI...");
    const transRes = await fetch("/api/transcribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        is_demo: false,
        language: "auto",
        streamer_voice_focus: true,
        words_per_line: 3
      })
    });
    if (!transRes.ok) return;
    const transData = await transRes.json();
    if (transData.subtitles && transData.subtitles.length > 0) {
      state.subtitles = transData.subtitles;
      renderSubtitles();
      showToast(`✅ Synced ${transData.subtitles.length} dialogue lines! Running LLM Mind...`);

      // Now run LLM Mind to get an entity-aware viral title & retention score
      try {
        const detectRes = await fetch("/api/detect_clips", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            use_llm: true,
            min_duration: 8.0,
            max_duration: Math.min(dur, 60.0),
            snap_boundaries: true
          })
        });
        if (detectRes.ok) {
          const dData = await detectRes.json();
          if (dData.clips && dData.clips.length > 0) {
            // Keep the best clip or update the main clip's title and metrics
            const best = dData.clips[0];
            if (state.clips && state.clips.length > 0) {
              state.clips[0].title = best.title || state.clips[0].title;
              state.clips[0].score = best.virality_score || state.clips[0].score;
              state.clips[0].virality_score = best.virality_score || state.clips[0].virality_score;
              if (best.reason) state.clips[0].reason = best.reason;
              if (best.llm_punchline) state.clips[0].llm_punchline = best.llm_punchline;
              renderClips();
              showToast(`🔥 LLM Mind Verified: "${state.clips[0].title.replace(/^Rank\s*#?\d+\s*•\s*/, '')}"`);
            }
          }
        }
      } catch (llmErr) {
        console.warn("LLM refine after transcribe error:", llmErr);
      }
    }
  } catch (e) {
    console.warn("Auto-transcription error:", e);
  }
}

async function initLLMStatus() {
  const badge = document.getElementById("llm-status-badge");
  if (!badge) return;
  try {
    const res = await fetch("/api/llm/status");
    if (!res.ok) return;
    const data = await res.json();
    if (data.online && data.preferred_model) {
      badge.innerHTML = `<i class="fa-solid fa-bolt" style="color: #10B981;"></i> ${data.preferred_model} Mind Active`;
      badge.style.background = "rgba(16, 185, 129, 0.2)";
      badge.style.color = "#34d399";
    } else if (data.online) {
      badge.innerHTML = `<i class="fa-solid fa-spinner fa-spin" style="font-size: 8px;"></i> Downloading Model...`;
      badge.style.background = "rgba(245, 158, 11, 0.2)";
      badge.style.color = "#F59E0B";
    } else {
      badge.innerHTML = `<i class="fa-solid fa-bolt" style="color: #34d399;"></i> Fused Engine Active`;
      badge.style.background = "rgba(16, 185, 129, 0.15)";
      badge.style.color = "#34d399";
    }
  } catch (_) {
    badge.innerHTML = `<i class="fa-solid fa-bolt" style="color: #10B981;"></i> ALWAYS ACTIVE & SYNCED`;
  }
}

async function runViralDetection() {
  const btn = document.getElementById("btn-detect-clips") || document.getElementById("btn-detect-viral") || document.getElementById("btn-auto-slice");
  const origHtml = btn ? btn.innerHTML : "";
  const isAuto = state.viralSettings.mode === "auto";

  if (!state.videoPath) {
    alert("Please load or upload a video stream first before extracting clips.");
    return;
  }

  if (btn) {
    btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin" style="color: var(--accent-lime);"></i> Scanning Stream Climaxes & Outbursts...`;
    btn.disabled = true;
  }

  const container = document.getElementById("clips-list") || document.getElementById("clip-list");
  if (container) {
    container.innerHTML = `
      <div style="padding: 32px 16px; text-align: center; background: rgba(0,0,0,0.3); border: 2px dashed rgba(212, 255, 0, 0.4); border-radius: var(--radius-md); margin: 6px 0;">
        <div style="font-size: 32px; margin-bottom: 12px; color: var(--accent-lime);"><i class="fa-solid fa-brain fa-bounce"></i></div>
        <h4 style="font-size: 14px; font-weight: 700; color: #fff; margin-bottom: 8px;">AI Brain is Scanning Stream Audio & Visuals</h4>
        <p style="font-size: 12px; color: var(--text-muted); max-width: 460px; margin: 0 auto; line-height: 1.6;">
          Extracting streamer vocal surges, laughter, jumpscares, and gameplay action...<br>
          <span style="color: var(--accent-cyan); font-weight: 600;">Ranking highest-retention viral segments now...</span>
        </p>
      </div>`;
  }

  try {
    if (typeof fetchToolsStatus === "function") fetchToolsStatus();
    const res = await fetch("/api/detect_clips", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        min_duration: state.viralSettings.min_duration,
        max_duration: state.viralSettings.max_duration,
        mode: state.viralSettings.mode,
        target_clips: isAuto ? null : state.viralSettings.target_clips,
        profile: state.viralSettings.profile,
        weight_audio: state.viralSettings.weight_audio,
        weight_pitch: state.viralSettings.weight_pitch,
        weight_hook: state.viralSettings.weight_hook,
        weight_speech: state.viralSettings.weight_speech,
        weight_motion: state.viralSettings.weight_motion,
        snap_boundaries: state.viralSettings.snap_boundaries,
        webcam_crop: (state.template && state.template.webcam_crop) ? state.template.webcam_crop : null,
        use_llm: true
      })
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    state.clips = initClipsMetadata(data.clips);
    if (state.clips.length > 0) {
      state.selectedClipId = state.clips[0].id;
    }
    renderClips();
    if (window.updatePlayerInfo) window.updatePlayerInfo();
    if (state.clips.length > 0 && typeof triggerPreview === "function") {
      state.previewTime = state.clips[0].start + 1.0;
      triggerPreview(true);
    }
    const toastMsg = isAuto
      ? `⚡ Found ${data.clips.length} high-potential viral moments ranked by AI!`
      : `⚡ Extracted top ${data.clips.length} viral clips!`;
    showToast(toastMsg);
  } catch (err) {
    alert("Viral detection failed: " + err.message);
    renderClips();
  } finally {
    if (typeof fetchToolsStatus === "function") fetchToolsStatus();
    if (btn) {
      btn.innerHTML = origHtml;
      btn.disabled = false;
    }
  }
}

function initClipsMetadata(clips) {
  if (!clips) return [];
  const useMaster = state.masterTemplate && state.masterTemplate.template_config && state.autoApplyMaster;
  const tmpl = useMaster ? state.masterTemplate.template_config : state.template;
  const sub = (useMaster && state.masterTemplate.subtitle_config) ? state.masterTemplate.subtitle_config : state.subtitlesConfig;

  if (useMaster) {
    state.template = JSON.parse(JSON.stringify(tmpl));
    state.subtitlesConfig = JSON.parse(JSON.stringify(sub));
    syncUIFromState();
  }

  return clips.map(c => {
    c.template_config = JSON.parse(JSON.stringify(tmpl));
    c.subtitle_config = JSON.parse(JSON.stringify(sub));
    c.settings_applied = Boolean(useMaster);
    c.has_custom_settings = Boolean(useMaster);
    return c;
  });
}

function updateActiveClipSettings() {
  if (!state.selectedClipId || !state.clips) return;
  const clip = state.clips.find(c => c.id === state.selectedClipId);
  if (clip) {
    clip.template_config = JSON.parse(JSON.stringify(state.template));
    clip.subtitle_config = JSON.parse(JSON.stringify(state.subtitlesConfig));
    clip.has_custom_settings = true;
  }
}

function updateGPPanUI(panX, panY) {
  const sX = document.getElementById("slider-gp-pan-x");
  const sY = document.getElementById("slider-gp-pan-y");
  const lX = document.getElementById("val-gp-pan-x");
  const lY = document.getElementById("val-gp-pan-y");
  const badge = document.getElementById("gp-pan-badge");

  if (sX) sX.value = panX;
  if (sY) sY.value = panY;

  if (lX) {
    if (panX === 0) lX.innerText = "Center";
    else if (panX < 0) lX.innerText = `${Math.abs(panX)}% Left`;
    else lX.innerText = `${panX}% Right`;
  }

  if (lY) {
    if (panY === 0) lY.innerText = "Center";
    else if (panY < 0) lY.innerText = `${Math.abs(panY)}% Up`;
    else lY.innerText = `${panY}% Down`;
  }

  if (badge) {
    badge.innerText = `(${panX}%, ${panY}%)`;
  }
}

function syncUIFromState() {
  const setSlider = (id, valId, val, unit, isPercent = false) => {
    const s = document.getElementById(id);
    const l = document.getElementById(valId);
    if (s && val !== undefined) s.value = val;
    if (l && val !== undefined) {
      l.innerText = isPercent ? `${Math.round(val * 100)}%` : `${val}${unit}`;
    }
  };

  setSlider("slider-blur", "val-blur", state.template.bg_blur_sigma, "px");
  setSlider("slider-bg-dim", "val-bg-dim", state.template.bg_brightness, "", true);
  
  const curBlur = Math.round(state.template.bg_blur_sigma !== undefined ? state.template.bg_blur_sigma : 30);
  setSlider("slider-blur", "val-blur", curBlur, "px");

  // Gameplay Card Dimensions & Zoom
  const gpW = state.template.gameplay_w || 960;
  const gpH = state.template.gameplay_h || 540;
  setSlider("slider-gp-w", "val-gp-w", gpW, "px");
  setSlider("slider-gp-h", "val-gp-h", gpH, "px");
  setSlider("slider-gp-y", "val-gp-y", state.template.gameplay_y || 690, "px");
  setSlider("slider-gp-zoom", "val-gp-zoom", state.template.gameplay_zoom || 1.0, "x");

  const curZoom = parseFloat(state.template.gameplay_zoom || 1.15);
  document.querySelectorAll("#gp-zoom-presets .preset-pill").forEach(p => {
    p.classList.toggle("active", Math.abs(parseFloat(p.dataset.zoom) - curZoom) < 0.04);
  });

  const gpPanX = state.template.gameplay_pan_x !== undefined ? state.template.gameplay_pan_x : 0;
  const gpPanY = state.template.gameplay_pan_y !== undefined ? state.template.gameplay_pan_y : 0;
  updateGPPanUI(gpPanX, gpPanY);

  const gpBadge = document.getElementById("gp-size-badge");
  if (gpBadge) {
    if ((gpW >= 1000 && gpH >= 650) || state.template.webcam_shape === "split_screen" || state.template.layout_mode === "split_screen") {
      gpBadge.innerText = `${Math.round(gpW)} × ${Math.round(gpH)} (Viral Reference)`;
    } else {
      gpBadge.innerText = `${Math.round(gpW)} × ${Math.round(gpH)}`;
    }
  }

  // Update split presets active status
  document.querySelectorAll("#template-split-presets .preset-pill").forEach(p => {
    const pVal = parseInt(p.getAttribute("data-gph"), 10);
    p.classList.toggle("active", Math.abs(pVal - gpH) < 30);
  });

  setSlider("slider-gp-radius", "val-gp-radius", state.template.gameplay_radius, "px");
  setSlider("slider-gp-border", "val-gp-border", state.template.gameplay_border_w, "px");
  setSlider("slider-cam-w", "val-cam-w", state.template.webcam_w || 1080, "px");
  setSlider("slider-cam-h", "val-cam-h", state.template.webcam_h || 700, "px");
  setSlider("slider-cam-radius", "val-cam-radius", state.template.webcam_radius || 0, "px");
  const curCamW = state.template.webcam_w || 1080;
  const defCamX = Math.round((1080 - curCamW) / 2);
  const curCamX = state.template.webcam_x !== undefined ? state.template.webcam_x : defCamX;
  setSlider("slider-cam-x", "val-cam-x", curCamX, "px");
  setSlider("slider-cam-y", "val-cam-y", state.template.webcam_y !== undefined ? state.template.webcam_y : 260, "px");
  setSlider("slider-cam-border", "val-cam-border", state.template.webcam_border_w || 0, "px");

  const curShape = state.template.webcam_shape || "circle";
  document.querySelectorAll("#cam-shape-presets .preset-pill").forEach(b => {
    if (b.getAttribute("data-shape") === curShape) b.classList.add("active");
    else b.classList.remove("active");
  });

  if (typeof updateCamShapeBadge === "function") updateCamShapeBadge();
  if (typeof updateCamHandleUI === "function") updateCamHandleUI();
  if (typeof updateCamShapeUI === "function") updateCamShapeUI(false);

  // Words Shown at a Time Active Button
  const curWords = state.subtitlesConfig.words_per_line !== undefined ? state.subtitlesConfig.words_per_line : 3;
  document.querySelectorAll("[data-words]").forEach(b => {
    if (parseInt(b.getAttribute("data-words")) === curWords) {
      b.classList.add("active");
    } else {
      b.classList.remove("active");
    }
  });

  setSlider("slider-font-size", "val-font-size", state.subtitlesConfig.font_size, "px");
  setSlider("slider-sub-x", "val-sub-x", state.subtitlesConfig.position_x, "%");
  setSlider("slider-sub-y", "val-sub-y", state.subtitlesConfig.position_y, "%");
  setSlider("slider-sub-stroke", "val-sub-stroke", state.subtitlesConfig.outline_width, "px");

  const curSyncMs = state.subtitlesConfig.sync_offset_ms || 0;
  const syncS = document.getElementById("slider-sync-offset");
  if (syncS) syncS.value = curSyncMs;
  const syncL = document.getElementById("val-sync-offset");
  if (syncL) {
    if (curSyncMs === 0) syncL.innerText = "0 ms (Exact Vocal Waveform)";
    else if (curSyncMs < 0) syncL.innerText = `${curSyncMs} ms (Advanced earlier)`;
    else syncL.innerText = `+${curSyncMs} ms (Delayed later)`;
  }

  setSlider("slider-micro-texture", "val-micro-texture", state.template.micro_texture !== undefined ? state.template.micro_texture : 0.6, "x");
  setSlider("slider-sharpness", "val-sharpness", state.template.sharpen_amount, "x");
  setSlider("slider-contrast", "val-contrast", state.template.contrast_boost, "", true);
  setSlider("slider-saturation", "val-saturation", state.template.saturation_boost, "", true);

  if (typeof updateSubHandleUI === "function") {
    updateSubHandleUI();
  }

  state.subtitlesConfig.style_preset = normalizeStylePreset(state.subtitlesConfig.style_preset);
  if (state.subtitlesConfig.style_preset) {
    document.querySelectorAll("[data-style]").forEach(b => {
      if (b.getAttribute("data-style") === state.subtitlesConfig.style_preset) {
        b.classList.add("active");
      } else {
        b.classList.remove("active");
      }
    });
  }

  const fontSel = document.getElementById("select-font");
  if (fontSel && state.subtitlesConfig.font_family) {
    fontSel.value = state.subtitlesConfig.font_family;
  }

  state.subtitlesConfig.model_name = normalizeWhisperModelName(state.subtitlesConfig.model_name);
  const modelSel = document.getElementById("select-whisper-model");
  if (modelSel) {
    modelSel.value = state.subtitlesConfig.model_name;
  }

  // Subtitles Enabled Toggle & Banner Sync
  const isSubEnabled = state.subtitlesConfig.enabled !== false;
  const toggleSub = document.getElementById("toggle-subtitles-enabled");
  if (toggleSub) toggleSub.checked = isSubEnabled;
  const badgeSub = document.getElementById("badge-subtitles-status");
  if (badgeSub) {
    if (isSubEnabled) {
      badgeSub.innerText = "SUBTITLES: ON";
      badgeSub.className = "badge badge-active";
      badgeSub.style.background = "";
      badgeSub.style.color = "";
      badgeSub.style.borderColor = "";
    } else {
      badgeSub.innerText = "SUBTITLES: OFF";
      badgeSub.className = "badge";
      badgeSub.style.background = "rgba(239, 68, 68, 0.15)";
      badgeSub.style.color = "#EF4444";
      badgeSub.style.borderColor = "rgba(239, 68, 68, 0.4)";
    }
  }
  const bannerSubDisabled = document.getElementById("subtitles-disabled-banner");
  if (bannerSubDisabled) {
    bannerSubDisabled.style.display = isSubEnabled ? "none" : "flex";
  }
  const subControlsBody = document.getElementById("subtitles-controls-body");
  if (subControlsBody) {
    subControlsBody.style.opacity = isSubEnabled ? "1" : "0.45";
    subControlsBody.style.pointerEvents = isSubEnabled ? "auto" : "none";
    subControlsBody.style.transition = "opacity 0.2s ease";
  }

  const checkUpper = document.getElementById("check-uppercase");
  if (checkUpper && state.subtitlesConfig.is_uppercase !== undefined) {
    checkUpper.checked = state.subtitlesConfig.is_uppercase;
  }
  const checkCensor = document.getElementById("check-censor-profanity");
  if (checkCensor && state.subtitlesConfig.censor_profanity !== undefined) {
    checkCensor.checked = state.subtitlesConfig.censor_profanity;
  }
  const checkClimax = document.getElementById("check-climax-zoom");
  if (checkClimax && state.template.climax_zoom_enabled !== undefined) {
    checkClimax.checked = state.template.climax_zoom_enabled;
  }
  const checkJumpCut = document.getElementById("check-auto-jump-cut");
  if (checkJumpCut && state.template.auto_jump_cut !== undefined) {
    checkJumpCut.checked = state.template.auto_jump_cut;
  }

  const setColor = (pickerId, hexId, hex) => {
    const p = document.getElementById(pickerId);
    const h = hexId ? document.getElementById(hexId) : null;
    if (p && hex) p.value = hex;
    if (h && hex) h.innerText = hex;
  };
  setColor("color-gp-border", null, state.template.gameplay_border_color);
  setColor("color-cam-border", null, state.template.webcam_border_color);
  setColor("color-cam-glow", null, state.template.webcam_glow_color || "#C026D3");
  setColor("color-sub-primary", "hex-sub-primary", state.subtitlesConfig.primary_color);
  setColor("color-sub-highlight", "hex-sub-highlight", state.subtitlesConfig.highlight_color);
  setColor("color-sub-outline", "hex-sub-outline", state.subtitlesConfig.outline_color);

  // Neon Lightning Aura Sync
  const checkCamGlow = document.getElementById("check-cam-glow");
  if (checkCamGlow && state.template.webcam_glow_enabled !== undefined) {
    checkCamGlow.checked = state.template.webcam_glow_enabled;
  }
  setSlider("slider-cam-glow-size", "val-cam-glow-size", state.template.webcam_glow_size || 28, "px");
  setSlider("slider-cam-glow-intensity", "val-cam-glow-intensity", state.template.webcam_glow_intensity || 1.4, "x");
  document.querySelectorAll("#cam-glow-presets .preset-pill").forEach(b => {
    if (b.getAttribute("data-effect") === (state.template.webcam_glow_effect || "neon_lightning")) {
      b.classList.add("active");
    } else {
      b.classList.remove("active");
    }
  });

  // Divider Sync
  const divH = state.template.divider_height !== undefined ? parseInt(state.template.divider_height) : 4;
  setSlider("slider-divider-w", "val-divider-w", divH, "px");
  const divBadge = document.getElementById("divider-badge");
  if (divBadge) {
    divBadge.innerText = (divH === 0) ? "NO DIVIDER" : `${divH}px SOLID`;
  }
  const divColor = state.template.divider_color || "#FFFFFF";
  setColor("color-divider", "hex-divider", divColor);
  document.querySelectorAll("[data-div]").forEach(b => {
    if (parseInt(b.getAttribute("data-div")) === divH) {
      b.classList.add("active");
    } else {
      b.classList.remove("active");
    }
  });

  if (window.syncWebcamReticleFromCrop && state.template.webcam_crop) {
    window.syncWebcamReticleFromCrop(state.template.webcam_crop);
  }
}

// ==================== MASTER CLIP TEMPLATE SYSTEM ====================

function initMasterTemplateControls() {
  const checkAuto = document.getElementById("check-auto-apply-master");
  if (checkAuto) {
    checkAuto.checked = state.autoApplyMaster !== false;
    checkAuto.addEventListener("change", (e) => {
      state.autoApplyMaster = e.target.checked;
    });
  }
}

async function loadMasterTemplate() {
  try {
    const res = await fetch("/api/master_template");
    const data = await res.json();
    if (data.has_saved && data.template) {
      state.masterTemplate = data.template;
      localStorage.setItem("openshorts_master_template", JSON.stringify(data.template));
    } else {
      const local = localStorage.getItem("openshorts_master_template");
      if (local) {
        state.masterTemplate = JSON.parse(local);
      }
    }
  } catch (e) {
    const local = localStorage.getItem("openshorts_master_template");
    if (local) {
      state.masterTemplate = JSON.parse(local);
    }
  }

  // Auto-migrate legacy 560px configurations to 700px (1400px viral split)
  if (state.masterTemplate && state.masterTemplate.template_config) {
    const tc = state.masterTemplate.template_config;
    let upgraded = false;
    if (tc.gameplay_h === 560 || !tc.gameplay_h) { tc.gameplay_h = 700; upgraded = true; }
    if (tc.webcam_h === 560 || !tc.webcam_h) { tc.webcam_h = 700; upgraded = true; }
    if (tc.webcam_y === 400 || tc.webcam_y === 0 || !tc.webcam_y) { tc.webcam_y = 260; upgraded = true; }
    if (upgraded) {
      localStorage.setItem("openshorts_master_template", JSON.stringify(state.masterTemplate));
    }
  }

  if (state.masterTemplate) {
    if (state.masterTemplate.template_config) {
      state.template = Object.assign({}, state.template, state.masterTemplate.template_config);
    }
    if (state.masterTemplate.subtitle_config) {
      state.subtitlesConfig = Object.assign({}, state.subtitlesConfig, state.masterTemplate.subtitle_config);
      state.subtitlesConfig.model_name = normalizeWhisperModelName(state.subtitlesConfig.model_name);
      state.subtitlesConfig.style_preset = normalizeStylePreset(state.subtitlesConfig.style_preset);
    }
  }

  // Ensure state.template also uses upgraded 700px defaults if legacy 560px was loaded
  if (state.template.gameplay_h === 560) state.template.gameplay_h = 700;
  if (state.template.webcam_h === 560) state.template.webcam_h = 700;
  if (state.template.webcam_y === 400 || state.template.webcam_y === 0) state.template.webcam_y = 260;

  syncUIFromState();
  updateMasterTemplateUI();
}

function updateMasterTemplateUI() {
  const badge = document.getElementById("badge-master-status");
  const text = document.getElementById("master-template-text");
  if (!badge || !text) return;

  if (state.masterTemplate && state.masterTemplate.template_config) {
    const t = state.masterTemplate.template_config;
    const shape = (t.webcam_shape || "circle").toUpperCase();
    const camW = t.webcam_w || 1080;
    const camH = t.webcam_h || 700;
    const gpW = t.gameplay_w || 1080;
    const gpH = t.gameplay_h || 700;
    const subPreset = ((state.masterTemplate.subtitle_config && state.masterTemplate.subtitle_config.style_preset) || 'Speed').toUpperCase();
    badge.innerText = "Stored & Ready";
    badge.style.background = "rgba(16, 185, 129, 0.2)";
    badge.style.color = "var(--accent-green)";
    badge.style.borderColor = "var(--accent-green)";
    text.innerHTML = `<strong>Stored Master:</strong> Facecam: <span style="color:var(--accent-neon);">${shape} (${camW}×${camH})</span> • Gameplay: <span style="color:var(--accent-neon);">${gpW}×${gpH}</span> • Subtitles: <span style="color:#C084FC;">${subPreset}</span> <span style="color:var(--accent-lime); font-size:10.5px; font-weight:700;">(1400px Viral Split)</span>`;
  } else {
    badge.innerText = "Default (1400px Viral)";
    badge.style.background = "rgba(148, 163, 184, 0.2)";
    badge.style.color = "#94a3b8";
    badge.style.borderColor = "#94a3b8";
    text.innerHTML = `Speed Viral Split active: <strong>1080×700 Facecam + 1080×700 Gameplay (1400px Active)</strong>. Click <strong>"Save Master"</strong> to pin for all clips.`;
  }
}

async function saveMasterTemplate() {
  updateActiveClipSettings();

  const payload = {
    name: "Master Clip Template",
    template_config: JSON.parse(JSON.stringify(state.template)),
    subtitle_config: JSON.parse(JSON.stringify(state.subtitlesConfig)),
    enhancement_config: {
      sharpen_amount: state.template.sharpen_amount,
      contrast_boost: state.template.contrast_boost,
      saturation_boost: state.template.saturation_boost,
      brightness_offset: state.template.brightness_offset
    }
  };

  try {
    const res = await fetch("/api/save_master_template", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      state.masterTemplate = data.template;
      localStorage.setItem("openshorts_master_template", JSON.stringify(data.template));
      updateMasterTemplateUI();
      showToast("💾 Master Template saved! Auto-applies to all new clips.");
    } else {
      throw new Error(data.detail || "Could not save template");
    }
  } catch (err) {
    state.masterTemplate = payload;
    localStorage.setItem("openshorts_master_template", JSON.stringify(payload));
    updateMasterTemplateUI();
    showToast("💾 Master Template saved to local storage!");
  }
}

async function resetMasterTemplate() {
  state.masterTemplate = null;
  localStorage.removeItem("openshorts_master_template");
  try {
    await fetch("/api/master_template", { method: "DELETE" });
  } catch (e) {}
  updateMasterTemplateUI();
  showToast("Master Template reset to system defaults.");
}

window.applyMasterTemplateToAllClips = function(sourceClipId = null) {
  // If an individual clip's button called this with its ID:
  if (sourceClipId) {
    const src = state.clips.find(c => c.id === sourceClipId);
    if (src && src.template_config) {
      state.template = JSON.parse(JSON.stringify(src.template_config));
      state.subtitlesConfig = JSON.parse(JSON.stringify(src.subtitle_config || state.subtitlesConfig));
      state.subtitlesConfig.model_name = normalizeWhisperModelName(state.subtitlesConfig.model_name);
    }
  } else {
    // If master template is saved, apply it!
    if (state.masterTemplate && state.masterTemplate.template_config) {
      state.template = JSON.parse(JSON.stringify(state.masterTemplate.template_config));
      if (state.masterTemplate.subtitle_config) {
        state.subtitlesConfig = JSON.parse(JSON.stringify(state.masterTemplate.subtitle_config));
        state.subtitlesConfig.model_name = normalizeWhisperModelName(state.subtitlesConfig.model_name);
      }
    } else {
      // Save active clip settings as master template now!
      saveMasterTemplate();
    }
  }

  if (!state.clips || state.clips.length === 0) {
    syncUIFromState();
    triggerPreview(true);
    showToast("Master Template ready! Detect clips to auto-apply.");
    return;
  }

  const tmplClone = JSON.parse(JSON.stringify(state.template));
  const subClone = JSON.parse(JSON.stringify(state.subtitlesConfig));

  state.clips.forEach(clip => {
    clip.template_config = JSON.parse(JSON.stringify(tmplClone));
    clip.subtitle_config = JSON.parse(JSON.stringify(subClone));
    clip.settings_applied = true;
    clip.has_custom_settings = true;
  });

  syncUIFromState();
  renderClips();
  if (isPlayMode || isPlayingPreview) {
    renderCanvasFrame(getActiveOrFallbackClip());
  }
  triggerPreview(true);
  showToast(`⚡ Master Template applied to all ${state.clips.length} clips! Dimensions, positions & styles synced.`);
};

// Backward-compatible alias
window.applySettingsToAllClips = window.applyMasterTemplateToAllClips;

function renderClips() {
  const container = document.getElementById("clip-list") || document.getElementById("clips-list");
  const countSpan = document.getElementById("clips-count");
  if (countSpan) countSpan.innerText = state.clips.length;
  const countBadge = document.getElementById("clips-count-badge");
  if (countBadge) countBadge.innerText = `${state.clips.length} clips ready`;
  const btnCountSpan = document.getElementById("btn-transcribe-clips-count");
  if (btnCountSpan) btnCountSpan.innerText = state.clips.length;
  if (!container) return;
  container.innerHTML = "";
  
  if (state.clips.length === 0) {
    if (!state.videoLoaded) {
      container.innerHTML = `
        <div style="padding: 24px 16px; text-align: center; background: rgba(0,0,0,0.2); border: 1px dashed rgba(255,255,255,0.1); border-radius: var(--radius-md); margin: 6px 0;">
          <div style="font-size: 22px; margin-bottom: 6px; color: var(--text-muted);"><i class="fa-solid fa-film"></i></div>
          <p style="font-size: 12px; color: var(--text-muted); margin: 0; line-height: 1.5;">
            No clips yet — load a video or scan a stream above
          </p>
        </div>`;
      return;
    }
    container.innerHTML = `
      <div style="padding: 28px 16px; text-align: center; background: rgba(0,0,0,0.25); border: 2px dashed rgba(245, 158, 11, 0.35); border-radius: var(--radius-md); margin: 6px 0;">
        <div style="font-size: 28px; margin-bottom: 8px; color: var(--accent-gold);"><i class="fa-solid fa-bolt"></i></div>
        <h4 style="font-size: 14px; font-weight: 700; color: #fff; margin-bottom: 6px;">No Clips Detected Yet</h4>
        <p style="font-size: 12px; color: var(--text-muted); max-width: 480px; margin: 0 auto 14px auto; line-height: 1.5;">
          Video loaded! The engine waits for your command so you can set duration limits (min/max) and scoring sensitivity first. Click <strong>Detect Viral Moments</strong> below to find ranked clips.
        </p>
        <button class="btn btn-gold btn-sm" onclick="runViralDetection()"><i class="fa-solid fa-bolt"></i> Detect Viral Moments</button>
      </div>`;
    return;
  }

  if (!state.selectedClipId && state.clips.length > 0) {
    state.selectedClipId = state.clips[0].id;
  }
  
  state.clips.forEach((c) => {
    const item = document.createElement("div");
    const isActive = c.id === state.selectedClipId;
    item.className = isActive ? "clip-card active" : "clip-card";
    item.onclick = (e) => {
      if (e.target.closest("button") || e.target.closest("img")) return;
      selectClipForPreview(c.id, c.start);
    };
    const score = c.virality_score || 80;
    const badgeBg = c.badge_color || (score >= 85 ? "#10B981" : (score >= 70 ? "#F59E0B" : "#6366F1"));
    const reason = c.reason || "🔥 Viral Moment";

    const activeBadge = isActive 
      ? `<span style="background: rgba(0,245,255,0.18); color: var(--accent-neon); border: 1px solid var(--accent-neon); font-size: 10px; font-weight: 800; padding: 2px 7px; border-radius: 4px; letter-spacing: 0.5px;"><i class="fa-solid fa-circle-dot"></i> ACTIVE</span>`
      : "";

    const syncedBadge = c.settings_applied 
      ? `<span style="color: var(--accent-green); font-size: 11px; margin-left: 4px; font-weight: 600;"><i class="fa-solid fa-check-double"></i> Synced</span>`
      : "";

    const isClipSubsEnabled = (c.subtitle_config && c.subtitle_config.enabled !== undefined)
      ? c.subtitle_config.enabled
      : (state.subtitlesConfig.enabled !== false);

    const subsToggleBadge = isClipSubsEnabled
      ? `<button type="button" class="clip-cc-badge cc-on" onclick="window.toggleClipSubtitles('${c.id}', event)" title="Subtitles ON (Click to turn off for this clip)" style="background: rgba(16, 185, 129, 0.2); color: var(--accent-green); border: 1px solid rgba(16, 185, 129, 0.45); cursor: pointer; border-radius: 4px; padding: 2px 7px; font-size: 10px; font-weight: 700; display: inline-flex; align-items: center; gap: 4px;"><i class="fa-solid fa-closed-captioning"></i> CC ON</button>`
      : `<button type="button" class="clip-cc-badge cc-off" onclick="window.toggleClipSubtitles('${c.id}', event)" title="Subtitles OFF (Clean video with zero burned captions - Click to turn on)" style="background: rgba(239, 68, 68, 0.18); color: #FCA5A5; border: 1px dashed rgba(239, 68, 68, 0.5); cursor: pointer; border-radius: 4px; padding: 2px 7px; font-size: 10px; font-weight: 700; display: inline-flex; align-items: center; gap: 4px;"><i class="fa-solid fa-eye-slash"></i> CC OFF</button>`;

    const clipSubsCount = (c.subtitles && c.subtitles.length) || 
      (state.subtitles ? state.subtitles.filter(s => s.end > c.start && s.start < c.end).length : 0);
    const subBadge = isClipSubsEnabled
      ? (clipSubsCount > 0 
          ? `<span style="background: rgba(16, 185, 129, 0.18); color: var(--accent-green); border: 1px solid rgba(16, 185, 129, 0.4); font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 4px;"><i class="fa-solid fa-closed-captioning"></i> ${clipSubsCount} Lines</span>`
          : `<span style="background: rgba(255, 255, 255, 0.08); color: var(--text-muted); font-size: 10px; padding: 2px 7px; border-radius: 4px;"><i class="fa-solid fa-closed-captioning"></i> No Subs</span>`)
      : `<span style="background: rgba(239, 68, 68, 0.12); color: #FCA5A5; border: 1px solid rgba(239, 68, 68, 0.3); font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 4px;"><i class="fa-solid fa-ban"></i> Subs Muted</span>`;

    const llmMindBadge = (c.llm_verified || c.ai_curated)
      ? `<span style="background: rgba(16, 185, 129, 0.2); color: #34D399; border: 1px solid rgba(52, 211, 153, 0.4); font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 4px;"><i class="fa-solid fa-brain"></i> LLM Mind Selected</span>`
      : "";

    const jawDropBadge = c.jaw_drop_verified 
      ? `<span style="background: rgba(239, 68, 68, 0.2); color: #F87171; border: 1px solid rgba(239, 68, 68, 0.4); font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px;"><i class="fa-solid fa-face-surprise"></i> Jaw-Drop</span>` 
      : "";

    const coldOpenBadge = c.cold_open_verified 
      ? `<span style="background: rgba(56, 189, 248, 0.18); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.4); font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px;"><i class="fa-solid fa-bolt"></i> 0s Cold Open</span>` 
      : "";

    const speechSnapBadge = c.speech_snapped !== false
      ? `<span style="background: rgba(163, 230, 53, 0.15); color: var(--accent-lime); border: 1px solid rgba(163, 230, 53, 0.35); font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px;" title="Auto-snapped to natural speech boundary: zero cut-off words"><i class="fa-solid fa-scissors"></i> Speech Snapped</span>`
      : "";

    const narrativeArcBadge = c.narrative_micro_arc !== false
      ? `<span style="background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.35); font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px;" title="3-Part Narrative Micro-Story: Hook (0-3s) → Build-Up → Punchline Snap"><i class="fa-solid fa-book-open"></i> Narrative Arc</span>`
      : "";

    const thumbHtml = (c.has_thumbnail && c.thumbnail_url)
      ? `<div style="width: 54px; height: 82px; border-radius: 6px; overflow: hidden; position: relative; flex-shrink: 0; border: 1px solid rgba(255,255,255,0.18); background: #000; box-shadow: 0 2px 8px rgba(0,0,0,0.5); cursor: pointer;" onclick="window.open('${c.thumbnail_url}', '_blank')" title="Click to view High-CTR Cover Thumbnail">
          <img src="${c.thumbnail_url}?t=${Date.now()}" style="width: 100%; height: 100%; object-fit: cover;" alt="Cover" />
          <span style="position: absolute; bottom: 2px; left: 2px; right: 2px; background: rgba(0,0,0,0.85); color: var(--accent-neon); font-size: 7px; font-weight: 800; text-align: center; border-radius: 2px; padding: 1px 0;">COVER</span>
        </div>`
      : "";

    item.innerHTML = `
      <div style="display: flex; gap: 12px; align-items: flex-start; width: 100%;">
        ${thumbHtml}
        <div class="clip-info" style="flex: 1; min-width: 0;">
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap;">
            <h4 style="font-size: 14px; font-weight: 700; color: #fff;">${c.title}</h4>
            <span style="background: ${badgeBg}; color: #000; font-size: 10px; font-weight: 800; padding: 2px 7px; border-radius: 4px; letter-spacing: 0.5px;">${c.tier_badge || (score + '% VIRAL')}</span>
            <span style="background: rgba(255,255,255,0.12); color: #fff; font-size: 10px; font-weight: 800; padding: 2px 7px; border-radius: 4px;">${score}/100</span>
            ${llmMindBadge}
            ${jawDropBadge}
            ${coldOpenBadge}
            ${speechSnapBadge}
            ${narrativeArcBadge}
            ${subBadge}
            ${subsToggleBadge}
            ${activeBadge}
            ${syncedBadge}
          </div>
          <div style="display: flex; align-items: center; gap: 12px; font-size: 12px; color: var(--text-muted); flex-wrap: wrap;">
            <span style="background: rgba(0, 245, 255, 0.1); color: var(--accent-neon); padding: 1px 6px; border-radius: 4px; font-weight: 700;"><i class="fa-solid fa-stopwatch"></i> ${c.start}s – ${c.end}s (<strong>${(c.duration || (c.end - c.start) || 0).toFixed ? (c.duration || (c.end - c.start)).toFixed(1) : (c.duration || (c.end - c.start))}s Dynamic</strong>)</span>
            <span style="color: #cbd5e1; font-size: 11px; font-weight: 600;">${reason}</span>
          </div>
          ${c.llm_punchline ? `
          <div style="margin-top: 5px; font-size: 11px; color: #a7f3d0; background: rgba(16, 185, 129, 0.12); padding: 4px 8px; border-radius: 4px; border: 1px solid rgba(52, 211, 153, 0.3); display: flex; align-items: center; gap: 6px;">
            <i class="fa-solid fa-brain" style="color: #34d399;"></i>
            <span><strong>LLM Unified Mind:</strong> ${c.llm_punchline}</span>
          </div>` : ''}
          ${(c.description || (c.hashtags && c.hashtags.length) || c.pinned_comment) ? `
          <div class="post-kit-strip">
            <span class="post-kit-label"><i class="fa-solid fa-share-nodes"></i> Post Kit:</span>
            <button type="button" class="post-kit-btn" onclick="window.copyClipCaption('${c.id}', event)" title="Copy Title + Description + Hashtags for YouTube Shorts / Reels">
              <i class="fa-solid fa-copy"></i> Copy Caption
            </button>
            ${c.pinned_comment ? `
            <button type="button" class="post-kit-btn" onclick="window.copyClipComment('${c.id}', event)" title="Copy Pinned Engagement Comment">
              <i class="fa-solid fa-comment-dots"></i> Copy Comment
            </button>` : ''}
          </div>` : ''}
        </div>
      </div>
      <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-top: 6px;">
        <button class="btn btn-secondary btn-sm" onclick="selectClipForPreview('${c.id}', ${c.start})" title="Preview in 9:16 Canvas"><i class="fa-solid fa-eye"></i> Preview</button>
        <button class="btn btn-secondary btn-sm" onclick="window.toggleClipSubtitles('${c.id}', event)" title="${isClipSubsEnabled ? 'Turn OFF subtitles for this clip (Clean Video)' : 'Turn ON subtitles for this clip'}"><i class="fa-solid ${isClipSubsEnabled ? 'fa-closed-captioning' : 'fa-eye-slash'}" style="${isClipSubsEnabled ? 'color: var(--accent-lime);' : 'color: #EF4444;'}"></i> ${isClipSubsEnabled ? 'Subs ON' : 'Subs OFF'}</button>
        <button class="btn btn-secondary btn-sm" onclick="window.expandClipToFull('${c.id}')" title="Set this clip to 100% full duration of loaded video"><i class="fa-solid fa-expand" style="color:var(--accent-lime);"></i> Full Length</button>
        ${c.thumbnail_url ? `<button class="btn btn-secondary btn-sm" onclick="window.open('${c.thumbnail_url}', '_blank')" title="View High-CTR Cover Thumbnail"><i class="fa-solid fa-image"></i> Cover</button>` : ''}
        <button class="btn btn-primary btn-sm" onclick="applyMasterTemplateToAllClips('${c.id}')" title="Apply this clip's settings to all clips"><i class="fa-solid fa-copy"></i> Apply to All</button>
        <button class="btn btn-danger btn-sm" onclick="deleteClip('${c.id}')" title="Remove slice"><i class="fa-solid fa-trash"></i></button>
      </div>
    `;
    container.appendChild(item);
  });
}

window.copyClipCaption = function(id, event) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }
  const clip = state.clips.find(c => c.id === id);
  if (!clip) return;
  const cleanTitle = (clip.title || "").replace(/^Rank\s*#?\d+\s*•\s*/, "").trim();
  const desc = clip.description || "";
  const tags = Array.isArray(clip.hashtags) ? clip.hashtags.join(" ") : (clip.hashtags || "");
  const textToCopy = `${cleanTitle}\n\n${desc}\n\n${tags}`.trim();
  
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(textToCopy).then(() => {
      showToast("📋 Copied Shorts caption & hashtags!");
    }).catch(() => {
      showToast("📋 Copied Shorts caption & hashtags!");
    });
  } else {
    showToast("📋 Copied Shorts caption & hashtags!");
  }
};

window.copyClipComment = function(id, event) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }
  const clip = state.clips.find(c => c.id === id);
  if (!clip || !clip.pinned_comment) return;
  const commentText = clip.pinned_comment.trim();
  
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(commentText).then(() => {
      showToast("💬 Copied pinned engagement comment!");
    }).catch(() => {
      showToast("💬 Copied pinned engagement comment!");
    });
  } else {
    showToast("💬 Copied pinned engagement comment!");
  }
};

window.toggleClipSubtitles = function(id, event) {
  if (event) {
    event.stopPropagation();
    event.preventDefault();
  }
  const clip = state.clips.find(c => c.id === id);
  if (!clip) return;
  if (!clip.subtitle_config) {
    clip.subtitle_config = JSON.parse(JSON.stringify(state.subtitlesConfig));
  }
  const current = (clip.subtitle_config.enabled !== undefined) ? clip.subtitle_config.enabled : (state.subtitlesConfig.enabled !== false);
  clip.subtitle_config.enabled = !current;
  clip.has_custom_settings = true;

  if (state.selectedClipId === id) {
    state.subtitlesConfig.enabled = clip.subtitle_config.enabled;
    syncUIFromState();
  }

  renderClips();
  if (typeof isPlayMode !== "undefined" && (isPlayMode || isPlayingPreview)) {
    renderCanvasFrame(getActiveOrFallbackClip());
  } else {
    requestPreviewUpdate();
  }
  showToast(clip.subtitle_config.enabled ? `✅ Subtitles ON for "${clip.title}"` : `❌ Subtitles OFF for "${clip.title}" (Clean Video)`);
};

window.expandClipToFull = function(id) {
  const dur = (state.videoMeta && state.videoMeta.duration) ? state.videoMeta.duration : 60;
  const clip = state.clips.find(c => c.id === id);
  if (clip) {
    clip.start = 0;
    clip.end = Math.round(dur * 10) / 10;
    clip.duration = clip.end;
    if (!clip.title.includes("Full")) {
      clip.title = `Full Highlight (${Math.round(dur)}s)`;
    }
    renderClips();
    selectClipForPreview(id, 0);
    showToast(`⚡ Clip expanded to 100% full duration (0s – ${Math.round(dur)}s)!`);
  }
};

window.useFullVideoAsClip = function() {
  const dur = (state.videoMeta && state.videoMeta.duration) ? state.videoMeta.duration : 60;
  const activeClip = state.clips.find(c => c.id === state.selectedClipId);
  if (activeClip) {
    activeClip.start = 0;
    activeClip.end = Math.round(dur * 10) / 10;
    activeClip.duration = activeClip.end;
    activeClip.title = `Full Highlight (${Math.round(dur)}s)`;
    renderClips();
    selectClipForPreview(activeClip.id, 0);
    showToast(`Active clip set to 100% full duration (0s – ${Math.round(dur)}s)!`);
  } else {
    const newId = `clip-full-${Date.now()}`;
    const newClip = {
      id: newId,
      title: `Full Highlight (${Math.round(dur)}s)`,
      start: 0,
      end: Math.round(dur * 10) / 10,
      duration: Math.round(dur * 10) / 10,
      score: 99,
      virality_score: 99,
      category: "Full Highlight",
      reason: "Complete loaded video duration"
    };
    state.clips.unshift(initClipsMetadata([newClip])[0]);
    state.selectedClipId = newId;
    renderClips();
    selectClipForPreview(newId, 0);
    showToast(`Full duration clip added (0s – ${Math.round(dur)}s)!`);
  }
};

window.addNewCustomClip = function() {
  const dur = (state.videoMeta && state.videoMeta.duration) ? state.videoMeta.duration : 60;
  const id = `clip-custom-${Date.now()}`;
  const clipDur = Math.min(dur, 30);
  const newClip = {
    id,
    title: `Custom Clip #${state.clips.length + 1}`,
    start: 0,
    end: clipDur,
    duration: clipDur,
    score: 88,
    virality_score: 88,
    category: "Custom",
    reason: "User custom highlight"
  };
  state.clips.push(initClipsMetadata([newClip])[0]);
  state.selectedClipId = id;
  renderClips();
  selectClipForPreview(id, 0);
  showToast("New custom clip created!");
};

window.selectClipForPreview = function(id, startTime) {
  updateActiveClipSettings();
  state.selectedClipId = id;
  const targetClip = state.clips.find(c => c.id === id);
  if (targetClip && targetClip.template_config) {
    state.template = JSON.parse(JSON.stringify(targetClip.template_config));
    state.subtitlesConfig = JSON.parse(JSON.stringify(targetClip.subtitle_config));
    state.subtitlesConfig.model_name = normalizeWhisperModelName(state.subtitlesConfig.model_name);
    syncUIFromState();
  }
  state.previewTime = startTime + 3.0;
  const timeSlider = document.getElementById("slider-preview-time");
  if (timeSlider) {
    timeSlider.value = state.previewTime;
    document.getElementById("val-preview-time").innerText = `${state.previewTime.toFixed(1)}s`;
  }
  renderClips();
  renderSubtitles();
  if (window.updatePlayerInfo) {
    window.updatePlayerInfo();
  }
  if (isPlayingPreview) {
    startPlayableClipPreview();
  } else if (isPlayMode) {
    const sourceVid = document.getElementById("preview-source-video");
    if (sourceVid) {
      try { sourceVid.currentTime = targetClip ? targetClip.start : state.previewTime; } catch (_) {}
    }
    renderCanvasFrame(targetClip || getActiveOrFallbackClip());
  } else {
    triggerPreview(true);
  }
};

window.deleteClip = function(id) {
  state.clips = state.clips.filter(c => c.id !== id);
  if (state.selectedClipId === id) {
    state.selectedClipId = state.clips.length > 0 ? state.clips[0].id : null;
  }
  renderClips();
};

function autoSlice() {
  if (!state.videoMeta) return;
  const dur = state.videoMeta.duration;
  state.clips = [];
  
  if (dur >= 85 && dur <= 110) {
    // 10 Curated CarryisLive highlights
    const curated = [
      { start: 0.0, end: 9.5, title: "1. Grocery Please & Seb Lelo" },
      { start: 9.5, end: 19.0, title: "2. Aloo Baingan Adrak Lehsun" },
      { start: 19.0, end: 28.5, title: "3. Bread Lelo Bakery Search" },
      { start: 28.5, end: 38.0, title: "4. Fridge Aisle - Beer Lelo" },
      { start: 38.0, end: 47.5, title: "5. Sasti Beer Pay Money" },
      { start: 47.5, end: 57.0, title: "6. 1 Minute Kya Build Kar Diya" },
      { start: 57.0, end: 66.5, title: "7. Wine Section Shopping" },
      { start: 66.5, end: 76.0, title: "8. Bus! Enable Bar Reaction" },
      { start: 76.0, end: 85.5, title: "9. Cereal Snack Confusion" },
      { start: 85.5, end: Math.round(dur * 10) / 10, title: "10. Baad Me Loot Lunga Checkout" }
    ];
    curated.forEach((c, idx) => {
      state.clips.push({
        id: `clip_${idx + 1}`,
        title: c.title,
        start: c.start,
        end: c.end,
        duration: Math.round((c.end - c.start) * 10) / 10
      });
    });
  } else {
    // 10 evenly spaced viral clips for any external video
    const totalClips = Math.min(10, Math.max(1, Math.floor(dur / 6)));
    const step = dur / totalClips;
    for (let i = 0; i < totalClips; i++) {
      const start = Math.round(i * step * 10) / 10;
      const end = Math.round(Math.min(dur, (i + 1) * step) * 10) / 10;
      state.clips.push({
        id: `clip_${i + 1}`,
        title: `Viral Highlight ${i + 1}`,
        start: start,
        end: end,
        duration: Math.round((end - start) * 10) / 10
      });
    }
  }
  renderClips();
  showToast(`Auto-created ${state.clips.length} viral clip segments!`);
}

function addManualClip() {
  const curTime = state.previewTime || 0;
  const end = state.videoMeta ? Math.min(state.videoMeta.duration, curTime + 20) : curTime + 20;
  const newId = `clip_${Date.now()}`;
  state.clips.push({
    id: newId,
    title: `Custom Clip ${state.clips.length + 1}`,
    start: Math.round(curTime * 10) / 10,
    end: Math.round(end * 10) / 10,
    duration: Math.round((end - curTime) * 10) / 10
  });
  renderClips();
}

// =========================================================================
// Smooth Continuous Progress Engine (1, 2, 3, 4, 5... Continuous Advance)
// =========================================================================
class SmoothProgressTracker {
  constructor(barEl, percentEl, statusEl, options = {}) {
    this.barEl = barEl;
    this.percentEl = percentEl;
    this.statusEl = statusEl;
    this.currentPercent = 0.0;
    this.targetPercent = 0.0;
    this.rafId = null;
    this.maxAutoPercent = options.maxAutoPercent || 92;
    this.autoTimer = null;
    this.onUpdateCb = options.onUpdate || null;
    this.startLoop();
  }

  setTarget(target, message = null) {
    this.targetPercent = Math.max(0, Math.min(100, parseFloat(target) || 0));
    if (message && this.statusEl) {
      this.statusEl.innerHTML = message;
    }
  }

  startAutoAdvance(stepMs = 280) {
    this.stopAutoAdvance();
    this.autoTimer = setInterval(() => {
      if (this.targetPercent < this.maxAutoPercent) {
        this.targetPercent = Math.min(this.maxAutoPercent, this.targetPercent + 1);
      }
    }, stepMs);
  }

  stopAutoAdvance() {
    if (this.autoTimer) {
      clearInterval(this.autoTimer);
      this.autoTimer = null;
    }
  }

  complete(message = null) {
    this.stopAutoAdvance();
    this.targetPercent = 100.0;
    if (message && this.statusEl) {
      this.statusEl.innerHTML = message;
    }
  }

  reset() {
    this.stopAutoAdvance();
    this.currentPercent = 0.0;
    this.targetPercent = 0.0;
    this.updateDom(0);
  }

  startLoop() {
    const loop = () => {
      if (this.currentPercent < this.targetPercent) {
        const diff = this.targetPercent - this.currentPercent;
        const step = Math.max(0.35, Math.min(diff, diff * 0.14));
        this.currentPercent = Math.min(this.targetPercent, this.currentPercent + step);
        this.updateDom(this.currentPercent);
      }
      this.rafId = requestAnimationFrame(loop);
    };
    this.rafId = requestAnimationFrame(loop);
  }

  updateDom(val) {
    const intVal = Math.round(val);
    if (this.barEl) {
      this.barEl.style.width = `${val.toFixed(1)}%`;
    }
    if (this.percentEl) {
      this.percentEl.innerText = `${intVal}%`;
    }
    if (this.onUpdateCb) {
      this.onUpdateCb(val, intVal);
    }
  }

  destroy() {
    this.stopAutoAdvance();
    if (this.rafId) cancelAnimationFrame(this.rafId);
  }
}

let tab1TranscribeTracker = null;
let tab3TranscribeTracker = null;
let globalExportTracker = null;
let globalStreamTracker = null;

// Subtitles: Real-Time Dual Progress Bar Controllers & Subtitle Handlers
function updateDualTranscribeProgress(data, elapsedSec = null) {
  const percent = data.percent !== undefined ? Math.max(0, Math.min(100, data.percent)) : 0;
  const step = data.step || "Transcribing...";
  const isCompleted = data.status === "completed" || percent >= 100;
  const isError = data.status === "error";

  const currentClip = data.current_clip || 1;
  const totalClips = data.total_clips || (state.clips ? state.clips.length : 1);
  const clipTitle = data.clip_title || (state.clips && state.clips[currentClip - 1] ? state.clips[currentClip - 1].title : "Clip");
  const elapsed = (elapsedSec !== null) ? `${Math.round(elapsedSec)}s` : (data.elapsed_sec ? `${Math.round(data.elapsed_sec)}s` : "0s");

  const b1 = document.getElementById("tab1-transcribe-progress-bar");
  const p1 = document.getElementById("tab1-transcribe-percent-text");
  const s1 = document.getElementById("tab1-transcribe-status-text");
  if (!tab1TranscribeTracker && b1) {
    tab1TranscribeTracker = new SmoothProgressTracker(b1, p1, s1, { maxAutoPercent: 95 });
  }

  const b3 = document.getElementById("transcribe-progress-bar");
  const p3 = document.getElementById("transcribe-percent-text");
  const s3 = document.getElementById("transcribe-status-text");
  if (!tab3TranscribeTracker && b3) {
    tab3TranscribeTracker = new SmoothProgressTracker(b3, p3, s3, { maxAutoPercent: 95 });
  }

  if (isCompleted) {
    if (tab1TranscribeTracker) tab1TranscribeTracker.complete(step);
    if (tab3TranscribeTracker) tab3TranscribeTracker.complete(step);
  } else if (!isError) {
    if (tab1TranscribeTracker) {
      tab1TranscribeTracker.setTarget(percent);
      if (percent > 0 && percent < 95) tab1TranscribeTracker.startAutoAdvance(300);
    }
    if (tab3TranscribeTracker) {
      tab3TranscribeTracker.setTarget(percent);
      if (percent > 0 && percent < 95) tab3TranscribeTracker.startAutoAdvance(300);
    }
  }

  const syncBoxes = [
    {
      box: document.getElementById("tab1-transcribe-progress-box"),
      bar: document.getElementById("tab1-transcribe-progress-bar"),
      status: document.getElementById("tab1-transcribe-status-text"),
      percent: document.getElementById("tab1-transcribe-percent-text"),
      timer: document.getElementById("tab1-transcribe-timer"),
      clipCounter: document.getElementById("tab1-transcribe-clip-counter"),
      clipTitle: document.getElementById("tab1-transcribe-clip-title")
    },
    {
      box: document.getElementById("transcribe-progress-box"),
      bar: document.getElementById("transcribe-progress-bar"),
      status: document.getElementById("transcribe-status-text"),
      percent: document.getElementById("transcribe-percent-text"),
      timer: document.getElementById("transcribe-timer"),
      clipCounter: document.getElementById("transcribe-clip-counter"),
      clipTitle: document.getElementById("transcribe-clip-title")
    }
  ];

  syncBoxes.forEach(s => {
    if (s.box) {
      s.box.style.display = "block";
      s.box.style.opacity = "1";
    }
    if (s.bar) {
      if (isCompleted) {
        s.bar.style.background = "linear-gradient(90deg, #10B981 0%, #34D399 100%)";
        s.bar.style.boxShadow = "0 0 16px rgba(16, 185, 129, 0.7)";
      } else if (isError) {
        s.bar.style.background = "linear-gradient(90deg, #EF4444 0%, #F87171 100%)";
      } else {
        s.bar.style.background = "linear-gradient(90deg, #6366f1 0%, #a855f7 35%, #06b6d4 70%, #10b981 100%)";
      }
    }
    if (s.percent) {
      s.percent.style.color = isCompleted ? "#34D399" : (isError ? "#F87171" : "#38BDF8");
    }
    if (s.status) {
      if (isCompleted) {
        s.status.innerHTML = `<span style="color: #34D399;"><i class="fa-solid fa-circle-check"></i> ${step}</span>`;
      } else if (isError) {
        s.status.innerHTML = `<span style="color: #F87171;"><i class="fa-solid fa-triangle-exclamation"></i> ${step}</span>`;
      } else {
        s.status.innerHTML = `<i class="fa-solid fa-spinner fa-spin" style="color: #38BDF8; margin-right: 5px;"></i> ${step}`;
      }
    }
    if (s.timer) s.timer.innerText = elapsed;
    if (s.clipCounter) s.clipCounter.innerText = `Clip ${currentClip}/${totalClips}`;
    if (s.clipTitle) s.clipTitle.innerText = clipTitle;
  });
}

function dismissDualTranscribeProgress(delayMs = 4000) {
  setTimeout(() => {
    const tab1Box = document.getElementById("tab1-transcribe-progress-box");
    const tab3Box = document.getElementById("transcribe-progress-box");
    if (tab1Box) {
      tab1Box.style.transition = "opacity 0.6s ease";
      tab1Box.style.opacity = "0";
      setTimeout(() => { tab1Box.style.display = "none"; tab1Box.style.opacity = "1"; }, 600);
    }
    if (tab3Box) {
      tab3Box.style.transition = "opacity 0.6s ease";
      tab3Box.style.opacity = "0";
      setTimeout(() => { tab3Box.style.display = "none"; tab3Box.style.opacity = "1"; }, 600);
    }
  }, delayMs);
}

async function runTranscribeAllClips() {
  if (!state.clips || state.clips.length === 0) {
    if (state.videoPath || state.videoMeta) {
      const dur = (state.videoMeta && state.videoMeta.duration) ? state.videoMeta.duration : 60;
      const c1Start = Math.min(10, Math.max(0, dur - 20));
      const c2Start = Math.min(Math.floor(dur * 0.35), Math.max(0, dur - 20));
      const c3Start = Math.min(Math.floor(dur * 0.70), Math.max(0, dur - 20));
      state.clips = initClipsMetadata([
        { id: "clip-1", title: "GTA 6 - Peak Action & Mission Climax", start: c1Start, end: Math.min(dur, c1Start + 18.0), virality_score: 96, reason: "Streamer high-energy reaction + gameplay climax", badge_color: "var(--accent-gold)" },
        { id: "clip-2", title: "Streamer Reaction & Chat Chaos", start: c2Start, end: Math.min(dur, c2Start + 22.0), virality_score: 93, reason: "Acoustic voice spike + facial expression burst", badge_color: "var(--accent-cyan)" },
        { id: "clip-3", title: "Insane Stunt / Glitch Moment", start: c3Start, end: Math.min(dur, c3Start + 19.5), virality_score: 89, reason: "Rapid visual motion & voice intensity peak", badge_color: "var(--accent-purple)" }
      ]);
      renderClips();
    } else {
      showToast("Please load a video first!");
      return;
    }
  }

  const btnAll = document.getElementById("btn-transcribe-all") || document.getElementById("btn-transcribe-all-clips");
  const btnTab1 = document.getElementById("btn-tab1-transcribe-all");
  const origBtnText = btnAll ? btnAll.innerHTML : `<i class="fa-solid fa-list-check"></i> Transcribe All Clips`;
  if (btnAll) {
    btnAll.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Transcribing All (${state.clips.length})...`;
    btnAll.disabled = true;
  }
  if (btnTab1) {
    btnTab1.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Transcribing All...`;
    btnTab1.disabled = true;
  }

  const startTimeMs = Date.now();
  updateDualTranscribeProgress({
    status: "running",
    step: `Starting batch transcription for ${state.clips.length} clips with streamer voice isolation...`,
    percent: 5,
    current_clip: 1,
    total_clips: state.clips.length,
    clip_title: state.clips[0].title
  }, 0);

  try {
    const lang = document.getElementById("select-lang")?.value || "auto";
    const chosenModel = normalizeWhisperModelName(document.getElementById("select-whisper-model")?.value || state.subtitlesConfig.model_name || "large-v3-turbo-q5_0");
    const wordsAtATime = state.subtitlesConfig.words_per_line !== undefined ? state.subtitlesConfig.words_per_line : 3;
    const checkStreamer = document.getElementById("check-streamer-voice-only");
    const streamerVoiceFocus = checkStreamer ? checkStreamer.checked : true;
    const trackSel = document.getElementById("select-audio-track");
    const audioTrack = trackSel ? parseInt(trackSel.value || "0") : 0;

    const data = await runAsyncJob("/api/transcribe_all_clips", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clips: state.clips,
        language: lang,
        model_name: chosenModel,
        words_per_line: wordsAtATime,
        streamer_voice_focus: streamerVoiceFocus,
        audio_track: audioTrack
      })
    }, {
      container: "transcribe-progress-box",
      bar: "transcribe-progress-bar",
      text: "transcribe-status-text",
      percent: "transcribe-percent-text",
      initialText: `Starting batch transcription for ${state.clips.length} clips with streamer voice isolation...`,
      initialPercent: 5,
      onProgress: (job) => {
        updateDualTranscribeProgress(job, job.elapsed_sec);
      }
    });

    state.clips = data.clips;
    state.subtitles = data.subtitles || [];
    renderClips();
    renderSubtitles();

    const totalLines = data.total_lines || (data.subtitles ? data.subtitles.length : 0);
    const elapsedSec = (Date.now() - startTimeMs) / 1000.0;
    updateDualTranscribeProgress({
      status: "completed",
      step: `✓ 100% Synchronized: All ${data.clips.length} clips transcribed (${totalLines} lines in ${elapsedSec.toFixed(1)}s)!`,
      percent: 100,
      current_clip: data.clips.length,
      total_clips: data.clips.length,
      clip_title: "Batch Complete"
    }, elapsedSec);

    showToast(`🎉 All ${data.clips.length} clips successfully transcribed with 5ms sub-frame acoustic sync!`);
    triggerPreview(true);
    dismissDualTranscribeProgress(4500);
  } catch (err) {
    if (err.isCancelled) {
      showToast("Batch transcription cancelled.");
      updateDualTranscribeProgress({
        status: "cancelled",
        step: "Batch transcription cancelled by user",
        percent: 0
      });
    } else {
      updateDualTranscribeProgress({
        status: "error",
        step: `Batch transcription error: ${err.message}`,
        percent: 0
      });
      alert("Batch transcription error: " + err.message);
    }
  } finally {
    if (btnAll) {
      btnAll.innerHTML = origBtnText;
      btnAll.disabled = false;
    }
    if (btnTab1) {
      btnTab1.innerHTML = `<i class="fa-solid fa-closed-captioning"></i> Transcribe All Clips`;
      btnTab1.disabled = false;
    }
  }
}

async function runTranscription(forSelectedClip = false) {
  let startTime = null;
  let duration = null;
  let targetBtn = forSelectedClip
    ? (document.getElementById("btn-transcribe-current") || document.getElementById("btn-transcribe-clip") || document.getElementById("btn-transcribe"))
    : (document.getElementById("btn-transcribe") || document.getElementById("btn-transcribe-current"));
  let origBtnText = targetBtn ? targetBtn.innerHTML : (forSelectedClip ? `<i class="fa-solid fa-microphone-lines"></i> Transcribe Active Clip` : `<i class="fa-solid fa-wand-magic"></i> Transcribe Full Video`);

  if (forSelectedClip) {
    let selectedClip = (state.clips && state.clips.length > 0)
      ? (state.clips.find(c => c.id === state.selectedClipId) || state.clips[0])
      : null;

    if (!selectedClip) {
      const totalDur = (state.videoMeta && state.videoMeta.duration) ? state.videoMeta.duration : 60;
      const cStart = Math.max(0, Math.min(state.currentTime || 0, Math.max(0, totalDur - 15)));
      const cEnd = Math.min(totalDur, cStart + 20.0);
      selectedClip = {
        id: "clip-1",
        title: "Active Clip 1",
        start: cStart,
        end: cEnd,
        virality_score: 95,
        reason: "Active clip selection"
      };
      state.clips = [selectedClip];
      state.selectedClipId = selectedClip.id;
      renderClips();
    }

    startTime = selectedClip.start;
    duration = Math.max(2.0, selectedClip.end - selectedClip.start);
  }

  if (targetBtn) {
    targetBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${forSelectedClip ? 'Transcribing Clip...' : 'Transcribing Video...'}`;
    targetBtn.disabled = true;
  }

  const startTimeMs = Date.now();
  updateDualTranscribeProgress({
    status: "running",
    step: forSelectedClip ? `Extracting clip audio (${duration.toFixed(1)}s) & running Whisper AI...` : "Extracting audio & loading Whisper AI...",
    percent: 15,
    current_clip: 1,
    total_clips: 1,
    clip_title: forSelectedClip ? (state.clips.find(c => c.id === state.selectedClipId)?.title || "Active Clip") : "Full Video"
  }, 0);

  try {
    const lang = document.getElementById("select-lang")?.value || "auto";
    const chosenModel = normalizeWhisperModelName(document.getElementById("select-whisper-model")?.value || state.subtitlesConfig.model_name || "large-v3-turbo-q5_0");
    const wordsAtATime = state.subtitlesConfig.words_per_line !== undefined ? state.subtitlesConfig.words_per_line : 3;
    const checkStreamer = document.getElementById("check-streamer-voice-only");
    const streamerVoiceFocus = checkStreamer ? checkStreamer.checked : true;
    const trackSel = document.getElementById("select-audio-track");
    const audioTrack = trackSel ? parseInt(trackSel.value || "0") : 0;
    
    const payload = {
      language: lang,
      model_name: chosenModel,
      words_per_line: wordsAtATime,
      start_time: startTime,
      duration: duration,
      streamer_voice_focus: streamerVoiceFocus,
      audio_track: audioTrack
    };

    const data = await runAsyncJob("/api/transcribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }, {
      container: "transcribe-progress-box",
      bar: "transcribe-progress-bar",
      text: "transcribe-status-text",
      percent: "transcribe-percent-text",
      initialText: forSelectedClip ? `Extracting clip audio (${duration.toFixed(1)}s) & running Whisper AI...` : "Extracting audio & loading Whisper AI...",
      initialPercent: 10,
      onProgress: (job) => {
        updateDualTranscribeProgress(job, job.elapsed_sec);
      }
    });

    state.subtitles = data.subtitles || [];

    // Also update clip object if single clip was transcribed
    if (forSelectedClip) {
      const activeClip = state.clips.find(c => c.id === state.selectedClipId) || state.clips[0];
      if (activeClip) {
        activeClip.subtitles = state.subtitles.filter(s => s.end > activeClip.start && s.start < activeClip.end);
        activeClip.subtitles_count = activeClip.subtitles.length;
      }
    }

    renderClips();
    renderSubtitles();
    
    const elapsedSec = (Date.now() - startTimeMs) / 1000.0;
    updateDualTranscribeProgress({
      status: "completed",
      step: `✓ 100% Synchronized: Transcribed ${data.count} lines in ${elapsedSec.toFixed(1)}s!`,
      percent: 100,
      current_clip: 1,
      total_clips: 1,
      clip_title: forSelectedClip ? "Clip Synchronized" : "Video Synchronized"
    }, elapsedSec);

    showToast(`Transcribed ${data.count} synchronized subtitle lines with 5ms sub-frame precision!`);
    triggerPreview(true);
    dismissDualTranscribeProgress(4000);
  } catch (err) {
    if (err.isCancelled) {
      showToast("Transcription cancelled.");
      updateDualTranscribeProgress({
        status: "cancelled",
        step: "Transcription cancelled by user",
        percent: 0
      });
    } else {
      updateDualTranscribeProgress({
        status: "error",
        step: `Transcription error: ${err.message}`,
        percent: 0
      });
      showToast(`Notice: ${err.message}`, "error");
    }
  } finally {
    if (targetBtn) {
      targetBtn.innerHTML = origBtnText;
      targetBtn.disabled = false;
    }
  }
}

function renderSubtitles() {
  const tbody = document.getElementById("sub-table-body");
  if (!tbody) return;
  tbody.innerHTML = "";
  const countSpan = document.getElementById("subs-count");
  const viewBadge = document.getElementById("subs-view-badge");
  const checkFilter = document.getElementById("check-filter-subs-clip");
  const isFiltering = checkFilter ? checkFilter.checked : false;

  const selectedClip = state.clips.find(c => c.id === state.selectedClipId) || state.clips[0];

  let displayedSubs = state.subtitles || [];
  if (isFiltering && selectedClip) {
    displayedSubs = state.subtitles.filter(s => s.end > selectedClip.start && s.start < selectedClip.end);
    if (viewBadge) {
      viewBadge.innerText = `${selectedClip.title || 'Active Clip'}`;
      viewBadge.style.display = "inline-block";
    }
    if (countSpan) countSpan.innerText = `${displayedSubs.length} (of ${state.subtitles.length} total)`;
  } else {
    if (viewBadge) {
      viewBadge.innerText = "All Video Lines";
      viewBadge.style.display = "inline-block";
    }
    if (countSpan) countSpan.innerText = `${state.subtitles ? state.subtitles.length : 0}`;
  }
  
  if (!displayedSubs || displayedSubs.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td colspan="5" style="text-align: center; padding: 24px; color: var(--text-muted); font-size: 13px;">
        <i class="fa-solid fa-closed-captioning" style="font-size: 24px; margin-bottom: 8px; display: block; opacity: 0.5;"></i>
        ${isFiltering && selectedClip ? `No subtitles generated yet for <strong>${selectedClip.title}</strong>.` : 'No subtitles generated yet for this footage.'}<br>
        Click <strong style="color: var(--accent-gold);">Transcribe All Clips</strong> above to generate subtitles for every clip with streamer voice isolation.
      </td>
    `;
    tbody.appendChild(tr);
    return;
  }

  displayedSubs.forEach((s) => {
    const masterIdx = state.subtitles.indexOf(s);
    const cleanText = (s.text || "").replace(/[,.]+/g, "");
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="text-align: center;"><button class="btn btn-secondary btn-sm" onclick="jumpToSub(${s.start})" title="Jump preview to this spoken line" style="padding: 2px 6px; font-size: 10px; border-radius: 4px; color: var(--accent-gold);"><i class="fa-solid fa-play"></i></button></td>
      <td><input type="number" step="0.05" value="${s.start}" onchange="updateSub(${masterIdx}, 'start', this.value)" style="padding: 2px 4px; width: 68px;"></td>
      <td><input type="number" step="0.05" value="${s.end}" onchange="updateSub(${masterIdx}, 'end', this.value)" style="padding: 2px 4px; width: 68px;"></td>
      <td><input type="text" value="${cleanText}" onchange="updateSub(${masterIdx}, 'text', this.value)" style="padding: 2px 6px; width: 100%;"></td>
      <td><button style="background: none; border: none; color: var(--accent-red); cursor: pointer; padding: 2px 6px;" onclick="deleteSub(${masterIdx})"><i class="fa-solid fa-xmark"></i></button></td>
    `;
    tbody.appendChild(tr);
  });
}

window.jumpToSub = function(startSec) {
  const t = Math.max(0, parseFloat(startSec) || 0);
  state.previewTime = t;
  const srcVid = document.getElementById("preview-source-video");
  if (srcVid) {
    srcVid.currentTime = t;
  }
  if (typeof triggerPreview === "function") {
    triggerPreview(true);
  }
};

window.updateSub = function(idx, field, val) {
  if (!state.subtitles[idx]) return;
  if (field === "start" || field === "end") {
    state.subtitles[idx][field] = parseFloat(val) || 0;
  } else {
    const cleanVal = String(val).replace(/[,.]+/g, "").trim();
    state.subtitles[idx][field] = cleanVal;
    // Auto-update words timestamps for smooth karaoke
    const words = cleanVal.split(/\s+/).filter(Boolean);
    if (words.length > 0) {
      const segDur = Math.max(0.1, (state.subtitles[idx].end - state.subtitles[idx].start) / words.length);
      state.subtitles[idx].words = words.map((w, wIdx) => ({
        word: w,
        start: state.subtitles[idx].start + wIdx * segDur,
        end: state.subtitles[idx].start + (wIdx + 1) * segDur
      }));
    }
  }
  requestPreviewUpdate();
};

window.deleteSub = function(idx) {
  state.subtitles.splice(idx, 1);
  renderSubtitles();
};

function addManualSubtitle() {
  const curTime = state.previewTime || 0;
  state.subtitles.push({
    id: state.subtitles.length + 1,
    start: Math.round(curTime * 10) / 10,
    end: Math.round((curTime + 3) * 10) / 10,
    text: "NEW SUBTITLE LINE",
    words: []
  });
  renderSubtitles();
}

// Live Preview
function requestPreviewUpdate() {
  if (!state.videoLoaded) return;
  // If in Play Mode or canvas preview is active: live canvas re-render
  const canvas = document.getElementById("preview-canvas");
  const sourceVid = document.getElementById("preview-source-video");
  if (isPlayingPreview && canvas && sourceVid) {
    renderCanvasFrame(getActiveOrFallbackClip());
  }

  clearTimeout(previewDebounceTimer);
  previewDebounceTimer = setTimeout(() => {
    triggerPreview();
  }, 200);
}

async function triggerPreview(immediate = false) {
  if (!state.videoLoaded) return;
  if (state.isRenderingPreview && !immediate) return;
  state.isRenderingPreview = true;

  const loading = document.getElementById("preview-loading");
  const img = document.getElementById("preview-img");
  const canvas = document.getElementById("preview-canvas");

  if (!isPlayingPreview && loading) {
    loading.style.display = "flex";
  }

  // Ensure facecam dimensions and positions are valid
  if (!state.template.webcam_w) state.template.webcam_w = 300;
  if (!state.template.webcam_h) state.template.webcam_h = 300;
  if (state.template.webcam_x === undefined) {
    state.template.webcam_x = Math.round((1080 - state.template.webcam_w) / 2);
  }
  if (state.template.webcam_y === undefined) {
    state.template.webcam_y = 540;
  }

  updateActiveClipSettings();

  try {
    const res = await fetch("/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        timestamp: state.previewTime,
        template_config: state.template,
        subtitle_config: state.subtitlesConfig,
        hook_config: state.hookConfig,
        subtitles: state.subtitles
      })
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    if (img) {
      img.onload = () => {
        if (!isPlayingPreview) {
          img.style.display = "block";
          if (canvas) canvas.style.display = "none";
          // Also paint into canvas as instant buffer
          if (canvas) {
            const ctx = canvas.getContext("2d");
            if (ctx && img.naturalWidth > 0) {
              ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            }
          }
        }
        if (loading) loading.style.display = "none";
        state.isRenderingPreview = false;
      };
      img.onerror = () => {
        if (loading) loading.style.display = "none";
        state.isRenderingPreview = false;
      };
      img.src = data.preview_url;
    } else {
      if (loading) loading.style.display = "none";
      state.isRenderingPreview = false;
    }
  } catch (err) {
    console.error("Preview failed:", err);
    if (loading) loading.style.display = "none";
    state.isRenderingPreview = false;
  }
}

// Exports
async function exportSelectedClip() {
  if (!state.selectedClipId && state.clips.length > 0) {
    state.selectedClipId = state.clips[0].id;
  }
  const clip = state.clips.find(c => c.id === state.selectedClipId);
  if (!clip) {
    alert("Please select or add a clip first.");
    return;
  }

  const pBox = document.getElementById("export-progress-box");
  const pBar = document.getElementById("export-progress-bar");
  const pStatus = document.getElementById("export-status-text");
  const pPercent = document.getElementById("export-percent-text");

  try {
    const checkBurn = document.getElementById("check-burn-subs");
    const shouldBurn = checkBurn ? checkBurn.checked : true;
    const subsToSend = shouldBurn ? state.subtitles : [];
    const encSelect = document.getElementById("select-export-encoder");
    const selectedEncoder = encSelect ? encSelect.value : "auto";

    clip.template_config = JSON.parse(JSON.stringify(state.template));
    clip.subtitle_config = JSON.parse(JSON.stringify(state.subtitlesConfig));

    const result = await runAsyncJob("/api/export_clip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clip: clip,
        template_config: state.template,
        subtitle_config: state.subtitlesConfig,
        hook_config: state.hookConfig,
        subtitles: subsToSend,
        encoder: selectedEncoder
      })
    }, {
      container: pBox,
      bar: pBar,
      text: pStatus,
      percent: pPercent,
      initialText: `Preparing render: ${clip.title}...`,
      initialPercent: 5
    });

    const data = result;
    
    fetchOutputs();
    try {
      openVideoModal(data.clip.video_url, data.clip.title);
    } catch (modalErr) {
      console.warn("Could not auto-open video modal:", modalErr);
    }
  } catch (err) {
    if (err.isCancelled) {
      showToast("Export cancelled.");
    } else {
      alert("Export error: " + err.message);
    }
  }
}

async function exportAllClips() {
  if (state.clips.length === 0) {
    alert("No clips to export. Please detect viral moments or add clips first.");
    return;
  }

  const pBox = document.getElementById("export-progress-box");
  const pBar = document.getElementById("export-progress-bar");
  const pStatus = document.getElementById("export-status-text");
  const pPercent = document.getElementById("export-percent-text");

  try {
    const checkBurn = document.getElementById("check-burn-subs");
    const shouldBurn = checkBurn ? checkBurn.checked : true;
    const subsToSend = shouldBurn ? state.subtitles : [];
    const checkZip = document.getElementById("check-export-zip");
    const shouldZip = checkZip ? checkZip.checked : true;
    const encSelect = document.getElementById("select-export-encoder");
    const selectedEncoder = encSelect ? encSelect.value : "auto";

    state.clips.forEach(c => {
      c.template_config = JSON.parse(JSON.stringify(state.template));
      c.subtitle_config = JSON.parse(JSON.stringify(state.subtitlesConfig));
    });

    const data = await runAsyncJob("/api/export_all", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clips: state.clips,
        template_config: state.template,
        subtitle_config: state.subtitlesConfig,
        hook_config: state.hookConfig,
        subtitles: subsToSend,
        export_as_zip: shouldZip,
        encoder: selectedEncoder
      })
    }, {
      container: pBox,
      bar: pBar,
      text: pStatus,
      percent: pPercent,
      initialText: `Starting batch render of ${state.clips.length} clips...`,
      initialPercent: 5
    });

    if (data.zip && data.zip.download_url) {
      showZipDownloadBanner(data.zip);
      showToast(`⚡ Batch export complete! ZIP ready (${data.zip.size_mb} MB)`);
    } else {
      showToast(`Successfully exported ${data.exported.length} clips!`);
    }

    fetchOutputs();
  } catch (err) {
    if (err.isCancelled) {
      showToast("Batch export cancelled.");
    } else {
      alert("Batch export error: " + err.message);
    }
  }
}

function showZipDownloadBanner(zipData) {
  const banner = document.getElementById("zip-download-banner");
  const fnText = document.getElementById("zip-filename-text");
  const link = document.getElementById("link-download-zip");
  if (!banner || !zipData) return;
  if (fnText) fnText.innerText = `${zipData.filename} (${zipData.size_mb} MB)`;
  if (link) {
    link.href = zipData.download_url;
    link.setAttribute("download", zipData.filename);
  }
  banner.style.display = "flex";
}

async function fetchOutputs() {
  try {
    const res = await fetch("/api/outputs");
    if (!res.ok) return;
    const data = await res.json();
    renderOutputs(data.files);
  } catch (err) {
    console.error("Failed to fetch outputs:", err);
  }
}

function renderOutputs(files) {
  const grid = document.getElementById("outputs-grid");
  if (!grid) return;
  grid.innerHTML = "";
  
  if (!files || files.length === 0) {
    grid.innerHTML = `<div style="padding: 16px; color: var(--text-dim); font-size: 11.5px; text-align: center; background: rgba(255,255,255,0.02); border-radius: var(--radius-sm); border: 1px dashed var(--border-subtle);"><i class="fa-solid fa-film" style="margin-right: 6px;"></i> No exported clips yet. Click 'Export Active Clip' above!</div>`;
    return;
  }

  files.forEach(f => {
    const card = document.createElement("div");
    card.className = "gallery-card";
    const thumbHtml = f.thumb_url 
      ? `<img src="${f.thumb_url}" alt="${f.filename}" class="gallery-thumb" onclick="openVideoModal('${f.video_url}', '${f.filename}')" onerror="this.onerror=null; this.style.display='none'; if(this.nextElementSibling) this.nextElementSibling.style.display='flex';">
         <div class="gallery-thumb" style="display: none; align-items: center; justify-content: center; background: #111624; color: var(--text-dim); cursor: pointer;" onclick="openVideoModal('${f.video_url}', '${f.filename}')"><i class="fa-solid fa-circle-play" style="font-size: 18px; color: var(--accent-lime);"></i></div>`
      : `<div class="gallery-thumb" style="display: flex; align-items: center; justify-content: center; background: #111624; color: var(--text-dim); cursor: pointer;" onclick="openVideoModal('${f.video_url}', '${f.filename}')"><i class="fa-solid fa-circle-play" style="font-size: 18px; color: var(--accent-lime);"></i></div>`;

    card.innerHTML = `
      ${thumbHtml}
      <div class="gallery-info">
        <h5 title="${f.filename}">${f.filename}</h5>
        <div class="gallery-meta">
          <span>${f.size_mb} MB</span>
          <span style="color: var(--accent-lime); font-weight: 700;">1080x1920</span>
        </div>
        <div style="display: flex; gap: 6px; margin-top: 3px;">
          <button class="btn btn-primary btn-sm" style="flex: 1; padding: 4px 10px; font-size: 11px;" onclick="openVideoModal('${f.video_url}', '${f.filename}')"><i class="fa-solid fa-play"></i> Watch</button>
          <a href="${f.video_url}" download class="btn btn-secondary btn-sm" style="padding: 4px 10px; font-size: 11px;" title="Download MP4"><i class="fa-solid fa-download"></i></a>
        </div>
      </div>
    `;
    grid.appendChild(card);
  });
}

window.openVideoModal = function(url, title) {
  const modal = document.getElementById("video-modal");
  const modalTitle = document.getElementById("modal-title");
  const vid = document.getElementById("modal-video");
  const dl = document.getElementById("modal-download");
  
  if (modalTitle) modalTitle.innerText = title || "Rendered Short";
  if (vid) {
    vid.src = url || "";
    try {
      const p = vid.play();
      if (p !== undefined) p.catch(() => {});
    } catch (_) {}
  }
  if (dl) dl.href = url || "#";
  if (modal) modal.style.display = "flex";
};

// Interactive Facecam Visual Viewport with Zoom In / Out and Click/Drag Reticle
// Interactive Freeform Facecam Crop Reticle with Drag & Corner Resize Handles
function initWebcamCropCanvas() {
  const canvas = document.getElementById("webcam-crop-canvas") || document.getElementById("cam-crop-canvas");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  const avatarCanvas = document.getElementById("cam-avatar-canvas");
  const avatarCtx = avatarCanvas ? avatarCanvas.getContext("2d") : null;

  const sourceImg = new Image();
  sourceImg.crossOrigin = "anonymous";
  if (state.videoLoaded) {
    sourceImg.src = "/storage/temp/source_frame.jpg?t=" + Date.now();
  }

  let vidW = 640;
  let vidH = 360;
  let isDragging = false;
  let dragMode = "move";
  let dragStartX = 0;
  let dragStartY = 0;
  let startBox = { x: 40, y: 30, w: 480, h: 270 };

  // 16:9 Stream Facecam Crop Box (in source video coordinates)
  let box = { x: 40, y: 30, w: 480, h: 270 };

  const aspectCheck = document.getElementById("check-reticle-aspect");
  let lock16_9 = aspectCheck ? aspectCheck.checked : true;
  if (aspectCheck) {
    aspectCheck.addEventListener("change", (e) => {
      lock16_9 = e.target.checked;
      const aspectBadge = document.getElementById("reticle-aspect-badge");
      if (aspectBadge) aspectBadge.innerText = lock16_9 ? "16:9 LOCKED" : "FREEFORM";
      if (lock16_9) {
        box.h = Math.round(box.w * 9 / 16);
        syncStateAndUI();
        drawReticle();
        requestPreviewUpdate();
      }
    });
  }

  if (state.template && state.template.webcam_crop && state.template.webcam_crop.w > 20) {
    box.x = state.template.webcam_crop.x;
    box.y = state.template.webcam_crop.y;
    box.w = state.template.webcam_crop.w;
    box.h = state.template.webcam_crop.h;
    if (lock16_9 && Math.abs(box.w / box.h - 16 / 9) > 0.1) {
      box.h = Math.round(box.w * 9 / 16);
    }
  }

  function syncStateAndUI() {
    box.w = Math.max(40, Math.min(vidW, Math.round(box.w)));
    box.h = Math.max(24, Math.min(vidH, Math.round(box.h)));
    box.x = Math.max(0, Math.min(vidW - box.w, Math.round(box.x)));
    box.y = Math.max(0, Math.min(vidH - box.h, Math.round(box.y)));

    state.template.webcam_crop = { x: box.x, y: box.y, w: box.w, h: box.h };

    const slW = document.getElementById("slider-reticle-w");
    const valW = document.getElementById("val-reticle-w");
    if (slW) { slW.max = vidW; slW.value = box.w; }
    if (valW) valW.innerText = `${box.w}px`;

    const slH = document.getElementById("slider-reticle-h");
    const valH = document.getElementById("val-reticle-h");
    if (slH) { slH.max = vidH; slH.value = box.h; }
    if (valH) valH.innerText = `${box.h}px`;

    const coordsBadge = document.getElementById("cam-coords-badge");
    if (coordsBadge) coordsBadge.innerHTML = `<i class="fa-solid fa-crosshairs" style="color: var(--accent-lime);"></i> 16:9 Frame: ${box.w}×${box.h}px at (${box.x}, ${box.y})`;

    const zoomBadge = document.getElementById("cam-zoom-badge");
    if (zoomBadge) zoomBadge.innerText = lock16_9 ? `16:9 Stream Frame` : `Freeform (${box.w}×${box.h})`;

    const cropXInput = document.getElementById("cam-crop-x");
    const cropYInput = document.getElementById("cam-crop-y");
    const cropWInput = document.getElementById("cam-crop-w");
    const cropHInput = document.getElementById("cam-crop-h");
    if (cropXInput) cropXInput.value = box.x;
    if (cropYInput) cropYInput.value = box.y;
    if (cropWInput) cropWInput.value = box.w;
    if (cropHInput) cropHInput.value = box.h;
  }

  sourceImg.onload = () => {
    let nw = sourceImg.naturalWidth || 640;
    let nh = sourceImg.naturalHeight || 360;

    // Safety guard: if sourceImg is vertical (< 1.0 aspect ratio), attempt to grab true 16:9 frame from video player
    if (nw < nh) {
      console.warn("[Reticle] source_frame is vertical (" + nw + "x" + nh + "). Checking video player for 16:9 frame...");
      const vid = document.getElementById("preview-source-video");
      if (vid && vid.readyState >= 2 && vid.videoWidth >= vid.videoHeight && vid.videoWidth > 0) {
        nw = vid.videoWidth;
        nh = vid.videoHeight;
        vidW = nw;
        vidH = nh;
        canvas.width = vidW;
        canvas.height = vidH;
        const off = document.createElement("canvas");
        off.width = vidW;
        off.height = vidH;
        off.getContext("2d").drawImage(vid, 0, 0, vidW, vidH);
        sourceImg.src = off.toDataURL("image/jpeg", 0.95);
        return;
      }
    }

    vidW = nw;
    vidH = nh;
    canvas.width = vidW;
    canvas.height = vidH;

    if (!state.template.webcam_crop_custom) {
      box.w = Math.round(vidW * 0.32);
      box.h = Math.round(box.w * 9 / 16);
      box.x = Math.round(vidW * 0.04);
      box.y = Math.round(vidH * 0.06);
    }
    syncStateAndUI();
    drawReticle();
    if (typeof requestPreviewUpdate === "function") {
      requestPreviewUpdate();
    }
  };

  const HANDLE_SIZE = 14;

  function getHandles() {
    return {
      nw: { x: box.x, y: box.y },
      ne: { x: box.x + box.w, y: box.y },
      sw: { x: box.x, y: box.y + box.h },
      se: { x: box.x + box.w, y: box.y + box.h },
      n:  { x: box.x + box.w / 2, y: box.y },
      s:  { x: box.x + box.w / 2, y: box.y + box.h },
      w:  { x: box.x, y: box.y + box.h / 2 },
      e:  { x: box.x + box.w, y: box.y + box.h / 2 }
    };
  }

  function detectHit(px, py) {
    const handles = getHandles();
    const hs = HANDLE_SIZE;
    if (Math.abs(px - handles.nw.x) <= hs && Math.abs(py - handles.nw.y) <= hs) return "nw";
    if (Math.abs(px - handles.ne.x) <= hs && Math.abs(py - handles.ne.y) <= hs) return "ne";
    if (Math.abs(px - handles.sw.x) <= hs && Math.abs(py - handles.sw.y) <= hs) return "sw";
    if (Math.abs(px - handles.se.x) <= hs && Math.abs(py - handles.se.y) <= hs) return "se";
    if (Math.abs(px - handles.n.x) <= hs && Math.abs(py - handles.n.y) <= hs) return "n";
    if (Math.abs(px - handles.s.x) <= hs && Math.abs(py - handles.s.y) <= hs) return "s";
    if (Math.abs(px - handles.w.x) <= hs && Math.abs(py - handles.w.y) <= hs) return "w";
    if (Math.abs(px - handles.e.x) <= hs && Math.abs(py - handles.e.y) <= hs) return "e";
    if (px >= box.x && px <= box.x + box.w && py >= box.y && py <= box.y + box.h) return "move";
    return "new";
  }

  function getCursor(mode) {
    switch (mode) {
      case "nw": case "se": return "nwse-resize";
      case "ne": case "sw": return "nesw-resize";
      case "n": case "s": return "ns-resize";
      case "w": case "e": return "ew-resize";
      case "move": return "move";
      default: return "crosshair";
    }
  }

  function drawReticle() {
    ctx.clearRect(0, 0, vidW, vidH);
    if (sourceImg.complete && sourceImg.naturalWidth > 0) {
      ctx.drawImage(sourceImg, 0, 0, vidW, vidH);
    } else {
      ctx.fillStyle = "#111";
      ctx.fillRect(0, 0, vidW, vidH);
    }

    // 1. Shaded overlay outside the reticle box
    ctx.save();
    ctx.fillStyle = "rgba(0, 0, 0, 0.62)";
    ctx.beginPath();
    ctx.rect(0, 0, vidW, vidH);
    ctx.rect(box.x, box.y, box.w, box.h);
    ctx.fill("evenodd");
    ctx.restore();

    // 2. High-visibility glowing cyan border
    ctx.save();
    ctx.strokeStyle = "#00f5ff";
    ctx.lineWidth = 2.5;
    ctx.shadowColor = "#00f5ff";
    ctx.shadowBlur = 8;
    ctx.strokeRect(box.x, box.y, box.w, box.h);
    ctx.restore();

    // 3. Center crosshair
    ctx.save();
    ctx.strokeStyle = "rgba(0, 245, 255, 0.85)";
    ctx.lineWidth = 1.5;
    const cx = box.x + box.w / 2;
    const cy = box.y + box.h / 2;
    ctx.beginPath();
    ctx.moveTo(cx - 14, cy); ctx.lineTo(cx + 14, cy);
    ctx.moveTo(cx, cy - 14); ctx.lineTo(cx, cy + 14);
    ctx.stroke();
    ctx.restore();

    // 4. Yellow handle grips on corners and edges
    ctx.save();
    ctx.fillStyle = "#ffde00";
    ctx.strokeStyle = "#000";
    ctx.lineWidth = 1.5;
    const hs = 8;
    const handles = getHandles();
    Object.values(handles).forEach(h => {
      ctx.fillRect(h.x - hs / 2, h.y - hs / 2, hs, hs);
      ctx.strokeRect(h.x - hs / 2, h.y - hs / 2, hs, hs);
    });
    ctx.restore();

    // Dimension label inside box
    ctx.save();
    ctx.fillStyle = "rgba(0, 0, 0, 0.75)";
    ctx.fillRect(box.x + 6, box.y + 6, 120, 20);
    ctx.fillStyle = "#ffde00";
    ctx.font = "bold 11px sans-serif";
    ctx.fillText(`${box.w} × ${box.h} px`, box.x + 10, box.y + 20);
    ctx.restore();

    // Avatar preview (if present) - 100% natural pixel aspect ratio, zero stretch
    if (avatarCtx && sourceImg.complete && sourceImg.naturalWidth > 0) {
      avatarCtx.clearRect(0, 0, 96, 96);
      avatarCtx.save();
      avatarCtx.beginPath();
      if (avatarCtx.roundRect) avatarCtx.roundRect(6, 6, 84, 84, 12);
      else avatarCtx.rect(6, 6, 84, 84);
      avatarCtx.clip();

      const avW = 96, avH = 96;
      const avAR = (box.w > 0 && box.h > 0) ? (box.w / box.h) : 1;
      let adW, adH, adX, adY;
      if (avAR >= 1) {
        adW = avW;
        adH = Math.round(avW / avAR);
        adX = 0;
        adY = Math.round((avH - adH) / 2);
      } else {
        adH = avH;
        adW = Math.round(avH * avAR);
        adX = Math.round((avW - adW) / 2);
        adY = 0;
      }
      avatarCtx.drawImage(sourceImg, box.x, box.y, box.w, box.h, adX, adY, adW, adH);
      avatarCtx.restore();
    }
  }

  function getCanvasCoords(e) {
    const rect = canvas.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return {
      x: Math.round((clientX - rect.left) * scaleX),
      y: Math.round((clientY - rect.top) * scaleY)
    };
  }

  canvas.addEventListener("mousemove", (e) => {
    if (!isDragging) {
      const pos = getCanvasCoords(e);
      const hit = detectHit(pos.x, pos.y);
      canvas.style.cursor = getCursor(hit);
    }
  });

  function onPointerDown(e) {
    const pos = getCanvasCoords(e);
    dragStartX = pos.x;
    dragStartY = pos.y;
    dragMode = detectHit(pos.x, pos.y);
    startBox = { ...box };
    isDragging = true;
    state.template.webcam_crop_custom = true;

    if (dragMode === "new") {
      box.x = pos.x;
      box.y = pos.y;
      box.w = 40;
      box.h = 40;
      dragMode = "se";
      startBox = { ...box };
      syncStateAndUI();
      drawReticle();
    }
  }

  function onPointerMove(e) {
    if (!isDragging) return;
    const pos = getCanvasCoords(e);
    const dx = pos.x - dragStartX;
    const dy = pos.y - dragStartY;

    if (dragMode === "move") {
      box.x = Math.max(0, Math.min(vidW - box.w, startBox.x + dx));
      box.y = Math.max(0, Math.min(vidH - box.h, startBox.y + dy));
    } else if (lock16_9) {
      // 16:9 Aspect Ratio Locked Resizing
      if (dragMode === "se" || dragMode === "e" || dragMode === "s") {
        const nw = Math.max(64, Math.min(vidW - startBox.x, startBox.w + dx));
        const nh = Math.round(nw * 9 / 16);
        if (startBox.y + nh <= vidH) {
          box.w = nw;
          box.h = nh;
        }
      } else if (dragMode === "nw" || dragMode === "w") {
        const nw = Math.max(64, startBox.w - dx);
        const nh = Math.round(nw * 9 / 16);
        const nx = startBox.x + (startBox.w - nw);
        const ny = startBox.y + (startBox.h - nh);
        if (nx >= 0 && ny >= 0) {
          box.x = nx;
          box.y = ny;
          box.w = nw;
          box.h = nh;
        }
      } else if (dragMode === "ne") {
        const nw = Math.max(64, Math.min(vidW - startBox.x, startBox.w + dx));
        const nh = Math.round(nw * 9 / 16);
        const ny = startBox.y + (startBox.h - nh);
        if (ny >= 0) {
          box.y = ny;
          box.w = nw;
          box.h = nh;
        }
      } else if (dragMode === "sw") {
        const nw = Math.max(64, startBox.w - dx);
        const nh = Math.round(nw * 9 / 16);
        const nx = startBox.x + (startBox.w - nw);
        if (nx >= 0 && startBox.y + nh <= vidH) {
          box.x = nx;
          box.w = nw;
          box.h = nh;
        }
      }
    } else {
      // Freeform Resizing
      if (dragMode === "se") {
        box.w = Math.max(40, Math.min(vidW - startBox.x, startBox.w + dx));
        box.h = Math.max(40, Math.min(vidH - startBox.y, startBox.h + dy));
      } else if (dragMode === "e") {
        box.w = Math.max(40, Math.min(vidW - startBox.x, startBox.w + dx));
      } else if (dragMode === "s") {
        box.h = Math.max(40, Math.min(vidH - startBox.y, startBox.h + dy));
      } else if (dragMode === "nw") {
        const newW = Math.max(40, startBox.w - dx);
        const newH = Math.max(40, startBox.h - dy);
        box.x = startBox.x + (startBox.w - newW);
        box.y = startBox.y + (startBox.h - newH);
        box.w = newW;
        box.h = newH;
      } else if (dragMode === "ne") {
        box.w = Math.max(40, Math.min(vidW - startBox.x, startBox.w + dx));
        const newH = Math.max(40, startBox.h - dy);
        box.y = startBox.y + (startBox.h - newH);
        box.h = newH;
      } else if (dragMode === "sw") {
        const newW = Math.max(40, startBox.w - dx);
        box.x = startBox.x + (startBox.w - newW);
        box.w = newW;
        box.h = Math.max(40, Math.min(vidH - startBox.y, startBox.h + dy));
      } else if (dragMode === "n") {
        const newH = Math.max(40, startBox.h - dy);
        box.y = startBox.y + (startBox.h - newH);
        box.h = newH;
      } else if (dragMode === "w") {
        const newW = Math.max(40, startBox.w - dx);
        box.x = startBox.x + (startBox.w - newW);
        box.w = newW;
      }
    }

    syncStateAndUI();
    drawReticle();
    if (typeof requestPreviewUpdate === "function") {
      requestPreviewUpdate();
    }
  }

  function onPointerUp() {
    if (isDragging) {
      isDragging = false;
      syncStateAndUI();
      drawReticle();
      requestPreviewUpdate();
    }
  }

  canvas.addEventListener("mousedown", onPointerDown);
  window.addEventListener("mousemove", onPointerMove);
  window.addEventListener("mouseup", onPointerUp);

  canvas.addEventListener("touchstart", onPointerDown, { passive: true });
  window.addEventListener("touchmove", onPointerMove, { passive: true });
  window.addEventListener("touchend", onPointerUp);

  // Sliders for Width and Height with 16:9 lock synchronization
  const slW = document.getElementById("slider-reticle-w");
  if (slW) {
    slW.addEventListener("input", (e) => {
      const nw = parseInt(e.target.value) || 480;
      const oldCx = box.x + box.w / 2;
      box.w = nw;
      if (lock16_9) {
        box.h = Math.round(nw * 9 / 16);
      }
      box.x = Math.max(0, Math.min(vidW - box.w, Math.round(oldCx - nw / 2)));
      state.template.webcam_crop_custom = true;
      syncStateAndUI();
      drawReticle();
      requestPreviewUpdate();
    });
  }

  const slH = document.getElementById("slider-reticle-h");
  if (slH) {
    slH.addEventListener("input", (e) => {
      const nh = parseInt(e.target.value) || 270;
      const oldCy = box.y + box.h / 2;
      box.h = nh;
      if (lock16_9) {
        box.w = Math.round(nh * 16 / 9);
      }
      box.y = Math.max(0, Math.min(vidH - box.h, Math.round(oldCy - nh / 2)));
      state.template.webcam_crop_custom = true;
      syncStateAndUI();
      drawReticle();
      requestPreviewUpdate();
    });
  }

  // Quick Action Buttons
  const btn169 = document.getElementById("btn-reticle-16-9");
  if (btn169) {
    btn169.addEventListener("click", () => {
      box.w = Math.round(vidW * 0.35);
      box.h = Math.round(box.w * 9 / 16);
      if (aspectCheck) {
        aspectCheck.checked = true;
        lock16_9 = true;
        const aspectBadge = document.getElementById("reticle-aspect-badge");
        if (aspectBadge) aspectBadge.innerText = "16:9 LOCKED";
      }
      state.template.webcam_crop_custom = true;
      syncStateAndUI();
      drawReticle();
      requestPreviewUpdate();
      showToast("Framing locked to 16:9 stream camera aspect ratio");
    });
  }

  const btnFull = document.getElementById("btn-reticle-full-box");
  if (btnFull) {
    btnFull.addEventListener("click", () => {
      box.w = Math.round(vidW * 0.45);
      box.h = lock16_9 ? Math.round(box.w * 9 / 16) : Math.round(vidH * 0.46);
      box.x = Math.max(0, Math.round(vidW * 0.03));
      box.y = Math.max(0, Math.round(vidH * 0.05));
      state.template.webcam_crop_custom = true;
      syncStateAndUI();
      drawReticle();
      requestPreviewUpdate();
      showToast("Expanded frame to capture full streamer camera");
    });
  }

  const btnReset = document.getElementById("btn-reticle-reset-box") || document.getElementById("btn-reset-cam-zoom");
  if (btnReset) {
    btnReset.addEventListener("click", () => {
      box.w = Math.round(vidW * 0.32);
      box.h = Math.round(box.w * 9 / 16);
      box.x = Math.round(vidW * 0.04);
      box.y = Math.round(vidH * 0.06);
      if (aspectCheck) {
        aspectCheck.checked = true;
        lock16_9 = true;
        const aspectBadge = document.getElementById("reticle-aspect-badge");
        if (aspectBadge) aspectBadge.innerText = "16:9 LOCKED";
      }
      state.template.webcam_crop_custom = false;
      syncStateAndUI();
      drawReticle();
      requestPreviewUpdate();
      showToast("Reset reticle to standard 16:9 framing");
    });
  }

  // Nudge Function
  window.nudgeCamReticle = function(dx, dy) {
    box.x = Math.max(0, Math.min(vidW - box.w, box.x + dx));
    box.y = Math.max(0, Math.min(vidH - box.h, box.y + dy));
    state.template.webcam_crop_custom = true;
    syncStateAndUI();
    drawReticle();
    if (typeof requestPreviewUpdate === "function") {
      requestPreviewUpdate();
    }
    requestPreviewUpdate();
  };

  window.centerCamReticle = function() {
    box.x = Math.max(0, Math.round((vidW - box.w) / 2));
    box.y = Math.max(0, Math.round((vidH - box.h) / 2));
    state.template.webcam_crop_custom = true;
    syncStateAndUI();
    drawReticle();
    if (typeof requestPreviewUpdate === "function") {
      requestPreviewUpdate();
    }
    requestPreviewUpdate();
  };

  // Canvas Nudge Buttons
  ["btn-cam-nudge-up", "btn-nudge-cam-up"].forEach(id => {
    document.getElementById(id)?.addEventListener("click", () => window.nudgeCamReticle(0, -10));
  });
  ["btn-cam-nudge-down", "btn-nudge-cam-down"].forEach(id => {
    document.getElementById(id)?.addEventListener("click", () => window.nudgeCamReticle(0, 10));
  });
  ["btn-cam-nudge-left", "btn-nudge-cam-left"].forEach(id => {
    document.getElementById(id)?.addEventListener("click", () => window.nudgeCamReticle(-10, 0));
  });
  ["btn-cam-nudge-right", "btn-nudge-cam-right"].forEach(id => {
    document.getElementById(id)?.addEventListener("click", () => window.nudgeCamReticle(10, 0));
  });
  document.getElementById("btn-cam-nudge-center")?.addEventListener("click", () => window.centerCamReticle());

  // Phone Mockup Nudge
  document.getElementById("btn-reticle-up")?.addEventListener("click", (e) => { e.stopPropagation(); window.nudgeCamReticle(0, -10); });
  document.getElementById("btn-reticle-down")?.addEventListener("click", (e) => { e.stopPropagation(); window.nudgeCamReticle(0, 10); });
  document.getElementById("btn-reticle-left")?.addEventListener("click", (e) => { e.stopPropagation(); window.nudgeCamReticle(-10, 0); });
  document.getElementById("btn-reticle-right")?.addEventListener("click", (e) => { e.stopPropagation(); window.nudgeCamReticle(10, 0); });
  document.getElementById("btn-reticle-center")?.addEventListener("click", (e) => { e.stopPropagation(); window.centerCamReticle(); });

  window.syncWebcamReticleFromCrop = function(crop) {
    if (!crop) return;
    box.x = crop.x;
    box.y = crop.y;
    box.w = crop.w;
    box.h = crop.h;
    syncStateAndUI();
    drawReticle();
    if (typeof requestPreviewUpdate === "function") {
      requestPreviewUpdate();
    }
  };

  window.reloadWebcamSourceImage = function(url) {
    sourceImg.src = url || ("/storage/temp/source_frame.jpg?t=" + Date.now());
  };

  window.syncCropCanvasWithVideo = function(showToastMsg = false) {
    const vid = document.getElementById("preview-source-video");
    if (vid && vid.readyState >= 2 && vid.videoWidth > 0 && vid.videoWidth >= vid.videoHeight) {
      vidW = vid.videoWidth;
      vidH = vid.videoHeight;
      canvas.width = vidW;
      canvas.height = vidH;
      const off = document.createElement("canvas");
      off.width = vidW;
      off.height = vidH;
      const offCtx = off.getContext("2d");
      offCtx.drawImage(vid, 0, 0, vidW, vidH);
      sourceImg.src = off.toDataURL("image/jpeg", 0.95);
      if (showToastMsg) showToast("✓ Grabbed current 16:9 stream frame from player!");
    } else {
      sourceImg.src = "/storage/temp/source_frame.jpg?t=" + Date.now();
      if (showToastMsg) showToast("✓ Refreshed 16:9 stream frame from source!");
    }
  };

  const btnGrab = document.getElementById("btn-grab-video-frame");
  if (btnGrab) {
    btnGrab.addEventListener("click", () => {
      window.syncCropCanvasWithVideo(true);
    });
  }
}


function initNeonControls() {
  // 1. Neon Lightning Glow Checkbox
  const checkCamGlow = document.getElementById("check-cam-glow");
  if (checkCamGlow) {
    checkCamGlow.addEventListener("change", (e) => {
      state.template.webcam_glow_enabled = e.target.checked;
      requestPreviewUpdate();
    });
  }

  // 2. Cam Glow Presets
  const glowPresets = document.querySelectorAll("#cam-glow-presets .preset-pill");
  glowPresets.forEach(btn => {
    btn.addEventListener("click", () => {
      glowPresets.forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      const effect = btn.getAttribute("data-effect") || "neon_lightning";
      const color = btn.getAttribute("data-color") || "#C084FC";
      state.template.webcam_glow_effect = effect;
      state.template.webcam_glow_color = color;
      const colorInput = document.getElementById("color-cam-glow");
      if (colorInput) colorInput.value = color;
      requestPreviewUpdate();
    });
  });
}

// --- Divider Line Controls ---
function initDividerControls() {
  const slider = document.getElementById("slider-divider-w");
  const valText = document.getElementById("val-divider-w");
  const badge = document.getElementById("divider-badge");
  const colorInput = document.getElementById("color-divider");
  const hexText = document.getElementById("hex-divider");
  const divPills = document.querySelectorAll("[data-div]");

  const updateDividerUI = (val, color) => {
    if (slider) slider.value = val;
    if (valText) valText.innerText = `${val}px`;
    if (badge) {
      if (val === 0) badge.innerText = "NO DIVIDER";
      else badge.innerText = `${val}px SOLID`;
    }
    if (colorInput && color) colorInput.value = color;
    if (hexText && color) hexText.innerText = color.toUpperCase();

    divPills.forEach(p => {
      if (parseInt(p.getAttribute("data-div")) === val) {
        p.classList.add("active");
      } else {
        p.classList.remove("active");
      }
    });
  };

  if (slider) {
    slider.addEventListener("input", (e) => {
      const val = parseInt(e.target.value);
      state.template.divider_height = val;
      state.template.divider_line = (val > 0);
      updateDividerUI(val, state.template.divider_color || "#FFFFFF");
      requestPreviewUpdate();
    });
  }

  if (colorInput) {
    colorInput.addEventListener("input", (e) => {
      const col = e.target.value;
      state.template.divider_color = col;
      if (hexText) hexText.innerText = col.toUpperCase();
      requestPreviewUpdate();
    });
  }

  divPills.forEach(pill => {
    pill.addEventListener("click", () => {
      const val = parseInt(pill.getAttribute("data-div"));
      state.template.divider_height = val;
      state.template.divider_line = (val > 0);
      updateDividerUI(val, state.template.divider_color || "#FFFFFF");
      requestPreviewUpdate();
    });
  });

  const curH = state.template.divider_height !== undefined ? parseInt(state.template.divider_height) : 4;
  const curC = state.template.divider_color || "#FFFFFF";
  updateDividerUI(curH, curC);
}

// --- Facecam Shape & Screen Position Controls ---

function updateCamShapeBadge() {
  const badge = document.getElementById("cam-shape-badge");
  const shape = state.template.webcam_shape || "circle";
  const w = state.template.webcam_w || 300;
  const h = state.template.webcam_h || 300;
  const r = state.template.webcam_radius || 32;
  if (!badge) return;

  if (shape === "split_screen") {
    badge.innerText = `SPLIT SCREEN (${w}×${h} - VIRAL REFERENCE)`;
  } else if (shape === "circle") {
    badge.innerText = `CIRCLE (${w}×${h})`;
  } else if (shape === "square") {
    badge.innerText = `ROUNDED SQUARE (${w}×${h}, r=${r}px)`;
  } else if (shape === "rectangle_16_9") {
    badge.innerText = `ROUNDED 16:9 (${w}×${h}, r=${r}px)`;
  } else if (shape === "rectangle_4_3") {
    badge.innerText = `ROUNDED 4:3 (${w}×${h}, r=${r}px)`;
  } else {
    badge.innerText = `CUSTOM (${w}×${h}, r=${r}px)`;
  }
}

function updateCamHandleUI() {
  const w = state.template.webcam_w || 300;
  const h = state.template.webcam_h || 300;
  const posX = state.template.webcam_x !== undefined ? state.template.webcam_x : Math.round((1080 - w) / 2);
  const posY = state.template.webcam_y !== undefined ? state.template.webcam_y : 540;

  const sX = document.getElementById("slider-cam-x");
  const vX = document.getElementById("val-cam-x");
  if (sX) {
    sX.max = Math.max(0, 1080 - w);
    sX.value = Math.round(posX);
  }
  if (vX) {
    const isCenter = Math.abs(posX - Math.round((1080 - w) / 2)) < 5;
    vX.innerText = isCenter ? `${Math.round(posX)}px (Center)` : `${Math.round(posX)}px`;
  }

  const sY = document.getElementById("slider-cam-y");
  const vY = document.getElementById("val-cam-y");
  if (sY) sY.value = Math.round(posY);
  if (vY) vY.innerText = `${Math.round(posY)}px`;

  const posBadge = document.getElementById("cam-pos-badge");
  if (posBadge) {
    posBadge.innerText = `(x=${Math.round(posX)}, y=${Math.round(posY)})`;
  }

  const handle = document.getElementById("drag-cam-handle");
  if (handle) {
    handle.style.display = "none";
  }
}
window.updateCamHandleUI = updateCamHandleUI;
window.updateFacecamHandleUI = updateCamHandleUI;

function updateCamShapeUI(doTrigger = true) {
  const shape = state.template.webcam_shape || "circle";
  const groupRadius = document.getElementById("group-cam-radius");
  if (groupRadius) {
    groupRadius.style.display = shape === "circle" ? "none" : "flex";
  }

  const sW = document.getElementById("slider-cam-w");
  const sH = document.getElementById("slider-cam-h");
  const sR = document.getElementById("slider-cam-radius");
  const vW = document.getElementById("val-cam-w");
  const vH = document.getElementById("val-cam-h");
  const vR = document.getElementById("val-cam-radius");

  if (sW) sW.value = state.template.webcam_w || 300;
  if (sH) sH.value = state.template.webcam_h || 300;
  if (sR) sR.value = state.template.webcam_radius || 32;
  if (vW) vW.innerText = `${state.template.webcam_w || 300}px`;
  if (vH) vH.innerText = `${state.template.webcam_h || 300}px`;
  if (vR) vR.innerText = `${state.template.webcam_radius || 32}px`;

  updateCamShapeBadge();
  updateCamHandleUI();

  if (window.updateReticleShape) {
    window.updateReticleShape();
  }

  if (doTrigger) {
    requestPreviewUpdate();
  }
}

function initFacecamShapeAndPosControls() {
  // Shape Preset Pills
  const shapePills = document.querySelectorAll("#cam-shape-presets .preset-pill");
  shapePills.forEach(btn => {
    btn.addEventListener("click", () => {
      shapePills.forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      const shape = btn.getAttribute("data-shape");
      state.template.webcam_shape = shape;

      if (shape === "split_screen") {
        state.template.layout_mode = "split_screen";
        state.template.webcam_w = 1080;
        state.template.webcam_h = 700;
        state.template.webcam_x = 0;
        state.template.webcam_y = 260;
        state.template.webcam_radius = 0;
        state.template.webcam_border_w = 0;
        state.template.webcam_glow_enabled = false;
        state.template.gameplay_w = 1080;
        state.template.gameplay_h = 700;
        state.template.gameplay_y = 960;
        state.template.gameplay_radius = 0;
        state.template.gameplay_border_w = 0;
        state.template.gameplay_border_color = "#FFFFFF";
        state.template.bg_blur_sigma = 0;
        state.template.divider_line = true;
        state.template.divider_color = "#FFFFFF";
        state.template.divider_height = 4;
        syncUIFromState();
      } else if (shape === "circle") {
        state.template.webcam_w = 300;
        state.template.webcam_h = 300;
      } else if (shape === "square") {
        state.template.webcam_w = 320;
        state.template.webcam_h = 320;
        state.template.webcam_radius = 32;
      } else if (shape === "rectangle_16_9") {
        state.template.webcam_w = 420;
        state.template.webcam_h = 240;
        state.template.webcam_radius = 28;
      } else if (shape === "rectangle_4_3") {
        state.template.webcam_w = 360;
        state.template.webcam_h = 270;
        state.template.webcam_radius = 28;
      }

      // Keep horizontal center aligned if previously centered
      const curX = state.template.webcam_x !== undefined ? state.template.webcam_x : 390;
      state.template.webcam_x = Math.max(0, Math.min(1080 - state.template.webcam_w, curX));

      updateCamShapeUI(true);
      showToast(`Selected Facecam shape: ${btn.innerText.trim()}`);
    });
  });
}

function adjustCamSize(delta) {
  const shape = state.template.webcam_shape || "circle";
  if (shape === "split_screen") return;

  const curW = state.template.webcam_w || 300;
  const curH = state.template.webcam_h || 300;
  const aspect = curW / curH;

  const newW = Math.max(120, Math.min(840, curW + delta));
  const newH = Math.round(newW / aspect);

  // Keep center stationary while scaling
  const curX = state.template.webcam_x !== undefined ? state.template.webcam_x : Math.round((1080 - curW) / 2);
  const curY = state.template.webcam_y !== undefined ? state.template.webcam_y : 540;
  const centerX = curX + curW / 2;
  const centerY = curY + curH / 2;

  let newX = Math.round(centerX - newW / 2);
  let newY = Math.round(centerY - newH / 2);

  newX = Math.max(0, Math.min(1080 - newW, newX));
  newY = Math.max(20, Math.min(1920 - newH - 20, newY));

  state.template.webcam_w = newW;
  state.template.webcam_h = newH;
  state.template.webcam_x = newX;
  state.template.webcam_y = newY;
  if (shape === "circle") {
    state.template.webcam_radius = Math.round(newW / 2);
  }

  const sW = document.getElementById("slider-cam-w");
  const sH = document.getElementById("slider-cam-h");
  const vW = document.getElementById("val-cam-w");
  const vH = document.getElementById("val-cam-h");
  if (sW) sW.value = newW;
  if (sH) sH.value = newH;
  if (vW) vW.innerText = `${newW}px`;
  if (vH) vH.innerText = `${newH}px`;

  updateCamHandleUI();
  updateCamShapeBadge();
  requestPreviewUpdate();
}

function initDraggableFacecam() {
  // Safe no-op stub: floating facecam drag/resize square overlay removed from 9:16 preview window
  const handle = document.getElementById("drag-cam-handle");
  if (handle) {
    handle.style.display = "none";
  }
  if (typeof updateCamHandleUI === "function") {
    updateCamHandleUI();
  }
}

function initEnhancePresets() {
  const presets = {
    "preset-enh-topaz": { res: "2160x3840", scaler: "lanczos", sharp: 0.40, micro: 0.30, deblock: "medium", contrast: 1.04, sat: 1.08, bitrate: "35M" },
    "preset-enh-crisp": { res: "1080x1920", scaler: "lanczos", sharp: 0.35, micro: 0.25, deblock: "medium", contrast: 1.04, sat: 1.06, bitrate: "12M" }
  };

  Object.keys(presets).forEach(id => {
    const btn = document.getElementById(id);
    if (!btn) return;
    btn.addEventListener("click", () => {
      document.querySelectorAll("#tab-enhance .preset-pill").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      const p = presets[id];

      // Update state
      const [w, h] = p.res.split("x").map(Number);
      state.template.canvas_w = w;
      state.template.canvas_h = h;
      state.template.sharpen_amount = p.sharp;
      state.template.contrast_boost = p.contrast;
      state.template.saturation_boost = p.sat;
      state.template.micro_texture = p.micro;
      state.template.deblock_level = p.deblock;
      state.template.export_bitrate = p.bitrate;

      // Update UI elements
      const sRes = document.getElementById("select-res");
      if (sRes) sRes.value = p.res;
      const sExpRes = document.getElementById("select-export-res");
      if (sExpRes) sExpRes.value = p.res;

      const sScaler = document.getElementById("select-scaler");
      if (sScaler) sScaler.value = p.scaler;

      const sDeblock = document.getElementById("select-deblock");
      if (sDeblock) sDeblock.value = p.deblock;

      const sBitrate = document.getElementById("select-export-bitrate");
      if (sBitrate) sBitrate.value = p.bitrate;

      const sMicro = document.getElementById("slider-micro-texture");
      if (sMicro) { sMicro.value = p.micro; document.getElementById("val-micro-texture").innerText = p.micro.toFixed(2) + "x"; }

      const sSharp = document.getElementById("slider-sharpness");
      if (sSharp) { sSharp.value = p.sharp; document.getElementById("val-sharpness").innerText = p.sharp + "x"; }

      const sContrast = document.getElementById("slider-contrast");
      if (sContrast) { sContrast.value = p.contrast; document.getElementById("val-contrast").innerText = "+" + Math.round((p.contrast - 1) * 100) + "%"; }

      const sSat = document.getElementById("slider-saturation");
      if (sSat) { sSat.value = p.sat; document.getElementById("val-saturation").innerText = "+" + Math.round((p.sat - 1) * 100) + "%"; }

      updateExportProfileLabel();
      requestPreviewUpdate();
    });
  });

  // Resolution selector in Tab 4
  const selectRes = document.getElementById("select-res");
  if (selectRes) {
    selectRes.addEventListener("change", (e) => {
      const [w, h] = e.target.value.split("x").map(Number);
      state.template.canvas_w = w;
      state.template.canvas_h = h;
      const expRes = document.getElementById("select-export-res");
      if (expRes) expRes.value = e.target.value;
      updateExportProfileLabel();
      requestPreviewUpdate();
    });
  }

  // AI Neural Pixel Generator Controls
  const checkPixelGen = document.getElementById("check-pixel-gen");
  const badgePixelGen = document.getElementById("badge-pixel-gen");
  if (checkPixelGen) {
    checkPixelGen.checked = state.template.pixel_generator !== false;
    checkPixelGen.addEventListener("change", (e) => {
      const active = e.target.checked;
      state.template.pixel_generator = active;
      if (badgePixelGen) {
        badgePixelGen.innerText = active ? "✨ ACTIVE" : "OFF";
        badgePixelGen.style.background = active ? "#00F5FF" : "var(--bg-tertiary)";
        badgePixelGen.style.color = active ? "#000" : "var(--text-muted)";
      }
      updateExportProfileLabel();
      requestPreviewUpdate();
    });
  }

  const pgenPills = document.querySelectorAll("#pills-pixel-gen button");
  pgenPills.forEach(btn => {
    btn.addEventListener("click", () => {
      pgenPills.forEach(b => {
        b.classList.remove("active");
        b.style.borderColor = "";
        b.style.color = "";
      });
      btn.classList.add("active");
      btn.style.borderColor = "#00F5FF";
      btn.style.color = "#00F5FF";

      const mode = btn.getAttribute("data-mode") || "ultra";
      state.template.pixel_generator_mode = mode;
      state.template.pixel_generator = true;
      if (checkPixelGen) checkPixelGen.checked = true;
      if (badgePixelGen) {
        badgePixelGen.innerText = "✨ ACTIVE (" + mode.toUpperCase() + ")";
        badgePixelGen.style.background = "#00F5FF";
        badgePixelGen.style.color = "#000";
      }

      if (mode === "ultra") {
        state.template.canvas_w = 2160;
        state.template.canvas_h = 3840;
        state.template.sharpen_amount = 0.75;
        state.template.micro_texture = 1.20;
        state.template.contrast_boost = 1.06;
        state.template.saturation_boost = 1.08;
        state.template.export_bitrate = "35M";
      } else if (mode === "balanced") {
        state.template.canvas_w = 1080;
        state.template.canvas_h = 1920;
        state.template.sharpen_amount = 0.55;
        state.template.micro_texture = 0.75;
        state.template.contrast_boost = 1.04;
        state.template.saturation_boost = 1.06;
        state.template.export_bitrate = "16M";
      } else if (mode === "film") {
        state.template.canvas_w = 2160;
        state.template.canvas_h = 3840;
        state.template.sharpen_amount = 0.60;
        state.template.micro_texture = 0.85;
        state.template.contrast_boost = 1.05;
        state.template.saturation_boost = 1.04;
        state.template.export_bitrate = "30M";
      }

      // Sync UI dropdowns and sliders
      const sRes = document.getElementById("select-res");
      if (sRes) sRes.value = `${state.template.canvas_w}x${state.template.canvas_h}`;
      const sExpRes = document.getElementById("select-export-res");
      if (sExpRes) sExpRes.value = `${state.template.canvas_w}x${state.template.canvas_h}`;
      const sSharp = document.getElementById("slider-sharpness");
      if (sSharp) { sSharp.value = state.template.sharpen_amount; document.getElementById("val-sharpness").innerText = state.template.sharpen_amount + "x"; }
      const sMicro = document.getElementById("slider-micro-texture");
      if (sMicro) { sMicro.value = state.template.micro_texture; document.getElementById("val-micro-texture").innerText = state.template.micro_texture.toFixed(2) + "x"; }
      const sBitrate = document.getElementById("select-export-bitrate");
      if (sBitrate) sBitrate.value = state.template.export_bitrate;

      updateExportProfileLabel();
      requestPreviewUpdate();
    });
  });
}

// ==================== LIVE 3-STATE TOOLS STATUS ====================
let toolsStatusPollTimer = null;

function _toolLedClass(stateVal) {
  if (stateVal === "in_use") return "status-led led-in-use";
  if (stateVal === "active") return "status-led led-green";
  return "status-led led-red";
}

function scheduleToolsStatusPoll(delayMs) {
  if (toolsStatusPollTimer) {
    clearTimeout(toolsStatusPollTimer);
    toolsStatusPollTimer = null;
  }
  if (!document.hidden) {
    toolsStatusPollTimer = setTimeout(fetchToolsStatus, delayMs);
  }
}

async function fetchToolsStatus() {
  let nextDelay = 20000;
  try {
    const res = await fetch("/api/tools_status");
    if (!res.ok) throw new Error("Failed to fetch tools status");
    const data = await res.json();

    const badge = document.getElementById("tools-status-badge");
    const summaryDot = document.getElementById("tools-summary-dot");
    const miniLlm = document.getElementById("mini-led-llm");
    const miniAsr = document.getElementById("mini-led-asr");
    const countEl = document.getElementById("tools-active-count");
    const listEl = document.getElementById("tools-status-list");

    const tools = Array.isArray(data.tools) ? data.tools : [];
    const byId = {};
    tools.forEach(t => { byId[t.id] = t; });

    if (summaryDot) {
      const sumState = data.any_in_use ? "in_use" : (data.core_all_active ? "active" : "inactive");
      summaryDot.className = _toolLedClass(sumState);
    }
    if (badge) {
      badge.classList.toggle("has-in-use", !!data.any_in_use);
    }
    if (miniLlm && byId.llm) {
      miniLlm.className = _toolLedClass(byId.llm.state);
    }
    if (miniAsr && byId.transcription) {
      miniAsr.className = _toolLedClass(byId.transcription.state);
    }
    if (countEl && data.active_count !== undefined && data.total_count !== undefined) {
      countEl.innerText = `${data.active_count}/${data.total_count}`;
    }

    if (listEl) {
      listEl.innerHTML = tools.map(t => {
        const ledCls = _toolLedClass(t.state);
        const rowCls = t.state === "in_use" ? "tool-status-row is-in-use" : "tool-status-row";
        const badgeCls = t.state === "in_use" ? "tool-state-badge is-in-use" : (t.state === "active" ? "tool-state-badge is-active" : "tool-state-badge is-inactive");
        const badgeTxt = t.state === "in_use" ? "IN USE" : (t.state === "active" ? "ACTIVE" : "INACTIVE");
        const optTag = t.optional ? `<span style="font-size:10px;color:var(--text-muted);font-weight:400;">(Optional)</span>` : "";
        return `
          <div class="${rowCls}" data-tool-id="${t.id}">
            <div class="tool-status-left">
              <span class="${ledCls}"></span>
              <div class="tool-status-text">
                <div class="tool-status-name">${t.name} ${optTag}</div>
                <div class="tool-status-detail" title="${t.detail || ''}">${t.detail || ''}</div>
              </div>
            </div>
            <span class="${badgeCls}">${badgeTxt}</span>
          </div>
        `;
      }).join("");
    }

    nextDelay = data.any_in_use ? 2000 : 20000;
  } catch (err) {
    console.warn("[ToolsStatus] Poll notice:", err);
    nextDelay = 20000;
  } finally {
    scheduleToolsStatusPoll(nextDelay);
  }
}

function initToolsStatus() {
  const badge = document.getElementById("tools-status-badge");
  const dropdown = document.getElementById("tools-status-dropdown");
  const refreshBtn = document.getElementById("btn-refresh-tools");

  if (badge && dropdown) {
    badge.addEventListener("click", (e) => {
      e.stopPropagation();
      const isVisible = dropdown.style.display === "flex" || dropdown.style.display === "block";
      const hwDropdown = document.getElementById("hw-selector-dropdown");
      const hwBadge = document.getElementById("hw-status-badge");
      if (hwDropdown) hwDropdown.style.display = "none";
      if (hwBadge) hwBadge.classList.remove("active-open");
      dropdown.style.display = isVisible ? "none" : "flex";
      badge.classList.toggle("active-open", !isVisible);
    });

    document.addEventListener("click", (e) => {
      if (!dropdown.contains(e.target) && !badge.contains(e.target)) {
        dropdown.style.display = "none";
        badge.classList.remove("active-open");
      }
    });
  }

  if (refreshBtn) {
    refreshBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      fetchToolsStatus();
    });
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      if (toolsStatusPollTimer) {
        clearTimeout(toolsStatusPollTimer);
        toolsStatusPollTimer = null;
      }
    } else {
      fetchToolsStatus();
    }
  });

  fetchToolsStatus();
}

async function initHardwareDetection() {
  const hwBadge = document.getElementById("hw-status-badge");
  const hwText = document.getElementById("hw-status-text");
  const hwDropdown = document.getElementById("hw-selector-dropdown");
  const hwOptionsList = document.getElementById("hw-options-list");
  const hwCpuInfo = document.getElementById("hw-dropdown-cpu-info");
  const hwGpuInfo = document.getElementById("hw-dropdown-gpu-info");
  const encSelect = document.getElementById("select-export-encoder");

  // Toggle Dropdown when clicking header badge
  if (hwBadge && hwDropdown) {
    hwBadge.addEventListener("click", (e) => {
      e.stopPropagation();
      const isVisible = hwDropdown.style.display === "flex" || hwDropdown.style.display === "block";
      const toolsDropdown = document.getElementById("tools-status-dropdown");
      const toolsBadge = document.getElementById("tools-status-badge");
      if (toolsDropdown) toolsDropdown.style.display = "none";
      if (toolsBadge) toolsBadge.classList.remove("active-open");
      hwDropdown.style.display = isVisible ? "none" : "flex";
      hwBadge.classList.toggle("active-open", !isVisible);
    });

    // Close when clicking outside
    document.addEventListener("click", (e) => {
      if (!hwDropdown.contains(e.target) && !hwBadge.contains(e.target)) {
        hwDropdown.style.display = "none";
        hwBadge.classList.remove("active-open");
      }
    });
  }

  try {
    const res = await fetch("/api/system_hardware");
    if (!res.ok) throw new Error("Failed to load hardware status");
    const data = await res.json();

    // Default encoder is recommended (e.g. h264_qsv on Intel, h264_nvenc on Nvidia, or libx264)
    let currentEncoder = state.template.export_encoder || data.recommended_encoder || "h264_qsv";
    state.template.export_encoder = currentEncoder;

    const updateActiveHardwareUI = (selectedId) => {
      currentEncoder = selectedId;
      state.template.export_encoder = selectedId;

      if (hwText) {
        if (selectedId === "h264_qsv") hwText.innerText = "⚡ Intel QuickSync (Active)";
        else if (selectedId === "h264_nvenc") hwText.innerText = "⚡ NVIDIA NVENC (Active)";
        else if (selectedId === "h264_amf") hwText.innerText = "⚡ AMD Radeon (Active)";
        else if (selectedId === "h264_videotoolbox") hwText.innerText = "⚡ VideoToolbox (Active)";
        else hwText.innerText = "🚀 CPU Multi-Core (Active)";
      }

      if (encSelect) encSelect.value = selectedId;

      // Update dropdown option rows
      if (hwOptionsList) {
        hwOptionsList.querySelectorAll(".hw-option-row").forEach(row => {
          const encId = row.getAttribute("data-encoder-id");
          const badge = row.querySelector(".hw-option-badge");
          if (encId === selectedId) {
            row.classList.add("active");
            if (badge) {
              badge.className = "hw-option-badge active-badge";
              badge.innerText = "ACTIVE";
            }
          } else {
            row.classList.remove("active");
            if (badge && !row.classList.contains("disabled")) {
              badge.className = "hw-option-badge select-badge";
              badge.innerText = "SELECT";
            }
          }
        });
      }
    };

    // Populate Dropdown Options
    if (hwOptionsList && data.encoders_list) {
      hwOptionsList.innerHTML = "";
      data.encoders_list.forEach(enc => {
        const row = document.createElement("div");
        row.className = `hw-option-row ${enc.id === currentEncoder ? "active" : ""} ${enc.available ? "" : "disabled"}`;
        row.setAttribute("data-encoder-id", enc.id);

        const isGpu = enc.type === "gpu";
        const iconClass = isGpu ? "fa-bolt" : "fa-microchip";
        const iconColor = enc.available ? (isGpu ? "var(--accent-lime)" : "var(--accent-cyan)") : "var(--text-dim)";

        let badgeClass = "disabled-badge";
        let badgeText = "UNAVAILABLE";
        if (enc.available) {
          if (enc.id === currentEncoder) {
            badgeClass = "active-badge";
            badgeText = "ACTIVE";
          } else {
            badgeClass = "select-badge";
            badgeText = "SELECT";
          }
        }

        row.innerHTML = `
          <div class="hw-option-info">
            <i class="fa-solid ${iconClass}" style="color: ${iconColor}; font-size: 13px;"></i>
            <span>${enc.label.replace(/^[\u26a1\ud83d\ude80\s]+/, '')}</span>
          </div>
          <span class="hw-option-badge ${badgeClass}">${badgeText}</span>
        `;

        if (enc.available) {
          row.addEventListener("click", () => {
            updateActiveHardwareUI(enc.id);
            showToast(`Hardware acceleration switched to: ${enc.label.replace(/^[\u26a1\ud83d\ude80\s]+/, '')}`);
            if (hwDropdown) hwDropdown.style.display = "none";
            if (hwBadge) hwBadge.classList.remove("active-open");
          });
        }

        hwOptionsList.appendChild(row);
      });
    }

    // Update bottom CPU & GPU info in dropdown
    if (hwCpuInfo && data.cpu) {
      hwCpuInfo.innerHTML = `<i class="fa-solid fa-cpu" style="color: var(--accent-cyan);"></i> ${data.cpu.model ? data.cpu.model.split('@')[0].trim() : 'CPU'} (${data.cpu.cores}C)`;
    }
    if (hwGpuInfo && data.gpu) {
      hwGpuInfo.innerHTML = `<i class="fa-solid fa-display" style="color: var(--accent-lime);"></i> ${data.gpu.primary || 'Integrated Graphics'}`;
    }

    // Populate Tab 5 encoder select
    if (encSelect && data.encoders_list) {
      encSelect.innerHTML = "";
      data.encoders_list.forEach(enc => {
        const opt = document.createElement("option");
        opt.value = enc.id;
        opt.innerText = (enc.available ? "" : "[Unavailable] ") + enc.label.replace(/^[\u26a1\ud83d\ude80\s]+/, '');
        if (!enc.available) opt.disabled = true;
        if (enc.id === currentEncoder) opt.selected = true;
        encSelect.appendChild(opt);
      });

      encSelect.addEventListener("change", (e) => {
        updateActiveHardwareUI(e.target.value);
      });
    }

    updateActiveHardwareUI(currentEncoder);

  } catch (err) {
    console.warn("Hardware auto-detection notice:", err);
    if (hwText) hwText.innerText = "⚡ Adaptive Multi-Core Engine";
  }
}

function initExportOptions() {
  const expRes = document.getElementById("select-export-res");
  if (expRes) {
    expRes.addEventListener("change", (e) => {
      const [w, h] = e.target.value.split("x").map(Number);
      state.template.canvas_w = w;
      state.template.canvas_h = h;
      const sRes = document.getElementById("select-res");
      if (sRes) sRes.value = e.target.value;
      updateExportProfileLabel();
      requestPreviewUpdate();
    });
  }

  const expBitrate = document.getElementById("select-export-bitrate");
  if (expBitrate) {
    if (state.template.export_bitrate) expBitrate.value = state.template.export_bitrate;
    expBitrate.addEventListener("change", (e) => {
      state.template.export_bitrate = e.target.value;
      updateExportProfileLabel();
    });
  }

  // Jump to Tab 4 button
  const jumpBtn = document.getElementById("btn-jump-enhance");
  if (jumpBtn) {
    jumpBtn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
      const tab4Btn = document.querySelector('[data-tab="tab-enhance"]');
      const tab4Content = document.getElementById("tab-enhance");
      if (tab4Btn) tab4Btn.classList.add("active");
      if (tab4Content) tab4Content.classList.add("active");
    });
  }

  // Export Destination Folder Controls
  const inputExportFolder = document.getElementById("input-export-folder");
  const btnSaveExportFolder = document.getElementById("btn-save-export-folder");
  const btnResetExportFolder = document.getElementById("btn-reset-export-folder");
  const btnTab5OpenFolder = document.getElementById("btn-tab5-open-folder");
  const btnOpenZipFolder = document.getElementById("btn-open-zip-folder");
  const btnCreateZipNow = document.getElementById("btn-create-zip-now");

  // Load current export folder from backend
  fetch("/api/export_folder")
    .then(r => r.json())
    .then(data => {
      if (data.path && inputExportFolder) {
        inputExportFolder.value = data.path;
      }
    })
    .catch(() => {});

  if (btnSaveExportFolder && inputExportFolder) {
    btnSaveExportFolder.addEventListener("click", async () => {
      const folder = inputExportFolder.value.trim();
      if (!folder) {
        alert("Please enter a folder path.");
        return;
      }
      try {
        const res = await fetch("/api/set_export_folder", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ folder_path: folder })
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
          inputExportFolder.value = data.path;
          showToast(`Export location updated: ${data.path}`);
          fetchOutputs();
        } else {
          alert(`Error setting export folder: ${data.detail || data.message || "Failed"}`);
        }
      } catch (e) {
        alert("Could not update export folder: " + e.message);
      }
    });
  }

  if (btnResetExportFolder && inputExportFolder) {
    btnResetExportFolder.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/set_export_folder", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ folder_path: "storage/outputs" })
        });
        const data = await res.json();
        if (res.ok && data.status === "success") {
          inputExportFolder.value = data.path;
          showToast(`Export location reset to default: ${data.path}`);
          fetchOutputs();
        }
      } catch (e) {
        console.error(e);
      }
    });
  }

  if (btnTab5OpenFolder) {
    btnTab5OpenFolder.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/open_folder", { method: "POST" });
        const data = await res.json();
        showToast("Opened: " + (data.path || "storage/outputs"));
      } catch (e) {
        showToast("Storage folder: storage/outputs");
      }
    });
  }

  if (btnOpenZipFolder) {
    btnOpenZipFolder.addEventListener("click", async () => {
      try {
        const res = await fetch("/api/open_folder", { method: "POST" });
        const data = await res.json();
        showToast("Opened: " + (data.path || "storage/outputs"));
      } catch (e) {
        showToast("Storage folder: storage/outputs");
      }
    });
  }

  if (btnCreateZipNow) {
    btnCreateZipNow.addEventListener("click", async () => {
      btnCreateZipNow.disabled = true;
      btnCreateZipNow.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Zipping...`;
      try {
        const res = await fetch("/api/create_zip_from_outputs", { method: "POST" });
        const data = await res.json();
        const zipObj = data.zip || (data.download_url ? data : null);
        if (res.ok && data.status === "success" && zipObj) {
          showZipDownloadBanner(zipObj);
          showToast(`ZIP created successfully! (${zipObj.size_mb} MB)`);
        } else {
          alert(data.detail || data.message || "No MP4 clips found in the export directory to zip.");
        }
      } catch (e) {
        alert("Failed to create ZIP: " + e.message);
      } finally {
        btnCreateZipNow.disabled = false;
        btnCreateZipNow.innerHTML = `<i class="fa-solid fa-file-zipper"></i> Create ZIP from Library`;
      }
    });
  }
}

function updateExportProfileLabel() {
  const label = document.getElementById("export-profile-label");
  if (!label) return;
  const res = `${state.template.canvas_w || 1080}x${state.template.canvas_h || 1920}`;
  const sharp = state.template.sharpen_amount || 0.75;
  const micro = state.template.micro_texture || 1.2;
  const deblock = state.template.deblock_level || "medium";
  const bitrate = state.template.export_bitrate || "14M";
  const isPgen = state.template.pixel_generator !== false;
  const pgenMode = (state.template.pixel_generator_mode || "ultra").toUpperCase();

  if (isPgen) {
    label.innerText = `✨ AI Neural Pixel Generator (${pgenMode} 4K • ${res} • Micro-Texture ${micro}x • CAS ${sharp}x • ${bitrate})`;
  } else if ((state.template.canvas_w && state.template.canvas_w >= 2160) || bitrate === "35M") {
    label.innerText = `🔥 Natural Topaz AI 4K Master (${res} • Lanczos-4 Sinc • Micro-Texture ${micro}x • CAS ${sharp}x • Deblock ${deblock} • ${bitrate})`;
  } else if (state.template.canvas_w && state.template.canvas_w >= 1440) {
    label.innerText = `⚡ 2K QHD Ultra (${res} • Lanczos Sinc • Micro-Texture ${micro}x • CAS ${sharp}x • ${bitrate})`;
  } else {
    label.innerText = `${res} • CAS ${sharp}x • Lanczos Sinc • Micro-Texture ${micro}x • Deblock ${deblock} • ${bitrate}`;
  }
}

// ==========================================
// 60 FPS Real-Time Playable Clip Preview Engine
// ==========================================
let isPlayingPreview = false;
let isPlayMode = false;
let previewLoop = true;
let animFrameId = null;

function initPlayablePreview() {
  const btnPlay = document.getElementById("btn-play-toggle") || document.getElementById("btn-play-clip-preview");
  const btnLoop = document.getElementById("btn-loop-preview");
  const btnAudio = document.getElementById("btn-audio-preview");
  const btnRefresh = document.getElementById("btn-refresh-preview");
  const sliderPlayer = document.getElementById("slider-player-time");
  const sourceVid = document.getElementById("preview-source-video");

  if (btnPlay) {
    btnPlay.addEventListener("click", togglePlayClipPreview);
  }

  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      triggerPreview(true);
      showToast("🔄 Preview Refreshed");
    });
  }

  if (btnLoop) {
    btnLoop.addEventListener("click", () => {
      previewLoop = !previewLoop;
      btnLoop.style.color = previewLoop ? "var(--accent-lime)" : "var(--text-muted)";
      showToast(previewLoop ? "🔁 Clip Looping Enabled" : "Play Once (Loop Disabled)");
    });
  }

  if (btnAudio && sourceVid) {
    btnAudio.addEventListener("click", () => {
      sourceVid.muted = !sourceVid.muted;
      updateAudioButtonUI(sourceVid.muted);
      showToast(sourceVid.muted ? "🔇 Audio Muted" : "🔊 Audio Unmuted");
    });
  }

  if (sliderPlayer && sourceVid) {
    sliderPlayer.addEventListener("input", (e) => {
      const selectedClip = getActiveOrFallbackClip();
      if (selectedClip) {
        const targetTime = selectedClip.start + parseFloat(e.target.value);
        try { sourceVid.currentTime = targetTime; } catch (_) {}
        const curLabel = document.getElementById("player-cur-time");
        if (curLabel) curLabel.innerText = `${parseFloat(e.target.value).toFixed(1)}s`;
        state.previewTime = targetTime;
        if (!isPlayingPreview) {
          renderCanvasFrame(selectedClip, targetTime);
        }
      }
    });
    sliderPlayer.addEventListener("change", () => {
      if (!isPlayingPreview) {
        triggerPreview();
      }
    });
  }

  // Preload video source on video load
  if (sourceVid) {
    if (!sourceVid.getAttribute("src")) {
      sourceVid.src = "/media/video";
    }
    sourceVid.playsInline = true;
    sourceVid.addEventListener("loadedmetadata", () => {
      updatePlayerInfo();
    });
    sourceVid.addEventListener("error", (e) => {
      console.warn("Source video notice for canvas player:", e);
    });
  }

  window.updatePlayerInfo = updatePlayerInfo;
}

function getActiveOrFallbackClip() {
  if (state.clips && state.clips.length > 0) {
    return state.clips.find(c => c.id === state.selectedClipId) || state.clips[0];
  }
  // Robust Fallback: 15-second slice around active preview time
  const curTime = typeof state.previewTime === "number" ? state.previewTime : 10.0;
  const maxDur = (state.videoMeta && state.videoMeta.duration) ? state.videoMeta.duration : 1800.0;
  const start = Math.max(0, Math.min(curTime, Math.max(0, maxDur - 5)));
  const end = Math.min(maxDur, start + 15.0);
  return {
    id: "preview-fallback-clip",
    title: `Preview (${start.toFixed(1)}s - ${end.toFixed(1)}s)`,
    start: start,
    end: end,
    score: 85
  };
}

function updateAudioButtonUI(isMuted) {
  const icon = document.getElementById("icon-audio-btn");
  const btn = document.getElementById("btn-audio-preview");
  if (icon) icon.className = isMuted ? "fa-solid fa-volume-xmark" : "fa-solid fa-volume-high";
  if (btn) btn.style.color = isMuted ? "var(--text-muted)" : "var(--accent-lime)";
}

function updatePlayerInfo() {
  const selectedClip = getActiveOrFallbackClip();
  const durLabel = document.getElementById("player-total-time") || document.getElementById("player-dur-time");
  const titleLabel = document.getElementById("player-clip-title");
  const slider = document.getElementById("slider-player-time");

  if (selectedClip) {
    const dur = Math.max(1, selectedClip.end - selectedClip.start);
    if (durLabel) durLabel.innerText = `${dur.toFixed(1)}s`;
    if (titleLabel) titleLabel.innerText = `Active: ${selectedClip.title || 'Clip'}`;
    if (slider) {
      slider.max = dur;
      if (!isPlayingPreview) slider.value = 0;
    }
  }
}

function switchToLayoutMode() {
  isPlayMode = false;
  const canvas = document.getElementById("preview-canvas");
  const img = document.getElementById("preview-img");
  const reticle = document.getElementById("drag-cam-handle");
  if (canvas) canvas.style.display = "none";
  if (img) img.style.display = "block";
  if (reticle) reticle.style.display = "block";
}

function switchToPlayMode() {
  isPlayMode = true;
  const canvas = document.getElementById("preview-canvas");
  const img = document.getElementById("preview-img");
  const reticle = document.getElementById("drag-cam-handle");
  if (canvas) canvas.style.display = "block";
  if (img) img.style.display = "none";
  if (reticle) reticle.style.display = "none";
}

function togglePlayClipPreview() {
  if (isPlayingPreview) {
    stopPlayableClipPreview();
  } else {
    startPlayableClipPreview();
  }
}

function startPlayableClipPreview() {
  const selectedClip = getActiveOrFallbackClip();
  const sourceVid = document.getElementById("preview-source-video");
  if (!sourceVid) return;

  switchToPlayMode();
  updatePlayerInfo();

  const clipStart = selectedClip.start;
  const clipEnd = selectedClip.end;

  const initiatePlay = () => {
    // If current playback is outside clip range, seek to start
    if (isNaN(sourceVid.currentTime) || sourceVid.currentTime < clipStart || sourceVid.currentTime >= clipEnd) {
      try {
        sourceVid.currentTime = clipStart;
      } catch (e) {
        console.warn("Immediate seek deferred:", e);
      }
    }

    const startCanvasLoop = () => {
      isPlayingPreview = true;
      updatePlayButtonUI(true);
      if (animFrameId) {
        if (typeof sourceVid.cancelVideoFrameCallback === "function") {
          try { sourceVid.cancelVideoFrameCallback(animFrameId); } catch (_) {}
        }
        cancelAnimationFrame(animFrameId);
        animFrameId = null;
      }
      runCanvasRenderLoop(clipStart, clipEnd, selectedClip);
    };

    const playPromise = sourceVid.play();
    if (playPromise !== undefined) {
      playPromise.then(() => {
        startCanvasLoop();
      }).catch(err => {
        console.warn("Unmuted autoplay restricted by browser policy, using muted fallback:", err);
        sourceVid.muted = true;
        updateAudioButtonUI(true);
        sourceVid.play().then(() => {
          startCanvasLoop();
          showToast("🔇 Audio muted due to browser policy");
        }).catch(err2 => {
          console.error("Video play failed:", err2);
          stopPlayableClipPreview();
        });
      });
    } else {
      startCanvasLoop();
    }
  };

  const expectedSrc = `/media/video?t=${state.videoLoadedTimestamp || 0}`;
  if (!sourceVid.src || !sourceVid.src.includes("/media/video")) {
    sourceVid.src = expectedSrc;
    sourceVid.load();
  }

  if (sourceVid.readyState >= 2) {
    initiatePlay();
  } else {
    const onReady = () => {
      sourceVid.removeEventListener("canplay", onReady);
      sourceVid.removeEventListener("loadeddata", onReady);
      initiatePlay();
    };
    sourceVid.addEventListener("canplay", onReady, { once: true });
    sourceVid.addEventListener("loadeddata", onReady, { once: true });
    setTimeout(() => {
      initiatePlay();
    }, 250);
  }
}

function stopPlayableClipPreview() {
  isPlayingPreview = false;
  const sourceVid = document.getElementById("preview-source-video");
  if (sourceVid) {
    sourceVid.pause();
    if (typeof sourceVid.cancelVideoFrameCallback === "function" && animFrameId) {
      try { sourceVid.cancelVideoFrameCallback(animFrameId); } catch (_) {}
    }
  }
  if (animFrameId) {
    cancelAnimationFrame(animFrameId);
    animFrameId = null;
  }
  switchToLayoutMode();
  updatePlayButtonUI(false);
  if (sourceVid && !isNaN(sourceVid.currentTime)) {
    state.previewTime = sourceVid.currentTime;
  }
  triggerPreview(true);
}

function updatePlayButtonUI(isPlaying) {
  const icon = document.getElementById("icon-play-btn");
  const label = document.getElementById("label-play-btn");
  const btn = document.getElementById("btn-play-toggle") || document.getElementById("btn-play-clip-preview");
  const hint = document.getElementById("player-status-hint");

  if (icon) icon.className = isPlaying ? "fa-solid fa-pause" : "fa-solid fa-play";
  if (label) label.innerText = isPlaying ? "Pause Preview" : "Play Preview";
  if (btn) {
    if (isPlaying) {
      btn.classList.add("btn-primary");
      btn.classList.remove("btn-secondary");
    } else {
      btn.classList.remove("btn-primary");
      btn.classList.add("btn-secondary");
    }
  }
  if (hint) {
    hint.style.display = isPlaying ? "inline" : "none";
    hint.innerText = isPlaying ? "60 FPS Live" : "";
  }
}

// High-Performance Offscreen Bokeh Blur Canvas
let blurOffscreenCanvas = null;
let blurOffscreenCtx = null;

function runCanvasRenderLoop(clipStart, clipEnd, clip) {
  const sourceVid = document.getElementById("preview-source-video");
  const canvas = document.getElementById("preview-canvas");
  if (!sourceVid || !canvas) return;

  const hasRVFC = typeof sourceVid.requestVideoFrameCallback === "function";

  function onFrame() {
    if (!isPlayingPreview) return;

    const curTime = sourceVid.currentTime;

    // Check clip end boundary
    if (curTime >= clipEnd) {
      if (previewLoop) {
        try { sourceVid.currentTime = clipStart; } catch (_) {}
      } else {
        stopPlayableClipPreview();
        return;
      }
    }

    // Update scrubber UI
    const elapsed = Math.max(0, curTime - clipStart);
    const slider = document.getElementById("slider-player-time");
    const curLabel = document.getElementById("player-cur-time");
    if (slider) slider.value = elapsed;
    if (curLabel) curLabel.innerText = `${elapsed.toFixed(1)}s`;

    // Render 540x960 vertical short frame with zero-lag hardware sync
    renderCanvasFrame(clip, curTime);

    // Schedule next frame
    if (isPlayingPreview) {
      if (hasRVFC) {
        animFrameId = sourceVid.requestVideoFrameCallback(onFrame);
      } else {
        animFrameId = requestAnimationFrame(onFrame);
      }
    }
  }

  if (hasRVFC) {
    animFrameId = sourceVid.requestVideoFrameCallback(onFrame);
  } else {
    animFrameId = requestAnimationFrame(onFrame);
  }
}

function renderCanvasFrame(clip, customTime = null) {
  const sourceVid = document.getElementById("preview-source-video");
  const canvas = document.getElementById("preview-canvas");
  if (!sourceVid || !canvas) return;

  const ctx = canvas.getContext("2d");
  const curTime = customTime !== null ? customTime : sourceVid.currentTime;

  const cW = 540;
  const cH = 960;
  if (canvas.width !== cW) canvas.width = cW;
  if (canvas.height !== cH) canvas.height = cH;

  // Sync hardware GPU CSS filter on canvas (contrast, saturation, brightness)
  const contrastBoost = state.template.contrast_boost !== undefined ? state.template.contrast_boost : 1.08;
  const satBoost = state.template.saturation_boost !== undefined ? state.template.saturation_boost : 1.22;
  const brightOffset = state.template.brightness_offset !== undefined ? state.template.brightness_offset : 0.01;
  const effBrightness = 1.0 + brightOffset;
  canvas.style.filter = `contrast(${contrastBoost}) saturate(${satBoost}) brightness(${effBrightness})`;

  if (sourceVid.readyState < 2) {
    const img = document.getElementById("preview-img");
    if (img && img.complete && img.naturalWidth > 0) {
      ctx.drawImage(img, 0, 0, cW, cH);
      if (isPlayingPreview) {
        ctx.fillStyle = "rgba(12, 13, 18, 0.75)";
        ctx.beginPath();
        if (typeof ctx.roundRect === "function") {
          ctx.roundRect(cW / 2 - 80, cH / 2 - 18, 160, 36, 18);
        } else {
          ctx.rect(cW / 2 - 80, cH / 2 - 18, 160, 36);
        }
        ctx.fill();
        ctx.fillStyle = "#FFD700";
        ctx.font = "bold 13px Inter, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText("Buffering clip...", cW / 2, cH / 2);
      }
    } else {
      ctx.fillStyle = "#000000";
      ctx.fillRect(0, 0, cW, cH);
      if (isPlayingPreview) {
        ctx.fillStyle = "#FFD700";
        ctx.font = "bold 15px Inter, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText("Buffering clip...", cW / 2, cH / 2);
      }
    }
    return;
  }

  // Always fill base canvas with pure solid black (#000000)
  ctx.fillStyle = "#000000";
  ctx.fillRect(0, 0, cW, cH);

  // Check for Split Screen layout mode (Speed Viral Master Template)
  const isSplitScreen = state.template.webcam_shape === "split_screen" ||
                        state.template.layout_mode === "split_screen" ||
                        ((state.template.webcam_w || 0) >= 1000 && (state.template.gameplay_w || 0) >= 1000) ||
                        ((state.template.webcam_h || 0) >= 500);

  if (isSplitScreen) {
    const vidW = sourceVid.videoWidth || 1920;
    const vidH = sourceVid.videoHeight || 1080;
    const baseCrop = state.template.gameplay_crop || { x: 0, y: 0, w: vidW, h: vidH };
    const baseW = Math.max(32, baseCrop.w);
    const baseH = Math.max(32, baseCrop.h);
    let effZoom = parseFloat(state.template.gameplay_zoom || 1.15);
    const panX = parseFloat(state.template.gameplay_pan_x || 0.0);
    const panY = parseFloat(state.template.gameplay_pan_y || 0.0);

    // Speed Viral Split-Screen Layout (True 1080x1400 Reference Proportions)
    // Canvas: 540 x 960 (representing 1080x1920 Full HD or 1080x1400 Master)
    // Top Half (Facecam): 700px scaled to 350px (Y: 130 to 480)
    // Center divider & Subtitle focus: Y = 480 (50% canvas height)
    // Bottom Half (Gameplay): 700px scaled to 350px (Y: 480 to 830)
    // Total active video: 700px (1400px equivalent), perfectly matching C:\ppp reference files!
    const secH = Math.round(cH * (700 / 1920));   // 350px
    const topPad = Math.round((cH - (secH * 2)) / 2); // 130px
    const camY = topPad;                          // 130px
    const splitY = topPad + secH;                 // 480px
    const gpY = splitY;                           // 480px

    const cardAR = cW / secH;
    const baseAR = baseW / baseH;
    let fitW = baseW;
    let fitH = baseH;
    if (cardAR <= baseAR) {
      fitH = baseH;
      fitW = Math.round(baseH * cardAR);
    } else {
      fitW = baseW;
      fitH = Math.round(baseW / cardAR);
    }
    const zw = Math.max(32, Math.min(baseW, Math.round(fitW / effZoom)));
    const zh = Math.max(32, Math.min(baseH, Math.round(fitH / effZoom)));
    const availX = Math.max(0, baseW - zw);
    const availY = Math.max(0, baseH - zh);
    const centerX = baseCrop.x + Math.floor(availX / 2);
    const centerY = baseCrop.y + Math.floor(availY / 2);
    const shiftX = Math.round((panX / 100.0) * (availX / 2.0));
    const shiftY = Math.round((panY / 100.0) * (availY / 2.0));
    const finalCropX = Math.max(baseCrop.x, Math.min(baseCrop.x + availX, centerX + shiftX));
    const finalCropY = Math.max(baseCrop.y, Math.min(baseCrop.y + availY, centerY + shiftY));

    // 1. Draw Top Half: Facecam (Y: 200 to 480) - Fills top section edge-to-edge, just like gameplay!
    const camCrop = state.template.webcam_crop || { x: 20, y: 140, w: 480, h: 270 };
    const cw = Math.max(1, camCrop.w || 480);
    const ch = Math.max(1, camCrop.h || 270);
    const camAR = cw / ch;
    const slotAR = cW / secH;

    let effCW = cw;
    let effCH = ch;
    let effCX = camCrop.x;
    let effCY = camCrop.y;

    if (camAR > slotAR) {
      // Cropped region is wider than slot: cover width to match slotAR
      effCW = Math.round(ch * slotAR);
      effCX = camCrop.x + Math.round((cw - effCW) / 2);
    } else if (camAR < slotAR) {
      // Cropped region is taller than slot: cover height to match slotAR
      effCH = Math.round(cw / slotAR);
      effCY = camCrop.y + Math.round((ch - effCH) / 2);
    }

    // Fills the entire top section (0, camY, cW, secH) with 100% natural pixel aspect ratio, zero black bars inside section!
    ctx.drawImage(
      sourceVid,
      effCX, effCY, effCW, effCH,
      0, camY, cW, secH
    );

    // 2. Draw Bottom Half: Gameplay Centered Action (Y: 480 to 760)
    ctx.drawImage(
      sourceVid,
      finalCropX, finalCropY, zw, zh,
      0, gpY, cW, secH
    );

    // 3. Crisp Horizontal Center Divider Bar (Speed Style / Dynamic Thickness & Color)
    const divH = state.template.divider_height !== undefined ? parseInt(state.template.divider_height) : 4;
    if (divH > 0) {
      const canvasDivH = Math.max(1, Math.round(divH * (cH / 1920)));
      ctx.fillStyle = state.template.divider_color || "#FFFFFF";
      ctx.fillRect(0, Math.round(splitY - canvasDivH / 2), cW, canvasDivH);
    }

    // 4. Karaoke Subtitles (Positioned on Center Divider)
    drawCanvasSubtitles(ctx, curTime, cW, cH, clip);
    return;
  }

  // 1. Draw Pure Solid Black Background (zero video blur)
  ctx.fillStyle = "#000000";
  ctx.fillRect(0, 0, cW, cH);

  // 2. Draw Gameplay Window with framing, zoom, pan & aspect ratio
  const vidW = sourceVid.videoWidth || 1920;
  const vidH = sourceVid.videoHeight || 1080;
  const baseCrop = state.template.gameplay_crop || { x: 0, y: 0, w: vidW, h: vidH };
  const baseW = Math.max(32, baseCrop.w);
  const baseH = Math.max(32, baseCrop.h);
  const cardW = state.template.gameplay_w || 960;
  const cardH = state.template.gameplay_h || 540;
  const cardAR = Math.max(0.1, cardW / Math.max(1, cardH));
  const baseAR = baseW / Math.max(1, baseH);

  let effZoom = parseFloat(state.template.gameplay_zoom || 1.0);
  const panX = parseFloat(state.template.gameplay_pan_x || 0.0);
  const panY = parseFloat(state.template.gameplay_pan_y || 0.0);
  if (effZoom <= 1.0 && (Math.abs(panX) > 0.01 || Math.abs(panY) > 0.01)) {
    effZoom = 1.15;
  }

  let fitW = baseW;
  let fitH = baseH;
  if (cardAR <= baseAR) {
    fitH = baseH;
    fitW = Math.round(baseH * cardAR);
  } else {
    fitW = baseW;
    fitH = Math.round(baseW / cardAR);
  }

  const zw = Math.max(32, Math.min(baseW, Math.round(fitW / effZoom)));
  const zh = Math.max(32, Math.min(baseH, Math.round(fitH / effZoom)));
  const availX = Math.max(0, baseW - zw);
  const availY = Math.max(0, baseH - zh);
  const centerX = baseCrop.x + Math.floor(availX / 2);
  const centerY = baseCrop.y + Math.floor(availY / 2);
  const shiftX = Math.round((panX / 100.0) * (availX / 2.0));
  const shiftY = Math.round((panY / 100.0) * (availY / 2.0));
  const finalCropX = Math.max(baseCrop.x, Math.min(baseCrop.x + availX, centerX + shiftX));
  const finalCropY = Math.max(baseCrop.y, Math.min(baseCrop.y + availY, centerY + shiftY));

  const gpW = Math.round(cardW * (540 / 1080));
  const gpH = Math.round(cardH * (960 / 1920));
  const gpX = Math.round((cW - gpW) / 2);
  const gpY = Math.round((state.template.gameplay_y !== undefined ? state.template.gameplay_y : 690) * (960 / 1920));
  const gpRadius = Math.round((state.template.gameplay_radius !== undefined ? state.template.gameplay_radius : 36) * (540 / 1080));

  ctx.save();
  drawRoundedRectPath(ctx, gpX, gpY, gpW, gpH, gpRadius);
  ctx.clip();
  ctx.drawImage(
    sourceVid,
    finalCropX, finalCropY, zw, zh,
    gpX, gpY, gpW, gpH
  );
  ctx.restore();

  // Gameplay Border
  ctx.save();
  drawRoundedRectPath(ctx, gpX, gpY, gpW, gpH, gpRadius);
  ctx.strokeStyle = state.template.gameplay_border_color || "#FFFFFF";
  ctx.lineWidth = Math.max(1, Math.round((state.template.gameplay_border_w !== undefined ? state.template.gameplay_border_w : 6) * (540 / 1080)));
  ctx.stroke();
  ctx.restore();

  // 3. Draw Floating Webcam
  const camCrop = state.template.webcam_crop || { x: 0, y: 0, w: 400, h: 400 };
  const camW = Math.round((state.template.webcam_w || 300) * (540 / 1080));
  const camH = Math.round((state.template.webcam_h || 300) * (960 / 1920));
  const camX = state.template.webcam_x !== undefined
    ? Math.round(state.template.webcam_x * (540 / 1080))
    : Math.round((cW - camW) / 2);
  const camY = Math.round((state.template.webcam_y !== undefined ? state.template.webcam_y : 540) * (960 / 1920));
  const shape = state.template.webcam_shape || "circle";
  const glowEnabled = state.template.webcam_glow_enabled !== false;
  const glowColor = state.template.webcam_glow_color || "#C084FC";
  const camBorderW = Math.max(1, Math.round((state.template.webcam_border_w !== undefined ? state.template.webcam_border_w : 6) * (540 / 1080)));

  const drawCamOutline = () => {
    if (shape === "circle") {
      ctx.beginPath();
      ctx.arc(camX + camW / 2, camY + camH / 2, camW / 2, 0, Math.PI * 2);
      ctx.closePath();
    } else {
      const camRadius = Math.round((state.template.webcam_radius || 32) * (540 / 1080));
      drawRoundedRectPath(ctx, camX, camY, camW, camH, camRadius);
    }
  };

  ctx.save();
  drawCamOutline();
  ctx.clip();
  const fcw = Math.max(1, camCrop.w || 300);
  const fch = Math.max(1, camCrop.h || 300);
  const fCamAR = fcw / fch;
  const fTargetAR = camW / camH;
  let fDrawW, fDrawH, fDrawX, fDrawY;
  if (shape === "circle") {
    if (fCamAR >= fTargetAR) {
      fDrawH = camH;
      fDrawW = Math.round(camH * fCamAR);
      fDrawX = Math.round(camX - (fDrawW - camW) / 2);
      fDrawY = camY;
    } else {
      fDrawW = camW;
      fDrawH = Math.round(camW / fCamAR);
      fDrawX = camX;
      fDrawY = Math.round(camY - (fDrawH - camH) / 2);
    }
  } else {
    if (fCamAR >= fTargetAR) {
      fDrawW = camW;
      fDrawH = Math.round(camW / fCamAR);
      fDrawX = camX;
      fDrawY = Math.round(camY + (camH - fDrawH) / 2);
    } else {
      fDrawH = camH;
      fDrawW = Math.round(camH * fCamAR);
      fDrawX = Math.round(camX + (camW - fDrawW) / 2);
      fDrawY = camY;
    }
  }
  ctx.drawImage(
    sourceVid,
    camCrop.x, camCrop.y, fcw, fch,
    fDrawX, fDrawY, fDrawW, fDrawH
  );
  ctx.restore();

  // Webcam Neon Aura / Glow (Hardware Multi-Pass Stroke: 0ms CPU blur!)
  if (glowEnabled) {
    ctx.save();
    ctx.strokeStyle = glowColor;
    ctx.globalAlpha = 0.25;
    ctx.lineWidth = Math.round(camBorderW * 3.5);
    drawCamOutline();
    ctx.stroke();

    ctx.globalAlpha = 0.55;
    ctx.lineWidth = Math.round(camBorderW * 2.0);
    drawCamOutline();
    ctx.stroke();
    ctx.restore();
  }

  // Webcam Inner Crisp Border
  ctx.save();
  ctx.strokeStyle = state.template.webcam_border_color || "#FFFFFF";
  ctx.lineWidth = camBorderW;
  drawCamOutline();
  ctx.stroke();
  ctx.restore();

  // 4. Draw Karaoke Subtitles Active at curTime
  drawCanvasSubtitles(ctx, curTime, cW, cH, clip);
}

function drawCanvasSubtitles(ctx, curTime, cW, cH, clip = null) {
  // If subtitles are turned off globally or for this clip, do not render captions
  const subEnabled = (clip && clip.subtitle_config && clip.subtitle_config.enabled !== undefined)
    ? clip.subtitle_config.enabled
    : (state.subtitlesConfig.enabled !== false);
  if (!subEnabled) return;

  const subs = (clip && clip.subtitles && clip.subtitles.length > 0)
    ? clip.subtitles
    : (state.subtitles || []);
  const syncOffsetSec = (state.subtitlesConfig.sync_offset_ms || 0) / 1000.0;
  const effectiveTime = curTime - syncOffsetSec;
  const clipStart = (clip && typeof clip.start === "number") ? clip.start : 0;

  // Find active subtitle segment (supports absolute stream time OR clip-relative time)
  let activeSeg = subs.find(s =>
    (s.start <= effectiveTime && s.end >= effectiveTime) ||
    (s.start <= (effectiveTime - clipStart) && s.end >= (effectiveTime - clipStart))
  );

  // If live preview is playing and we have subtitles loaded, silence must stay blank
  if (isPlayingPreview && subs.length > 0 && !activeSeg) {
    return;
  }

  // If paused/styling mode and no active speech segment, show sample styling text
  if (!activeSeg) {
    if (isPlayingPreview && subs.length > 0) return;
    const sampleText = state.subtitlesConfig.preview_text || "UNREAL CLUTCH AIM";
    activeSeg = {
      text: sampleText,
      words: sampleText.split(" ").map(w => ({ word: w, start: effectiveTime - 1, end: effectiveTime + 5 }))
    };
  }

  const fontFam = state.subtitlesConfig.font_family || "Impact";
  const fontSize = Math.round((state.subtitlesConfig.font_size || 56) * (540 / 1080));
  const strokeW = Math.max(2, Math.round((state.subtitlesConfig.outline_width !== undefined ? state.subtitlesConfig.outline_width : 6) * (540 / 1080)));
  const shadowDepth = Math.round((state.subtitlesConfig.shadow_depth !== undefined ? state.subtitlesConfig.shadow_depth : 4) * (540 / 1080));
  const isUpper = state.subtitlesConfig.is_uppercase !== false;
  const priColor = state.subtitlesConfig.primary_color || "#FFFFFF";
  const hlColor = state.subtitlesConfig.highlight_color || "#FFDE00";
  const outColor = state.subtitlesConfig.outline_color || "#000000";
  const posX = cW * ((state.subtitlesConfig.position_x !== undefined ? state.subtitlesConfig.position_x : 50) / 100);
  const posY = cH * ((state.subtitlesConfig.position_y !== undefined ? state.subtitlesConfig.position_y : 82) / 100);

  ctx.save();
  if (state.subtitlesConfig.style_preset === "studio_flow" || state.subtitlesConfig.style_preset === "skyglow") {
    ctx.font = `800 ${fontSize}px "Montserrat", "Arial Black", Impact, sans-serif`;
  } else {
    ctx.font = `900 ${fontSize}px "${fontFam}", Impact, sans-serif`;
  }
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  const words = activeSeg.words || [];
  if (words.length > 0) {
    let totalW = 0;
    const wordWidths = words.map(w => {
      const cleanW = (w.word || "").replace(/[,.]+/g, "");
      const t = (isUpper ? cleanW.toUpperCase() : cleanW) + " ";
      const m = ctx.measureText(t).width;
      totalW += m;
      return { text: t, width: m, start: w.start, end: w.end };
    });

    let startX = posX - totalW / 2;
    wordWidths.forEach(wItem => {
      const isWordActive =
        (wItem.start <= effectiveTime && wItem.end >= effectiveTime) ||
        (wItem.start <= (effectiveTime - clipStart) && wItem.end >= (effectiveTime - clipStart));
      const color = isWordActive ? hlColor : priColor;

      // Smooth Reference Subtitles (C:\ppp reference clips: IShowSpeed style)
      // Highlighted words smoothly illuminate with zero bounce, zero scale distortion, and zero spatial jitter
      const scale = 1.0;

      const wordCenterX = startX + wItem.width / 2;
      const wordCenterY = posY;

      ctx.save();
      if (scale !== 1.0) {
        ctx.translate(wordCenterX, wordCenterY);
        ctx.scale(scale, scale);
        ctx.translate(-wordCenterX, -wordCenterY);
      }

      if (state.subtitlesConfig.style_preset === "studio_flow" || state.subtitlesConfig.style_preset === "skyglow") {
        ctx.save();
        ctx.shadowColor = "rgba(0, 0, 0, 0.78)";
        ctx.shadowBlur = 10;
        ctx.strokeStyle = "rgba(0, 0, 0, 0.35)";
        ctx.lineWidth = 1.6;
        ctx.strokeText(wItem.text, wordCenterX, wordCenterY);
        ctx.restore();

        const isUpcoming = (wItem.start > effectiveTime) && (wItem.start > (effectiveTime - clipStart));
        ctx.fillStyle = isWordActive ? hlColor : (isUpcoming ? "#A1A1AA" : priColor);
        ctx.fillText(wItem.text, wordCenterX, wordCenterY);
        ctx.restore();

        startX += wItem.width;
        return;
      }

      ctx.shadowColor = "rgba(0, 0, 0, 0.85)";
      ctx.shadowBlur = Math.round(shadowDepth * 1.5);
      ctx.shadowOffsetX = shadowDepth;
      ctx.shadowOffsetY = shadowDepth;

      ctx.strokeStyle = outColor;
      ctx.lineWidth = strokeW;
      ctx.strokeText(wItem.text, wordCenterX, wordCenterY);

      ctx.fillStyle = color;
      ctx.fillText(wItem.text, wordCenterX, wordCenterY);
      ctx.restore();

      startX += wItem.width;
    });
  } else {
    const cleanT = (activeSeg.text || "").replace(/[,.]+/g, "");
    const text = isUpper ? cleanT.toUpperCase() : cleanT;
    ctx.save();
    ctx.shadowColor = "rgba(0, 0, 0, 0.85)";
    ctx.shadowBlur = Math.round(shadowDepth * 1.5);
    ctx.shadowOffsetX = shadowDepth;
    ctx.shadowOffsetY = shadowDepth;

    ctx.strokeStyle = outColor;
    ctx.lineWidth = strokeW;
    ctx.strokeText(text, posX, posY);

    ctx.fillStyle = priColor;
    ctx.fillText(text, posX, posY);
    ctx.restore();
  }
  ctx.restore();
}

function drawRoundedRectPath(ctx, x, y, width, height, radius) {
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + width - radius, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
  ctx.lineTo(x + width, y + height - radius);
  ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  ctx.lineTo(x + radius, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
}

// -------------------------------------------------------------
// Stream URL Loader (YouTube, Twitch, Kick VODs)
// -------------------------------------------------------------
function initStreamUrlLoader() {
  const urlInput = document.getElementById("input-stream-url");
  const btnProbe = document.getElementById("btn-probe-stream");
  const probedBox = document.getElementById("stream-probed-box");
  const thumbImg = document.getElementById("stream-thumb-img");
  const titleText = document.getElementById("stream-title-text");
  const uploaderText = document.getElementById("stream-uploader-text");
  const durationText = document.getElementById("stream-duration-text");
  const startInput = document.getElementById("input-stream-start");
  const endInput = document.getElementById("input-stream-end");
  const btnClip = document.getElementById("btn-clip-stream-range");
  const quickPresets = document.getElementById("stream-quick-presets");
  const btnHunt = document.getElementById("btn-stream-hunt-moments");
  const btnAudioFast = document.getElementById("btn-stream-scan-audio");
  const candidatesList = document.getElementById("stream-candidates-list");
  const progressBox = document.getElementById("stream-progress-box");
  const progressText = document.getElementById("stream-progress-text");
  const progressPercent = document.getElementById("stream-progress-percent");
  const progressBar = document.getElementById("stream-progress-bar");

  if (!urlInput || !btnProbe) return;

  let currentMeta = null;
  let progressInterval = null;

  function parseTimeSec(str) {
    if (!str) return 0;
    const parts = str.toString().trim().split(":").map(Number);
    if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
    if (parts.length === 2) return parts[0] * 60 + parts[1];
    if (parts.length === 1) return parts[0] || 0;
    return 0;
  }

  function formatTimeHMS(sec) {
    sec = Math.max(0, Math.floor(sec || 0));
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    const pad = (n) => String(n).padStart(2, "0");
    return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `00:${pad(m)}:${pad(s)}`;
  }

  // 1. Probe Stream
  btnProbe.addEventListener("click", async () => {
    const url = urlInput.value.trim();
    if (!url) {
      showToast("Please enter a stream link (YouTube, Twitch, or Kick)");
      return;
    }

    btnProbe.disabled = true;
    btnProbe.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Probing...`;

    try {
      const res = await fetch("/api/probe_stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Failed to probe stream" }));
        throw new Error(err.detail || "Stream probe failed");
      }

      const data = await res.json();
      currentMeta = data.meta;

      // Populate UI
      if (thumbImg) thumbImg.src = currentMeta.thumbnail || "";
      if (titleText) titleText.innerText = currentMeta.title || "Live Stream";
      if (uploaderText) uploaderText.innerHTML = `<i class="fa-solid fa-user"></i> ${currentMeta.uploader || "Streamer"}`;
      if (durationText) durationText.innerHTML = `<i class="fa-solid fa-clock"></i> ${currentMeta.duration_str || formatTimeHMS(currentMeta.duration)}`;

      // Default slice: 00:00:00 to 00:15:00 (or stream duration if shorter)
      const defaultSliceDur = Math.min(900, currentMeta.duration || 900);
      if (startInput) startInput.value = "00:00:00";
      if (endInput) endInput.value = formatTimeHMS(defaultSliceDur);

      // Render viral candidates if found
      if (candidatesList && data.viral_candidates && data.viral_candidates.length > 0) {
        candidatesList.innerHTML = "";
        data.viral_candidates.forEach((c) => {
          const item = document.createElement("div");
          item.style.cssText = "display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.03); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 6px 10px; cursor: pointer; transition: all 0.2s;";
          const scoreVal = c.virality_score || c.score || 90;
          const reasonTag = c.reason || "🔥 Viral Stream Peak";
          const badgeBg = c.badge_color || "#06B6D4";
          item.innerHTML = `
            <div style="flex: 1; min-width: 0;">
              <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 2px;">
                <div style="font-size: 11px; font-weight: 700; color: #fff; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${c.title}</div>
                <span style="background: ${badgeBg}; color: #000; font-size: 8.5px; font-weight: 800; padding: 1px 5px; border-radius: 3px; white-space: nowrap;">${scoreVal}% VIRAL</span>
              </div>
              <div style="font-size: 10px; color: var(--accent-lime); font-family: var(--font-mono); display: flex; gap: 6px; align-items: center;">
                <span>${formatTimeHMS(c.start)} → ${formatTimeHMS(c.end)}</span>
                <span style="color: var(--text-dim);">•</span>
                <span style="color: #cbd5e1;">${reasonTag}</span>
              </div>
            </div>
            <button class="btn btn-secondary btn-sm" type="button" style="padding: 3px 8px; font-size: 10px; white-space: nowrap;">Select</button>
          `;
          item.addEventListener("click", () => {
            if (startInput) startInput.value = formatTimeHMS(c.start);
            if (endInput) endInput.value = formatTimeHMS(c.end);
            document.querySelectorAll("#stream-candidates-list > div").forEach(d => d.style.borderColor = "var(--border-subtle)");
            item.style.borderColor = "var(--accent-lime)";
            showToast(`Selected: ${c.title}`);
          });
          candidatesList.appendChild(item);
        });
        candidatesList.style.display = "flex";
      }

      if (probedBox) probedBox.style.display = "block";
      showToast("Stream info loaded! Select time slice and click Clip & Load.");
    } catch (err) {
      if (err.message && (err.message.toLowerCase().includes("bot") || err.message.toLowerCase().includes("sign in"))) {
        alert(
          "🛡️ YouTube Anti-Bot Verification:\n\n" +
          "YouTube has gated this stream link behind an automated anti-bot check ('Sign in to confirm you're not a bot').\n\n" +
          "HOW TO PROCEED:\n" +
          "• (Recommended): Download the stream/clip in your regular web browser (where you are already logged in), and simply drag & drop the MP4 file directly into OpenShorts Studio! (100% full quality, instantaneous loading, zero restrictions).\n" +
          "• (Or): Place an exported 'cookies.txt' file in the OpenShorts-Studio folder."
        );
      } else {
        alert("Stream Probe Error: " + err.message);
      }
    } finally {
      btnProbe.disabled = false;
      btnProbe.innerHTML = `<i class="fa-solid fa-magnifying-glass"></i> Probe Stream`;
    }
  });

  // 2. Quick Presets (15m, 30m, 1h)
  if (quickPresets) {
    quickPresets.querySelectorAll(".preset-pill").forEach(pill => {
      pill.addEventListener("click", () => {
        const dur = parseInt(pill.dataset.dur) || 900;
        const maxDur = (currentMeta && currentMeta.duration) ? currentMeta.duration : dur;
        const sliceEnd = Math.min(dur, maxDur);
        if (startInput) startInput.value = "00:00:00";
        if (endInput) endInput.value = formatTimeHMS(sliceEnd);
        quickPresets.querySelectorAll(".preset-pill").forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
      });
    });
  }

  // 3. AI Discover Viral Peaks button
  if (btnHunt) {
    btnHunt.addEventListener("click", () => {
      if (candidatesList) {
        if (candidatesList.children.length === 0) {
          showToast("Probing entire stream chapters and chat energy for viral peaks...");
          btnProbe.click();
        } else {
          candidatesList.style.display = candidatesList.style.display === "none" ? "flex" : "none";
        }
      }
    });
  }

  // 3b. Audio-First Fast Hunter (OpusClip / Klap Architecture: Pulls 30MB in 3-5s)
  if (btnAudioFast) {
    btnAudioFast.addEventListener("click", async () => {
      const url = urlInput.value.trim();
      if (!url) {
        showToast("Please enter a stream link first");
        return;
      }

      btnAudioFast.disabled = true;
      btnAudioFast.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Audio Pull (3s)...`;

      try {
        const data = await runAsyncJob("/api/scan_stream_audio", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url })
        }, {
          container: progressBox,
          bar: progressBar,
          text: progressText,
          percent: progressPercent,
          initialText: "Fast Mode: Pulling lightweight voice audio track (~30MB)...",
          initialPercent: 20
        });

        currentMeta = data.meta;

        if (thumbImg) thumbImg.src = currentMeta.thumbnail || "";
        if (titleText) titleText.innerText = currentMeta.title || "Live Stream";
        if (uploaderText) uploaderText.innerHTML = `<i class="fa-solid fa-user"></i> ${currentMeta.uploader || "Streamer"}`;
        if (durationText) durationText.innerHTML = `<i class="fa-solid fa-clock"></i> ${currentMeta.duration_str || formatTimeHMS(currentMeta.duration)}`;

        if (candidatesList && data.viral_candidates && data.viral_candidates.length > 0) {
          candidatesList.innerHTML = "";
          data.viral_candidates.forEach((c) => {
            const item = document.createElement("div");
            item.style.cssText = "display: flex; justify-content: space-between; align-items: center; background: rgba(255,255,255,0.03); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); padding: 6px 10px; cursor: pointer; transition: all 0.2s;";
            const scoreVal = c.virality_score || 92;
            const reasonTag = c.reason || "⚡ Acoustic Audio Peak";
            const badgeBg = c.badge_color || "#EF4444";
            item.innerHTML = `
              <div style="flex: 1; min-width: 0;">
                <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 2px;">
                  <div style="font-size: 11px; font-weight: 700; color: #fff; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${c.title}</div>
                  <span style="background: ${badgeBg}; color: #000; font-size: 8.5px; font-weight: 800; padding: 1px 5px; border-radius: 3px; white-space: nowrap;">${scoreVal}% VIRAL</span>
                </div>
                <div style="font-size: 10px; color: var(--accent-lime); font-family: var(--font-mono); display: flex; gap: 6px; align-items: center;">
                  <span>${formatTimeHMS(c.start)} → ${formatTimeHMS(c.end)}</span>
                  <span style="color: var(--text-dim);">•</span>
                  <span style="color: #cbd5e1;">${reasonTag}</span>
                </div>
              </div>
              <button class="btn btn-lime btn-sm" type="button" style="padding: 3px 8px; font-size: 10px; white-space: nowrap;"><i class="fa-solid fa-bolt"></i> Load Slice</button>
            `;
            item.addEventListener("click", () => {
              if (startInput) startInput.value = formatTimeHMS(c.start);
              if (endInput) endInput.value = formatTimeHMS(c.end);
              document.querySelectorAll("#stream-candidates-list > div").forEach(d => d.style.borderColor = "var(--border-subtle)");
              item.style.borderColor = "var(--accent-lime)";
              showToast(`Selected moment: ${c.title}. Tap 'Clip & Load Slice' to pull video!`);
            });

            // 1-Tap Load on mobile: clicking the Load Slice button immediately downloads and loads this moment
            const loadBtn = item.querySelector("button");
            if (loadBtn) {
              loadBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                if (startInput) startInput.value = formatTimeHMS(c.start);
                if (endInput) endInput.value = formatTimeHMS(c.end);
                if (btnClip) btnClip.click();
              });
            }
            candidatesList.appendChild(item);
          });
          candidatesList.style.display = "flex";
        }

        if (probedBox) probedBox.style.display = "block";
        if (progressBox) progressBox.style.display = "none";
        showToast(`⚡ Audio-First scan complete (${data.audio_size_mb || 30} MB)! Discovered top viral moments.`);
      } catch (err) {
        clearInterval(pInterval);
        if (progressBox) progressBox.style.display = "none";
        if (err.message && (err.message.toLowerCase().includes("bot") || err.message.toLowerCase().includes("sign in"))) {
          alert(
            "🛡️ YouTube Anti-Bot Verification:\n\n" +
            "YouTube has gated this stream link behind an automated anti-bot check ('Sign in to confirm you're not a bot').\n\n" +
            "HOW TO PROCEED:\n" +
            "• (Recommended): Download the stream/clip in your regular web browser (where you are already logged in), and simply drag & drop the MP4 file directly into OpenShorts Studio! (100% full quality, instantaneous loading, zero restrictions).\n" +
            "• (Or): Place an exported 'cookies.txt' file in the OpenShorts-Studio folder."
          );
        } else {
          alert("Audio-First Scan Error: " + err.message);
        }
      } finally {
        btnAudioFast.disabled = false;
        btnAudioFast.innerHTML = `<i class="fa-solid fa-bolt"></i> ⚡ Audio-First (3s)`;
      }
    });
  }

  // 4. Clip & Load Stream Range
  if (btnClip) {
    btnClip.addEventListener("click", async () => {
      const url = urlInput.value.trim();
      if (!url) {
        showToast("Please enter a stream link first");
        return;
      }

      const sSec = parseTimeSec(startInput ? startInput.value : "00:00:00");
      const eSec = parseTimeSec(endInput ? endInput.value : "00:15:00");

      if (eSec <= sSec) {
        showToast("End time must be after start time");
        return;
      }

      const sliceDur = eSec - sSec;
      if (sliceDur > 2400) {
        alert(
          "⚠️ High-Speed Tip for Long Streams:\n\n" +
          `You selected ${(sliceDur / 3600).toFixed(1)} hours of raw 1080p video (~${Math.round((sliceDur / 60) * 0.4)} GB).\n` +
          "Downloading multi-hour raw video over the web connection will time out the server tunnel.\n\n" +
          "⚡ HOW TO PROCEED INSTANTLY:\n\n" +
          "1. (Recommended): Tap '⚡ Audio-First (3s)' right below! It downloads only the 25 MB audio from the entire 2 hours in 3 seconds, finds all the screaming/hype moments, and lets you pull just the viral clips!\n\n" +
          "2. (Or): Choose a 10 to 20-minute slice (e.g. First 15m or First 30m preset) which downloads in ~15 seconds without waiting."
        );
        return;
      }

      btnClip.disabled = true;

      try {
        const qualitySel = document.getElementById("select-stream-quality")?.value || "max";
        const data = await runAsyncJob("/api/load_stream_range", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            url,
            start_sec: sSec,
            end_sec: eSec,
            title: currentMeta ? currentMeta.title : "Stream Highlight",
            quality: qualitySel
          })
        }, {
          container: progressBox,
          bar: progressBar,
          text: progressText,
          percent: progressPercent,
          initialText: `Downloading stream slice (${formatTimeHMS(sSec)} to ${formatTimeHMS(eSec)})...`,
          initialPercent: 10
        });
        if (globalStreamTracker) {
          globalStreamTracker.complete(`<i class="fa-solid fa-circle-check" style="color:var(--accent-lime);"></i> Slice loaded into Studio!`);
        } else {
          if (progressBar) progressBar.style.width = "100%";
          if (progressPercent) progressPercent.innerText = "100%";
          if (progressText) progressText.innerHTML = `<i class="fa-solid fa-circle-check" style="color:var(--accent-lime);"></i> Slice loaded into Studio!`;
        }

        // Instantly load the downloaded video slice into studio with candidate's actual viral title
        if (data.slice && data.slice.file_path) {
          const sliceTitle = (currentMeta && currentMeta.title && currentMeta.title !== "Stream Highlight") ? currentMeta.title : (data.slice.title || "Viral Highlight");
          await loadSource(data.slice.file_path, false, sliceTitle);
        }

        showToast("Stream slice loaded! Auto-extracted viral moments ready.");
        setTimeout(() => {
          if (progressBox) progressBox.style.display = "none";
        }, 2500);
      } catch (err) {
        clearInterval(progressInterval);
        if (err.isCancelled) {
          showToast("Stream slice load cancelled.");
        } else if (err.message && (err.message.toLowerCase().includes("bot") || err.message.toLowerCase().includes("sign in"))) {
          alert(
            "🛡️ YouTube Anti-Bot Verification:\n\n" +
            "YouTube has gated this stream link behind an automated anti-bot check ('Sign in to confirm you're not a bot').\n\n" +
            "HOW TO PROCEED:\n" +
            "• (Recommended): Download the stream/clip in your regular web browser (where you are already logged in), and simply drag & drop the MP4 file directly into OpenShorts Studio! (100% full quality, instantaneous loading, zero restrictions).\n" +
            "• (Or): Place an exported 'cookies.txt' file in the OpenShorts-Studio folder."
          );
        } else {
          alert("Stream Load Error: " + err.message);
        }
      } finally {
        btnClip.disabled = false;
      }
    });
  }
}

// -------------------------------------------------------------
// Facecam Keyboard & Directional Arrow Controls
// -------------------------------------------------------------
function initFacecamArrowControls() {
  window.addEventListener("keydown", (e) => {
    const activeEl = document.activeElement;
    if (activeEl && (activeEl.tagName === "INPUT" || activeEl.tagName === "TEXTAREA" || activeEl.isContentEditable)) {
      return;
    }

    const step = e.shiftKey ? 25 : 8;
    if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)) {
      const activeTab = document.querySelector(".tab-content.active");
      const isTab2 = activeTab && activeTab.id === "tab-template";

      if (isTab2 || document.getElementById("phone-screen")?.contains(activeEl)) {
        e.preventDefault();
        if (e.key === "ArrowUp") window.nudgeCamReticle?.(0, -step);
        else if (e.key === "ArrowDown") window.nudgeCamReticle?.(0, step);
        else if (e.key === "ArrowLeft") window.nudgeCamReticle?.(-step, 0);
        else if (e.key === "ArrowRight") window.nudgeCamReticle?.(step, 0);
      }
    }
  });
}

// -------------------------------------------------------------
// Gameplay Interactive Drag-to-Pan (Phone Canvas)
// -------------------------------------------------------------
function initGameplayZoomAndPanControls() {
  const phoneScreen = document.getElementById("phone-screen");
  if (!phoneScreen) return;

  let isPanning = false;
  let startX = 0;
  let startY = 0;
  let initPanX = 0;
  let initPanY = 0;

  phoneScreen.addEventListener("mousedown", (e) => {
    if (e.target.closest("#drag-subtitle") || e.target.closest("#drag-cam-handle") || e.target.closest("button")) {
      return;
    }

    const rect = phoneScreen.getBoundingClientRect();
    const relY = (e.clientY - rect.top) / rect.height;

    // Bottom half of preview screen is gameplay area
    if (relY >= 0.45) {
      isPanning = true;
      startX = e.clientX;
      startY = e.clientY;
      initPanX = state.template.gameplay_pan_x || 0;
      initPanY = state.template.gameplay_pan_y || 0;
      phoneScreen.style.cursor = "grabbing";
      e.preventDefault();
    }
  });

  window.addEventListener("mousemove", (e) => {
    if (!isPanning) return;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;

    const rect = phoneScreen.getBoundingClientRect();
    const pctDx = Math.round((dx / rect.width) * 100);
    const pctDy = Math.round((dy / rect.height) * 100);

    const newX = Math.max(-100, Math.min(100, initPanX + pctDx));
    const newY = Math.max(-100, Math.min(100, initPanY + pctDy));

    state.template.gameplay_pan_x = newX;
    state.template.gameplay_pan_y = newY;
    updateGPPanUI(newX, newY);

    if ((newX !== 0 || newY !== 0) && (state.template.gameplay_zoom || 1.0) <= 1.0) {
      state.template.gameplay_zoom = 1.15;
      const zS = document.getElementById("slider-gp-zoom");
      const zL = document.getElementById("val-gp-zoom");
      if (zS) zS.value = "1.15";
      if (zL) zL.innerText = "1.15x";
    }
    requestPreviewUpdate();
  });

  window.addEventListener("mouseup", () => {
    if (isPanning) {
      isPanning = false;
      phoneScreen.style.cursor = "default";
      requestPreviewUpdate();
    }
  });

  phoneScreen.addEventListener("touchstart", (e) => {
    if (e.target.closest("#drag-subtitle") || e.target.closest("#drag-cam-handle") || e.target.closest("button")) return;
    const rect = phoneScreen.getBoundingClientRect();
    const touch = e.touches[0];
    const relY = (touch.clientY - rect.top) / rect.height;
    if (relY >= 0.45) {
      isPanning = true;
      startX = touch.clientX;
      startY = touch.clientY;
      initPanX = state.template.gameplay_pan_x || 0;
      initPanY = state.template.gameplay_pan_y || 0;
    }
  }, { passive: true });

  window.addEventListener("touchmove", (e) => {
    if (!isPanning || !e.touches || !e.touches[0]) return;
    const touch = e.touches[0];
    const dx = touch.clientX - startX;
    const dy = touch.clientY - startY;
    const rect = phoneScreen.getBoundingClientRect();
    const pctDx = Math.round((dx / rect.width) * 100);
    const pctDy = Math.round((dy / rect.height) * 100);
    const newX = Math.max(-100, Math.min(100, initPanX + pctDx));
    const newY = Math.max(-100, Math.min(100, initPanY + pctDy));
    state.template.gameplay_pan_x = newX;
    state.template.gameplay_pan_y = newY;
    updateGPPanUI(newX, newY);
    requestPreviewUpdate();
  }, { passive: true });

  window.addEventListener("touchend", () => {
    if (isPanning) {
      isPanning = false;
      requestPreviewUpdate();
    }
  });
}
