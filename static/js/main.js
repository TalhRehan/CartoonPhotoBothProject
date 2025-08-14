const $ = (s) => document.querySelector(s);

const panelCapture = $("#panelCapture");
const panelPreview = $("#panelPreview");
const panelPrint   = $("#panelPrint");

const cameraEl = $("#camera");
const captureBtn = $("#captureBtn");
const countdownEl = $("#countdown");
const autoHint = $("#autoHint");
const manualToggle = $("#manualToggle");

const photoCanvas = $("#photoCanvas");
const origPreview = $("#origPreview");
const cartoonPreview = $("#cartoonPreview");
const processing = $("#processing");

const approveBtn = $("#approveBtn");
const retakeBtn = $("#retakeBtn");

const sheetPreview = $("#sheetPreview");
const printBtn = $("#printBtn");
const backToEditBtn = $("#backToEditBtn");

let stream = null;
let useManual = false;
let latestCartoonData = null;
let latestPhotoData = null;

function showPanel(name){
  [panelCapture, panelPreview, panelPrint].forEach(p => p.classList.remove("active"));
  name.classList.add("active");
}

async function initCamera(){
  try{
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 1920 },
        height: { ideal: 1080 },
        facingMode: "user"
      },
      audio:false
    });
    cameraEl.srcObject = stream;
  } catch(e){
    alert("Camera access failed: " + e.message);
  }
}

function takeSnapshotFromVideo(){
  const videoWidth = cameraEl.videoWidth || 1600;
  const videoHeight = cameraEl.videoHeight || 1200;

  // High-res canvas for better print quality
  photoCanvas.width = videoWidth;
  photoCanvas.height = videoHeight;

  const ctx = photoCanvas.getContext("2d");
  ctx.drawImage(cameraEl, 0, 0, videoWidth, videoHeight);

  const dataUrl = photoCanvas.toDataURL("image/png"); // lossless PNG
  return dataUrl;
}

function setBusy(btn, busy){
  btn.disabled = busy;
  if(busy){
    btn.dataset._txt = btn.textContent;
    btn.textContent = "Please wait…";
  }else{
    if(btn.dataset._txt) btn.textContent = btn.dataset._txt;
  }
}

async function startAutoCountdownAndCapture(){
  captureBtn.disabled = true;
  countdownEl.classList.remove("d-none");
  let n = 5;
  countdownEl.textContent = n;

  const timer = setInterval(()=>{
    n -= 1;
    countdownEl.textContent = n;
    if(n <= 0){
      clearInterval(timer);
      countdownEl.classList.add("d-none");
      doCaptureFlow();
    }
  }, 1000);
}

async function doCaptureFlow(){
  // 1) Snapshot
  const snap = takeSnapshotFromVideo();
  latestPhotoData = snap;

  // 2) Go to Preview panel + show original thumbnail
  origPreview.src = snap;
  cartoonPreview.classList.add("d-none");
  processing.classList.remove("d-none");
  showPanel(panelPreview);

  // 3) Send to backend for cartoonize (stub returns same for now)
  try{
    const res = await fetch("/api/cartoonize", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ imageData: snap })
    });
    const json = await res.json();
    if(!res.ok) throw new Error(json.error || "Cartoonize failed");
    latestCartoonData = json.cartoonData;

    // 4) Show cartoon preview
    cartoonPreview.src = latestCartoonData;
    processing.classList.add("d-none");
    cartoonPreview.classList.remove("d-none");
  }catch(err){
    processing.classList.add("d-none");
    alert("Cartoon conversion error: " + err.message);
  }finally{
    captureBtn.disabled = false;
  }
}

manualToggle.addEventListener("change", (e)=>{
  useManual = e.target.checked;
  autoHint.classList.toggle("d-none", useManual);
  captureBtn.textContent = useManual ? "Capture Now" : "Start Capture";
});

captureBtn.addEventListener("click", async ()=>{
  if(useManual){
    await doCaptureFlow();
  }else{
    await startAutoCountdownAndCapture();
  }
});

retakeBtn.addEventListener("click", ()=>{
  // Reset preview state
  latestPhotoData = null;
  latestCartoonData = null;
  cartoonPreview.classList.add("d-none");
  processing.classList.add("d-none");
  showPanel(panelCapture);
});

approveBtn.addEventListener("click", async ()=>{
  // NOTE: We'll compose A4 in a later chunk. For now we already have backend stub ready.
  if(!latestCartoonData){
    alert("Please wait for cartoon preview to load.");
    return;
  }
  setBusy(approveBtn, true);
  try{
    const res = await fetch("/api/print-sheet", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ imageData: latestCartoonData })
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
    alert("Sheet generation error: " + err.message);
  }finally{
    setBusy(approveBtn, false);
  }
});

backToEditBtn.addEventListener("click", ()=>{
  showPanel(panelPreview);
});

printBtn.addEventListener("click", ()=>{
  // Open a printable window
  const w = window.open("", "_blank");
  if(!w){
    alert("Popup blocked! Please allow popups and try again.");
    return;
  }
  // Simple print layout (A4 friendly)
  w.document.write(`
    <html>
      <head>
        <title>Sticker Sheet</title>
        <style>
          @page { size: A4; margin: 10mm; }
          body { margin:0; }
          img { width:100%; height:auto; }
        </style>
      </head>
      <body>
        <img src="${sheetPreview.src}" />
        <script>
          window.onload = () => { window.focus(); window.print(); };
        </script>
      </body>
    </html>
  `);
  w.document.close();
});

window.addEventListener("DOMContentLoaded", initCamera);
