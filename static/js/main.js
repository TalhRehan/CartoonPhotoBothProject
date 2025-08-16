const $ = (s) => document.querySelector(s);

/* Panels */
const panelCapture = $("#panelCapture");
const panelPreview = $("#panelPreview");
const panelPrint   = $("#panelPrint");

/* Capture UI */
const cameraEl = $("#camera");
const captureBtn = $("#captureBtn");
const countdownEl = $("#countdown");
const autoHint = $("#autoHint");
const manualToggle = $("#manualToggle");
const autoFaceToggle = $("#autoFaceToggle");
const faceOverlay = $("#faceOverlay");
const resetBtn = $("#resetBtn");
const settingsBtn = $("#settingsBtn");

/* Preview UI */
const photoCanvas = $("#photoCanvas");
const origPreview = $("#origPreview");
const cartoonPreview = $("#cartoonPreview");
const cartoonWrap = $("#cartoonWrap");
const processing = $("#processing");
const procText = $("#procText");
const retryBtn = $("#retryBtn");

const approveBtn = $("#approveBtn");
const retakeBtn = $("#retakeBtn");

/* Layout options */
const shapeSelect = $("#shapeSelect");
const borderSelect = $("#borderSelect");
const themeSelect = $("#themeSelect");
const brandColorInput = $("#brandColor");
const brandToggle = $("#brandToggle");
const brandTextInput = $("#brandText");

/* Print UI */
const sheetPreview = $("#sheetPreview");
const printBtn = $("#printBtn");
const downloadPdfBtn = $("#downloadPdfBtn");
const backToEditBtn = $("#backToEditBtn");

/* Settings modal */
const settingsModalEl = $("#settingsModal");
const timerInput = $("#timerInput");
const soundToggle = $("#soundToggle");
const langSelect = $("#langSelect");
const kioskToggle = $("#kioskToggle");
const saveSettingsBtn = $("#saveSettingsBtn");

/* Camera settings UI */
const cameraSelect = document.querySelector("#cameraSelect");
const refreshCamerasBtn = document.querySelector("#refreshCamerasBtn");
const resolutionSelect = document.querySelector("#resolutionSelect");
const mirrorToggle = document.querySelector("#mirrorToggle");

/* Toast host */
const toastHost = $("#toastHost");

/* i18n labels (English only) */
const i18n = {
  en: {
    brand: "Sticker Booth",
    manual: "Manual",
    autoFace: "Auto Face",
    startCapture: "Start Capture",
    autoHint: (n)=> `Auto capture in ${n}s`,
    converting: "Converting to cartoon…",
    retry: "Retry",
    approve: "Approve",
    retake: "Retake",
    printNow: "Print Now",
    downloadPdf: "Download PDF",
    backToEdit: "Back to Edit",
    shape: "Shape",
    border: "Border",
    theme: "Theme",
    branding: "Branding",
    settings: "Settings",
    countdown: "Countdown (seconds)",
    sound: "Countdown sound",
    language: "Language",
    kiosk: "Kiosk mode (fullscreen)",
    reset: "Reset",
    toastReady: "Cartoon ready!",
    toastFallback: "Fallback mode used (local stylize). Background may not be transparent.",
    toastErr: (msg)=> `Error: ${msg}`,
    alignFace: "Align your face in the box",
    captureNow: "Capture Now"
  }
};

/* Globals */
let stream = null;
let useManual = false;
let autoFaceOn = true;
let countdownRunning = false;
let faceStableFrames = 0;
const STABLE_N = 8;
const CENTER_TOL = 0.18;
const MIN_FACE_RATIO = 0.18;

let detector = null;
let latestCartoonData = null;
let latestPhotoData = null;

const settings = {
  timerSeconds: 5,
  countdownSound: true,
  language: "en",       // default to English
  kioskMode: false,
  cameraId: null,       // deviceId or "facing:user" / "facing:environment"
  resolution: "auto",   // e.g. "1920x1080"
  mirrorPreview: true
};

/* Load/save settings */
function loadSettings(){
  try{
    const s = JSON.parse(localStorage.getItem("booth_settings") || "{}");
    Object.assign(settings, s);
    // force English if something else was saved previously
    settings.language = "en";
  }catch{}
}
function saveSettings(){
  localStorage.setItem("booth_settings", JSON.stringify(settings));
}
function applySettingsToUI(){
  timerInput.value = settings.timerSeconds;
  soundToggle.checked = settings.countdownSound;
  langSelect.value = settings.language; // will be "en"
  kioskToggle.checked = settings.kioskMode;
  resolutionSelect.value = settings.resolution || "auto";
  mirrorToggle.checked = settings.mirrorPreview;
  applyLanguage();
  applyKioskMode(settings.kioskMode);
}

/* i18n */
function t(key){
  // Only "en" exists; keep helper for future-proofing
  return i18n.en[key];
}
function applyLanguage(){
  $("#txtBrand").textContent = i18n.en.brand;
  $("#txtManual").textContent = i18n.en.manual;
  $("#txtAutoFace").textContent = i18n.en.autoFace;
  $("#txtSettings").textContent = i18n.en.settings;
  $("#txtTimer").textContent = i18n.en.countdown;
  $("#txtSound").textContent = i18n.en.sound;
  $("#txtLanguage").textContent = i18n.en.language;
  $("#txtKiosk").textContent = i18n.en.kiosk;

  $("#txtShape").textContent = i18n.en.shape;
  $("#txtBorder").textContent = i18n.en.border;
  $("#txtTheme").textContent = i18n.en.theme;
  $("#txtBranding").textContent = i18n.en.branding;

  captureBtn.textContent = useManual ? i18n.en.captureNow : i18n.en.startCapture;
  autoHint.textContent = i18n.en.autoHint(settings.timerSeconds);
  procText.textContent = i18n.en.converting;
  retryBtn.textContent = i18n.en.retry;
  approveBtn.textContent = i18n.en.approve;
  retakeBtn.textContent = i18n.en.retake;
  printBtn.textContent = i18n.en.printNow;
  downloadPdfBtn.textContent = i18n.en.downloadPdf;
  backToEditBtn.textContent = i18n.en.backToEdit;
  $("#resetBtn").textContent = i18n.en.reset;
}

/* Toast */
function showToast(msg, type=""){
  const div = document.createElement("div");
  div.className = `toast ${type}`;
  div.textContent = msg;
  toastHost.appendChild(div);
  setTimeout(()=> div.remove(), 3500);
}

/* Telemetry */
async function logEvent(level, message, meta={}){
  try{
    await fetch("/api/log", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ level, message, meta })
    });
  }catch{}
}

/* Fetch with timeout + JSON */
async function fetchJson(url, opts={}, timeoutMs=60000){
  const controller = new AbortController();
  const id = setTimeout(()=> controller.abort(), timeoutMs);
  try{
    const res = await fetch(url, { ...opts, signal: controller.signal });
    const txt = await res.text();
    let json = {};
    try { json = JSON.parse(txt); } catch { json = { raw: txt }; }
    if(!res.ok){
      const msg = json.error || `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return json;
  } finally {
    clearTimeout(id);
  }
}

/* Camera helpers */
async function enumerateCameras(){
  try{
    const devices = await navigator.mediaDevices.enumerateDevices();
    const videos = devices.filter(d => d.kind === "videoinput");
    cameraSelect.innerHTML = "";

    // Facing shortcuts (mobile-friendly)
    cameraSelect.add(new Option("Front (user)", "facing:user"));
    cameraSelect.add(new Option("Back (environment)", "facing:environment"));

    if(videos.length === 0){
      const opt = new Option("No video inputs found", "", true, true);
      opt.disabled = true;
      cameraSelect.add(opt);
      return;
    }
    for(const d of videos){
      const label = d.label || `Camera ${cameraSelect.length - 1}`;
      cameraSelect.add(new Option(label, d.deviceId));
    }

    // Keep/restore selection
    const found = Array.from(cameraSelect.options).some(o => o.value === settings.cameraId);
    cameraSelect.value = found ? settings.cameraId : (settings.cameraId || "facing:user");
    if(!found) settings.cameraId = cameraSelect.value;

  }catch(e){
    console.warn("enumerateDevices failed", e);
    showToast("Unable to enumerate cameras.", "error");
  }
}

function parseResolution(res){
  if(!res || res === "auto") return null;
  const [w,h] = res.split("x").map(n => parseInt(n,10));
  if(Number.isFinite(w) && Number.isFinite(h)) return { width:w, height:h };
  return null;
}

function buildConstraints(){
  const base = { audio: false, video: {} };
  const res = parseResolution(settings.resolution);
  if(res){
    base.video.width  = { ideal: res.width };
    base.video.height = { ideal: res.height };
  } else {
    base.video.width  = { ideal: 1920 };
    base.video.height = { ideal: 1080 };
  }

  if(settings.cameraId === "facing:user"){
    base.video.facingMode = "user";
  } else if(settings.cameraId === "facing:environment"){
    base.video.facingMode = { ideal: "environment" };
  } else if(settings.cameraId){
    base.video.deviceId = { exact: settings.cameraId };
  } else {
    base.video.facingMode = "user";
  }
  return base;
}

function applyMirrorClass(){
  const useMirror = settings.mirrorPreview;
  cameraEl.classList.toggle("mirror", useMirror);
  faceOverlay.classList.toggle("mirror", useMirror);
}

async function stopCamera(){
  if(stream){
    for(const t of stream.getTracks()) t.stop();
    stream = null;
  }
}

async function startCameraWithConstraints(constraints){
  await stopCamera();
  const s = await navigator.mediaDevices.getUserMedia(constraints);
  stream = s;
  cameraEl.srcObject = stream;

  setTimeout(()=>{
    const rect = cameraEl.getBoundingClientRect();
    faceOverlay.width  = rect.width;
    faceOverlay.height = rect.height;
  }, 100);

  applyMirrorClass();
}

async function restartCameraFromSettings(){
  try{
    const constraints = buildConstraints();
    await startCameraWithConstraints(constraints);
    showToast("Camera switched", "success");
  }catch(e){
    showToast("Camera start failed: " + e.message, "error");
  }
}

/* Face Detector */
async function initFaceDetector(){
  if('FaceDetector' in window){
    try{
      detector = new window.FaceDetector({ fastMode: true, maxDetectedFaces: 1 });
      return;
    }catch(e){
      console.warn("FaceDetector init failed", e);
    }
  }
  detector = null;
  autoFaceToggle.checked = false;
  autoFaceToggle.disabled = true;
  showToast("Auto face not supported on this browser. Use manual/timer.", "error");
}

function drawOverlay(faceBox, ok){
  const ctx = faceOverlay.getContext("2d");
  const w = faceOverlay.width, h = faceOverlay.height;
  ctx.clearRect(0,0,w,h);

  // Center safe zone
  const cx = w/2, cy = h/2;
  const tolX = w * CENTER_TOL, tolY = h * CENTER_TOL;
  ctx.strokeStyle = "rgba(0,229,255,0.45)";
  ctx.lineWidth = 2;
  ctx.setLineDash([8,8]);
  ctx.strokeRect(cx - tolX, cy - tolY, tolX*2, tolY*2);
  ctx.setLineDash([]);

  if(faceBox){
    ctx.strokeStyle = ok ? "rgba(0,255,120,0.9)" : "rgba(255,180,0,0.9)";
    ctx.lineWidth = 3;
    ctx.strokeRect(faceBox.x, faceBox.y, faceBox.width, faceBox.height);
  }

  ctx.fillStyle = "rgba(0,0,0,0.45)";
  ctx.fillRect(w/2 - 160, 10, 320, 28);
  ctx.fillStyle = "#fff";
  ctx.font = "14px Poppins, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(i18n.en.alignFace, w/2, 30);
}

async function startFaceLoop(){
  if(!detector) return;
  const loop = async ()=>{
    try{
      if(!autoFaceOn || useManual || countdownRunning || panelCapture.classList.contains("active") === false){
        const ctx = faceOverlay.getContext("2d");
        ctx.clearRect(0,0,faceOverlay.width, faceOverlay.height);
        requestAnimationFrame(loop); return;
      }
      const faces = await detector.detect(cameraEl);
      const ctxRect = cameraEl.getBoundingClientRect();
      const overlayRect = faceOverlay.getBoundingClientRect();
      const scaleX = overlayRect.width / ctxRect.width;
      const scaleY = overlayRect.height / ctxRect.height;

      let faceBox = null;
      if(faces && faces.length){
        let best = faces[0];
        for(const f of faces){
          if(f.boundingBox.width * f.boundingBox.height > best.boundingBox.width * best.boundingBox.height){
            best = f;
          }
        }
        const bb = best.boundingBox;
        faceBox = {
          x: bb.x * scaleX, y: bb.y * scaleY,
          width: bb.width * scaleX, height: bb.height * scaleY
        };

        const cx = faceOverlay.width/2, cy = faceOverlay.height/2;
        const fb_cx = faceBox.x + faceBox.width/2;
        const fb_cy = faceBox.y + faceBox.height/2;
        const centered = Math.abs(fb_cx - cx) < (CENTER_TOL * faceOverlay.width) &&
                         Math.abs(fb_cy - cy) < (CENTER_TOL * faceOverlay.height);
        const bigEnough = (faceBox.height / faceOverlay.height) >= MIN_FACE_RATIO;
        const ok = centered && bigEnough;

        drawOverlay(faceBox, ok);
        if(ok){
          faceStableFrames++;
          if(faceStableFrames >= STABLE_N){
            faceStableFrames = 0;
            startAutoCountdownAndCapture();
            countdownRunning = true;
          }
        } else {
          faceStableFrames = 0;
        }
      } else {
        drawOverlay(null, false);
        faceStableFrames = 0;
      }
    }catch(e){
      // keep loop alive
    } finally {
      requestAnimationFrame(loop);
    }
  };
  requestAnimationFrame(loop);
}

/* Snapshot & Flow */
function takeSnapshotFromVideo(){
  const videoWidth = cameraEl.videoWidth || 1600;
  const videoHeight = cameraEl.videoHeight || 1200;
  photoCanvas.width = videoWidth;
  photoCanvas.height = videoHeight;
  const ctx = photoCanvas.getContext("2d");
  ctx.drawImage(cameraEl, 0, 0, videoWidth, videoHeight);
  return photoCanvas.toDataURL("image/png");
}

function setBusy(btn, busy, label="Please wait…"){
  btn.disabled = busy;
  if(busy){
    btn.dataset._txt = btn.textContent;
    btn.textContent = label;
  }else{
    if(btn.dataset._txt) btn.textContent = btn.dataset._txt;
  }
}

/* Beep (WebAudio) */
let audioCtx = null;
function beep(freq=880, dur=120){
  if(!settings.countdownSound) return;
  try{
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const o = audioCtx.createOscillator();
    const g = audioCtx.createGain();
    o.type = "sine"; o.frequency.value = freq;
    o.connect(g); g.connect(audioCtx.destination);
    g.gain.setValueAtTime(0.001, audioCtx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.2, audioCtx.currentTime + 0.02);
    o.start();
    setTimeout(()=>{ g.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.02); o.stop(); }, dur);
  }catch{}
}

async function startAutoCountdownAndCapture(){
  captureBtn.disabled = true;
  const secs = Math.max(3, Math.min(10, parseInt(settings.timerSeconds)||5));
  autoHint.textContent = i18n.en.autoHint(secs);

  countdownEl.classList.remove("d-none");
  let n = secs;
  countdownEl.textContent = n;

  const timer = setInterval(()=>{
    n -= 1;
    countdownEl.textContent = n;
    beep(880 - (secs - n)*40, 90);
    if(n <= 0){
      clearInterval(timer);
      countdownEl.classList.add("d-none");
      doCaptureFlow().finally(()=>{
        countdownRunning = false;
        captureBtn.disabled = false;
      });
    }
  }, 1000);
}

/* === quality gate + forceFresh retry === */
async function runCartoonize(imageData, attempt=1){
  processing.classList.remove("d-none");
  cartoonWrap.classList.add("d-none");
  approveBtn.disabled = true;
  retryBtn.classList.add("d-none");
  procText.textContent = attempt > 1 ? `Retrying… (attempt ${attempt})` : i18n.en.converting;

  const payload = {
    imageData,
    qualityGate: true,
    forceFresh: attempt > 1
  };

  try{
    const res = await fetch("/api/cartoonize", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    });

    // Quality gate failed
    if(res.status === 422){
      const j = await res.json();
      processing.classList.add("d-none");
      cartoonWrap.classList.add("d-none");
      approveBtn.disabled = true;

      const reason = j.reason;
      if(reason === "blurry"){
        showToast("Photo looks blurry. Please retake.", "error");
      } else if(reason === "dark"){
        showToast("Photo is too dark. Improve lighting and retake.", "error");
      } else {
        showToast("Photo quality is low. Please retake.", "error");
      }
      showPanel(panelCapture);
      return;
    }

    if(!res.ok){
      const j = await res.json().catch(()=> ({}));
      throw new Error(j.error || `HTTP ${res.status}`);
    }

    const json = await res.json();
    latestCartoonData = json.cartoonData;
    cartoonPreview.src = latestCartoonData;

    processing.classList.add("d-none");
    cartoonWrap.classList.remove("d-none");
    approveBtn.disabled = false;

    if(json.fallback){
      showToast(i18n.en.toastFallback, "error");
      logEvent("warn", "fallback_stylize_used");
    }else{
      showToast(i18n.en.toastReady, "success");
    }
  }catch(err){
    procText.textContent = `Conversion failed: ${err.message}`;
    retryBtn.classList.remove("d-none");
    showToast(i18n.en.toastErr(err.message), "error");
    logEvent("error", "cartoonize_failed", { message: err.message });
  }
}

async function doCaptureFlow(){
  const snap = takeSnapshotFromVideo();
  latestPhotoData = snap;
  origPreview.src = snap;
  showPanel(panelPreview);
  await runCartoonize(snap, 1);
}

/* Panels */
function showPanel(name){
  [panelCapture, panelPreview, panelPrint].forEach(p => p.classList.remove("active"));
  void name.offsetWidth;
  name.classList.add("active");
}

/* Kiosk mode */
function applyKioskMode(on){
  document.body.classList.toggle("kiosk", on);
  try{
    if(on && !document.fullscreenElement){
      document.documentElement.requestFullscreen().catch(()=>{});
    } else if(!on && document.fullscreenElement){
      document.exitFullscreen().catch(()=>{});
    }
  }catch{}
  function prevent(e){ e.preventDefault(); }
  if(on){
    document.addEventListener("contextmenu", prevent);
  }else{
    document.removeEventListener("contextmenu", prevent);
  }
}

/* Reset session */
function resetSession(){
  latestPhotoData = null;
  latestCartoonData = null;
  cartoonWrap.classList.add("d-none");
  processing.classList.add("d-none");
  approveBtn.disabled = true;
  showPanel(panelCapture);
}

/* EVENTS */
manualToggle.addEventListener("change", (e)=>{
  useManual = e.target.checked;
  autoHint.classList.toggle("d-none", useManual);
  captureBtn.textContent = useManual ? i18n.en.captureNow : i18n.en.startCapture;
});
autoFaceToggle.addEventListener("change", (e)=>{ autoFaceOn = e.target.checked; });

captureBtn.addEventListener("click", async ()=>{
  if(useManual){
    await doCaptureFlow();
  }else{
    await startAutoCountdownAndCapture();
  }
});

retryBtn.addEventListener("click", async ()=>{
  retryBtn.classList.add("d-none");
  await runCartoonize(latestPhotoData, 2); // attempt 2 => forceFresh
});

retakeBtn.addEventListener("click", ()=> resetSession());

approveBtn.addEventListener("click", async ()=>{
  if(!latestCartoonData){
    showToast(i18n.en.toastErr("Please wait for the cartoon"), "error");
    return;
  }
  const shape = shapeSelect?.value || "circle";
  const border = borderSelect?.value || "none";
  const theme  = themeSelect?.value || "none";
  const brand_color = brandColorInput?.value || "#FF4081";
  const branding = brandToggle?.checked || false;
  const brand_text = brandTextInput?.value || "";

  setBusy(approveBtn, true, "Preparing sheet…");
  try{
    const res = await fetch("/api/print-sheet", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        imageData: latestCartoonData,
        options: { shape, border, branding, brand_text, theme, brand_color }
      })
    });
    if(!res.ok){
      const j = await res.json().catch(()=> ({}));
      throw new Error(j.error || "Failed to generate A4 sheet");
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    sheetPreview.src = url;
    showPanel(panelPrint);
  }catch(err){
    showToast("Sheet generation error: " + err.message, "error");
    logEvent("error", "sheet_failed", { message: err.message });
  }finally{
    setBusy(approveBtn, false);
  }
});

backToEditBtn.addEventListener("click", ()=> showPanel(panelPreview));

printBtn.addEventListener("click", ()=>{
  const w = window.open("", "_blank");
  if(!w){ alert("Popup blocked! Please allow popups and try again."); return; }
  w.document.write(`
    <html><head><title>Sticker Sheet</title>
    <style>@page{size:A4;margin:10mm}body{margin:0}img{width:100%;height:auto}</style>
    </head><body><img src="${sheetPreview.src}" />
    <script>window.onload=()=>{window.focus();window.print();};</script>
    </body></html>
  `);
  w.document.close();
});

downloadPdfBtn.addEventListener("click", async ()=>{
  if(!latestCartoonData){ showToast("No sheet to export.", "error"); return; }
  const shape = shapeSelect?.value || "circle";
  const border = borderSelect?.value || "none";
  const theme  = themeSelect?.value || "none";
  const brand_color = brandColorInput?.value || "#FF4081";
  const branding = brandToggle?.checked || false;
  const brand_text = brandTextInput?.value || "";
  try{
    const res = await fetch("/api/print-sheet-pdf", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        imageData: latestCartoonData,
        options: { shape, border, branding, brand_text, theme, brand_color }
      })
    });
    if(!res.ok){
      const j = await res.json().catch(()=> ({}));
      throw new Error(j.error || "Failed to create PDF");
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "sticker_sheet_a4.pdf"; a.click();
    URL.revokeObjectURL(url);
  }catch(err){
    showToast("PDF error: " + err.message, "error");
    logEvent("error", "pdf_failed", { message: err.message });
  }
});

resetBtn.addEventListener("click", ()=>{
  resetSession();
  showToast("Session reset", "success");
});

/* Settings modal */
let bsModal = null;
settingsBtn.addEventListener("click", async ()=>{
  // Optional: show warning if API key missing (requires /api/info; ignored if not present)
  try{
    const info = await fetchJson("/api/info", {}, 8000);
    if(info && info.key_present === false){
      showToast("OpenAI API key missing on server. Please set OPENAI_API_KEY.", "error");
    }
  }catch{}
  bsModal = bsModal || new bootstrap.Modal(settingsModalEl);
  bsModal.show();
});

saveSettingsBtn.addEventListener("click", async ()=>{
  const old = { ...settings };

  settings.timerSeconds = Math.max(3, Math.min(10, parseInt(timerInput.value)||5));
  settings.countdownSound = !!soundToggle.checked;
  settings.language = "en"; // always English
  const kioskWas = settings.kioskMode;
  settings.kioskMode = !!kioskToggle.checked;

  settings.cameraId = cameraSelect?.value || null;
  settings.resolution = resolutionSelect?.value || "auto";
  settings.mirrorPreview = !!mirrorToggle?.checked;

  saveSettings();
  applySettingsToUI();

  const camChanged = old.cameraId !== settings.cameraId || old.resolution !== settings.resolution;
  const mirrorChanged = old.mirrorPreview !== settings.mirrorPreview;

  if (camChanged) {
    await restartCameraFromSettings();
  } else if (mirrorChanged) {
    applyMirrorClass();
  }

  if(!kioskWas && settings.kioskMode) showToast("Kiosk mode ON", "success");
  else if(kioskWas && !settings.kioskMode) showToast("Kiosk mode OFF", "success");

  bsModal?.hide();
});

/* Camera settings UI events */
refreshCamerasBtn.addEventListener("click", async ()=>{
  await enumerateCameras();
  showToast("Camera list refreshed", "success");
});

cameraSelect.addEventListener("change", async ()=>{
  settings.cameraId = cameraSelect.value;
  saveSettings();
  await restartCameraFromSettings();
});

resolutionSelect.addEventListener("change", async ()=>{
  settings.resolution = resolutionSelect.value;
  saveSettings();
  await restartCameraFromSettings();
});

mirrorToggle.addEventListener("change", ()=>{
  settings.mirrorPreview = !!mirrorToggle.checked;
  saveSettings();
  applyMirrorClass();
});

/* Init */
async function initCamera(){
  try{
    const constraints = buildConstraints();
    await startCameraWithConstraints(constraints);
    await enumerateCameras();

    if (navigator.mediaDevices && "ondevicechange" in navigator.mediaDevices){
      navigator.mediaDevices.addEventListener("devicechange", async ()=>{
        await enumerateCameras();
        const found = Array.from(cameraSelect.options).some(o => o.value === settings.cameraId);
        if(!found){
          settings.cameraId = cameraSelect.value;
          saveSettings();
          await restartCameraFromSettings();
          showToast("Cameras changed — switched.", "success");
        }else{
          showToast("Cameras changed", "");
        }
      });
    }

    await initFaceDetector();
    startFaceLoop();
  } catch(e){
    alert("Camera access failed: " + e.message);
    logEvent("error", "camera_access_failed", { message: e.message });
  }
}

window.addEventListener("DOMContentLoaded", async ()=>{
  loadSettings();
  applySettingsToUI();
  applyLanguage();
  autoHint.textContent = i18n.en.autoHint(settings.timerSeconds);
  await initCamera();
});
