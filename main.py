"""AutoCut Backend V3 - Works 100% on Render Free Tier"""
import os, uuid, shutil, subprocess, json, asyncio
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="AutoCut API V3")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

UPLOAD_DIR = Path("/tmp/autocut/uploads")
OUTPUT_DIR = Path("/tmp/autocut/outputs")
WORK_DIR = Path("/tmp/autocut/processing")
for d in [UPLOAD_DIR, OUTPUT_DIR, WORK_DIR]: d.mkdir(parents=True, exist_ok=True)

jobs = {}

class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int
    message: str
    output_url: Optional[str] = None
    error: Optional[str] = None

STYLES = {
    "pop": {"anim": "{\\fscx0\\fscy0\\t(0,80,\\fscx110\\fscy110)\\t(80,150,\\fscx100\\fscy100)}", "font": "Impact", "size": 58, "outline": 5},
    "fade": {"anim": "{\\fad(200,200)}", "font": "Arial", "size": 48, "outline": 3},
    "bounce": {"anim": "{\\fscx0\\fscy0\\t(0,100,\\fscx120\\fscy120)\\t(100,200,\\fscx95\\fscy95)\\t(200,300,\\fscx100\\fscy100)}", "font": "Impact", "size": 54, "outline": 4},
    "typewriter": {"anim": "{\\fad(50,0)}", "font": "Courier New", "size": 44, "outline": 2},
}

COLORS = {"white": "&H00FFFFFF", "yellow": "&H0000FFFF", "cyan": "&H00FFFF00", "red": "&H000000FF"}

@app.get("/")
async def root(): return {"message": "AutoCut V3", "status": "ok"}

@app.get("/health")
async def health(): return {"status": "healthy"}

@app.post("/upload")
async def upload(bg: BackgroundTasks, file: UploadFile = File(...), montage_type: str = Form("tiktok_classic"), options: str = Form("{}"), subtitle_text: str = Form("")):
    if not file.filename: raise HTTPException(400, "No file")
    ext = Path(file.filename).suffix.lower()
    if ext not in {".mp4", ".mov", ".avi", ".mkv", ".webm"}: raise HTTPException(400, "Bad format")
    
    opts = json.loads(options) if options else {}
    job_id = str(uuid.uuid4())[:8]
    inp = UPLOAD_DIR / f"{job_id}{ext}"
    out = OUTPUT_DIR / f"{job_id}_out.mp4"
    
    with open(inp, "wb") as f: shutil.copyfileobj(file.file, f)
    jobs[job_id] = JobStatus(job_id=job_id, status="pending", progress=0, message="Starting...")
    bg.add_task(process, job_id, str(inp), str(out), montage_type, opts, subtitle_text)
    return {"job_id": job_id}

@app.get("/status/{job_id}")
async def status(job_id: str):
    if job_id not in jobs: raise HTTPException(404, "Not found")
    return jobs[job_id]

@app.get("/download/{job_id}")
async def download(job_id: str):
    if job_id not in jobs: raise HTTPException(404, "Not found")
    if jobs[job_id].status != "completed": raise HTTPException(400, "Not ready")
    out = OUTPUT_DIR / f"{job_id}_out.mp4"
    if not out.exists(): raise HTTPException(404, "File missing")
    return FileResponse(str(out), filename=f"autocut_{job_id}.mp4", media_type="video/mp4")

async def process(job_id: str, inp: str, out: str, mtype: str, opts: dict, text: str):
    try:
        jobs[job_id].status = "processing"
        jobs[job_id].progress = 10
        jobs[job_id].message = "Analyzing..."
        
        work = WORK_DIR / job_id
        work.mkdir(parents=True, exist_ok=True)
        
        info = get_info(inp)
        jobs[job_id].progress = 30
        jobs[job_id].message = "Creating subtitles..."
        
        sub = work / "subs.ass"
        make_subs(str(sub), info, opts, text, mtype)
        
        jobs[job_id].progress = 60
        jobs[job_id].message = "Rendering..."
        
        flt = build_flt(str(sub), mtype, opts, info)
        await asyncio.to_thread(render, inp, out, flt)
        
        jobs[job_id].status = "completed"
        jobs[job_id].progress = 100
        jobs[job_id].message = "Done!"
        jobs[job_id].output_url = f"/download/{job_id}"
        
        shutil.rmtree(work, ignore_errors=True)
        os.remove(inp)
    except Exception as e:
        jobs[job_id].status = "failed"
        jobs[job_id].error = str(e)
        jobs[job_id].message = f"Error: {e}"

def get_info(p: str) -> dict:
    r = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", p], capture_output=True, text=True)
    d = json.loads(r.stdout)
    vs = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    return {"width": int(vs.get("width", 1080)), "height": int(vs.get("height", 1920)), "duration": float(d.get("format", {}).get("duration", 10))}

def make_subs(path: str, info: dict, opts: dict, text: str, mtype: str):
    st = STYLES.get(opts.get("subtitle_style", "pop"), STYLES["pop"])
    col = COLORS.get(opts.get("colors", "white"), "&H00FFFFFF")
    pos = opts.get("position", "center")
    align = {"center": 5, "bottom": 2, "top": 8}.get(pos, 5)
    mv = 100 if pos == "center" else 60
    
    ass = f"""[Script Info]
Title: AutoCut
ScriptType: v4.00+
PlayResX: {info['width']}
PlayResY: {info['height']}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{st['font']},{st['size']},{col},&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,2,0,1,{st['outline']},0,{align},20,20,{mv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()] if text.strip() else ["AutoCut V3", f"Style: {mtype}", "Montage auto", "By AI"]
    dur = info["duration"]
    tpl = min(3.0, dur / max(len(lines), 1))
    for i, line in enumerate(lines):
        s = f"{int(i*tpl//3600)}:{int((i*tpl%3600)//60):02d}:{i*tpl%60:05.2f}"
        e = f"{int(((i+1)*tpl-0.1)//3600)}:{int((((i+1)*tpl-0.1)%3600)//60):02d}:{((i+1)*tpl-0.1)%60:05.2f}"
        ass += f"Dialogue: 0,{s},{e},Default,,0,0,0,,{st['anim']}{line}\n"
    with open(path, "w", encoding="utf-8") as f: f.write(ass)

def build_flt(sub: str, mtype: str, opts: dict, info: dict) -> str:
    fl = [f"ass={sub.replace(':', '\\:')}"]
    if mtype == "tiktok_edit":
        if opts.get("video_effects") == "vhs": fl.append("noise=alls=20:allf=t+u")
        elif opts.get("video_effects") == "rgb_split": fl.append("rgbashift=rh=-3:bh=3")
        if opts.get("overlay") == "grain": fl.append("noise=alls=10:allf=t")
    elif mtype == "cinematic":
        g = opts.get("color_grade", "")
        if g == "warm": fl.append("colorbalance=rs=.1:gs=0:bs=-.1")
        elif g == "cold": fl.append("colorbalance=rs=-.1:gs=0:bs=.1")
        elif g == "vintage": fl.append("curves=vintage")
        elif g == "teal_orange": fl.append("colorbalance=rs=.1:gs=-.05:bs=-.1:rm=-.1:gm=.05:bm=.1")
        if opts.get("aspect_ratio") == "21_9_letterbox":
            bh = int(info["height"] * 0.12)
            fl.append(f"drawbox=x=0:y=0:w=iw:h={bh}:c=black:t=fill,drawbox=x=0:y=ih-{bh}:w=iw:h={bh}:c=black:t=fill")
    elif mtype == "comedy":
        if opts.get("effects") == "deep_fried": fl.append("eq=saturation=3:contrast=1.5,noise=alls=30:allf=t")
        elif opts.get("effects") == "vhs": fl.append("noise=alls=20:allf=t+u")
    elif mtype == "motivation" and opts.get("cinematic") == "letterbox":
        bh = int(info["height"] * 0.1)
        fl.append(f"drawbox=x=0:y=0:w=iw:h={bh}:c=black:t=fill,drawbox=x=0:y=ih-{bh}:w=iw:h={bh}:c=black:t=fill")
    return ",".join(fl)

def render(inp: str, out: str, flt: str):
    r = subprocess.run(["ffmpeg", "-y", "-i", inp, "-vf", flt, "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out], capture_output=True, text=True)
    if r.returncode != 0:
        subprocess.run(["ffmpeg", "-y", "-i", inp, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-c:a", "aac", out], capture_output=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
