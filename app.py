"""
Product Listing Generator — web server.

Run with:
    python app.py
    # or: uvicorn app:app --reload
"""

import asyncio
import io
import json
import zipfile
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pipeline import run_pipeline

# Ensure output dir exists before mounting
Path("output").mkdir(exist_ok=True)

app = FastAPI(title="Product Listing Generator")
app.mount("/files", StaticFiles(directory="output"), name="output_files")

# In-memory job store: job_id -> {queue, task}
jobs: dict[str, dict] = {}


# ------------------------------------------------------------------ models

class RunRequest(BaseModel):
    url: str


# ------------------------------------------------------------------ routes

@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.post("/run")
async def start_run(req: RunRequest):
    url = req.url.strip()
    if not url.startswith("http"):
        raise HTTPException(400, "URL must start with http:// or https://")

    job_id = str(uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    jobs[job_id] = {"queue": queue}

    async def _run():
        def log(msg: str):
            queue.put_nowait({"type": "log", "msg": msg})

        try:
            results = await run_pipeline(url, log)
            queue.put_nowait({"type": "results", "data": results})
        except Exception as e:
            queue.put_nowait({"type": "error", "msg": str(e)})
        finally:
            queue.put_nowait(None)  # sentinel — close the SSE stream

    asyncio.create_task(_run())
    return {"job_id": job_id}


@app.get("/stream/{job_id}")
async def stream_events(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    queue: asyncio.Queue = jobs[job_id]["queue"]

    async def _generate():
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=120.0)
            except asyncio.TimeoutError:
                # Keep-alive ping so the connection doesn't drop
                yield "data: " + json.dumps({"type": "ping"}) + "\n\n"
                continue

            if event is None:
                yield "data: " + json.dumps({"type": "done"}) + "\n\n"
                break
            yield "data: " + json.dumps(event) + "\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/download/{slug}")
async def download_zip(slug: str):
    output_dir = Path("output") / slug
    if not output_dir.exists():
        raise HTTPException(404, "Output not found")

    def _build_zip() -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(output_dir.rglob("*")):
                if f.is_file():
                    zf.write(f, f.relative_to(output_dir))
        return buf.getvalue()

    zip_bytes = await asyncio.to_thread(_build_zip)
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{slug}.zip"'},
    )


# ------------------------------------------------------------------ entry point

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
