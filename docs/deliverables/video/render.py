"""Render the system video (brief item 3d) to dist/demo.mp4.

Three tools, one command, run from the repository root:

    python3 docs/deliverables/video/render.py            # record, then compose
    python3 docs/deliverables/video/render.py --no-record  # recompose only

1. VHS plays demo.tape against the real curses UI and writes
   dist/demo-raw.mp4. The tmux status line in that recording is a step
   marker that flips between green and magenta at the start of each step.
2. Headless Google Chrome renders one caption bar per ``# caption:`` line
   in the tape, as a PNG. This ffmpeg build has no text filters, so text is
   drawn by the browser instead.
3. ffmpeg crops the marker line off the recording, stacks the caption bar
   underneath, switches captions at the marker flips, and writes
   dist/demo.mp4 at 1920x1080.

Needs ``brew install vhs`` (which brings ttyd and ffmpeg) and Google Chrome.
Standard library only; this script is tooling, not part of the PIM.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TAPE = HERE / "demo.tape"
RAW = ROOT / "dist" / "demo-raw.mp4"
OUT = ROOT / "dist" / "demo.mp4"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

FINAL_HEIGHT = 1080
LIMIT_SECONDS = 240  # the brief: no more than 4 minutes
MARKERS = {"green": (0, 255, 0), "magenta": (255, 0, 255)}
CAPTION_LINE = re.compile(r"^# caption: (.+?) \| (.+)$")

CAPTION_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><style>
html, body {{ margin: 0; width: {width}px; height: {height}px; overflow: hidden; background: #121316; }}
.band {{
  box-sizing: border-box; height: 100%; display: flex; align-items: center; gap: 28px;
  padding: 0 56px; border-top: 3px solid #fde68a; color: #f5f5f4;
  font-family: -apple-system, "SF Pro Display", "Helvetica Neue", Helvetica, sans-serif;
}}
.count {{ flex: none; min-width: 84px; font: 600 26px Menlo, monospace; color: #a8a29e; }}
.tag {{
  flex: none; padding: 8px 18px; border-radius: 10px; background: #fde68a; color: #1c1917;
  font-size: 30px; font-weight: 700; letter-spacing: 0.01em; white-space: nowrap;
}}
.text {{ font-size: 40px; font-weight: 600; line-height: 1.2; }}
.progress {{ position: fixed; left: 0; bottom: 0; height: 6px; width: {progress}%; background: #fde68a; }}
</style></head>
<body><div class="band">{count}<span class="tag">{tag}</span><span class="text">{text}</span></div>
<div class="progress"></div></body></html>
"""


def run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command, failing loudly with its stderr if it exits non-zero."""
    result = subprocess.run(args, capture_output=True, **kwargs)
    if result.returncode != 0:
        sys.exit(f"{args[0]} failed:\n{result.stderr.decode(errors='replace')[-2000:]}")
    return result


def read_captions(tape: Path) -> list[tuple[str, str]]:
    """Return (tag, text) for every ``# caption: tag | text`` line, in order."""
    found = []
    for line in tape.read_text(encoding="utf-8").splitlines():
        match = CAPTION_LINE.match(line)
        if match:
            found.append((match.group(1).strip(), match.group(2).strip()))
    if not found:
        sys.exit(f"no '# caption:' lines in {tape}")
    return found


def probe(video: Path) -> tuple[int, int, Fraction]:
    """Return (width, height, frames per second) of the first video stream."""
    out = run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate", "-of", "json", str(video),
    ]).stdout
    stream = json.loads(out)["streams"][0]
    return stream["width"], stream["height"], Fraction(stream["r_frame_rate"])


def pixels(video: Path, crop: str, seek: float | None = None) -> list[tuple[int, int, int]]:
    """Decode the cropped region of every frame (or one frame at ``seek``) as RGB triples."""
    args = ["ffmpeg", "-v", "error"]
    if seek is not None:
        args += ["-ss", str(seek)]
    args += ["-i", str(video)]
    if seek is not None:
        args += ["-frames:v", "1"]
    # Convert before cropping: a 1-pixel crop of subsampled yuv420p is rejected.
    args += ["-vf", f"format=rgb24,crop={crop}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    data = run(args).stdout
    return [tuple(data[i:i + 3]) for i in range(0, len(data) - 2, 3)]


def marker(rgb: tuple[int, int, int]) -> str | None:
    """Name the step-marker colour nearest to ``rgb``, or None if none is close."""
    name, ref = min(MARKERS.items(), key=lambda item: sum((a - b) ** 2 for a, b in zip(rgb, item[1])))
    return name if sum((a - b) ** 2 for a, b in zip(rgb, ref)) < 90 ** 2 else None


def find_status_line(video: Path, width: int) -> tuple[int, int]:
    """Return (top, bottom) pixel rows of the tmux marker line, searched from the bottom up."""
    column = pixels(video, f"1:ih:{width // 2}:0", seek=0.5)
    rows = [y for y, rgb in enumerate(column) if marker(rgb)]
    if not rows:
        sys.exit("no green or magenta step marker found in the recording")
    bottom = rows[-1]
    top = bottom
    while top - 1 in rows:
        top -= 1
    return top, bottom


def step_starts(video: Path, width: int, row: int, fps: Fraction) -> tuple[list[float], float]:
    """Return the start time of every step and the recording's length, in seconds.

    A step starts on the first frame whose marker colour differs from the
    previous step's. A flip that reverts within three frames is ignored as
    a decoding artefact.
    """
    names = [marker(rgb) for rgb in pixels(video, f"1:1:{width // 2}:{row}")]
    starts = [0.0]
    current = next((name for name in names if name), None)
    for index, name in enumerate(names):
        if name and name != current and all(n == name for n in names[index:index + 3]):
            starts.append(float(index / fps))
            current = name
    return starts, float(len(names) / fps)


def render_captions(captions: list[tuple[str, str]], width: int, height: int, folder: Path) -> list[Path]:
    """Render one caption bar per step to PNG with headless Chrome."""
    numbered = len(captions) - 2  # the first and last captions are not counted steps
    images = []
    for index, (tag, text) in enumerate(captions):
        step = index if 0 < index <= numbered else None
        count = f'<span class="count">{step} / {numbered}</span>' if step else ""
        page = folder / f"caption{index:02d}.html"
        page.write_text(CAPTION_HTML.format(
            width=width, height=height, count=count, tag=html.escape(tag), text=html.escape(text),
            progress=round(100 * index / (len(captions) - 1), 2),
        ), encoding="utf-8")
        image = folder / f"caption{index:02d}.png"
        run([
            CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
            "--force-device-scale-factor=1", f"--user-data-dir={folder / 'chrome'}",
            f"--window-size={width},{height}", f"--screenshot={image}", page.as_uri(),
        ])
        if probe(image)[:2] != (width, height):
            sys.exit(f"Chrome rendered {image.name} at {probe(image)[:2]}, expected {(width, height)}")
        images.append(image)
    return images


def compose(raw: Path, images: list[Path], starts: list[float], length: float,
            width: int, top: int, fps: Fraction, folder: Path) -> None:
    """Stack the cropped recording over the timed caption bars and encode dist/demo.mp4."""
    ends = starts[1:] + [length]
    listing = folder / "captions.txt"
    lines = []
    for image, start, end in zip(images, starts, ends):
        lines += [f"file '{image}'", f"duration {end - start:.4f}"]
    lines.append(f"file '{images[-1]}'")  # the concat demuxer needs the last file twice
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    graph = (
        f"[0:v]crop={width}:{top}:0:0,format=yuv444p[term];"
        f"[1:v]fps={fps},format=yuv444p[band];"
        f"[term][band]vstack=shortest=1,format=yuv420p[out]"
    )
    run([
        "ffmpeg", "-v", "error", "-y", "-i", str(raw), "-f", "concat", "-safe", "0", "-i", str(listing),
        "-filter_complex", graph, "-map", "[out]", "-r", str(fps), "-c:v", "libx264", "-preset", "slow",
        "-crf", "18", "-movflags", "+faststart", str(OUT),
    ])


def main() -> None:
    """Record (unless --no-record), then compose and check the final video."""
    parser = argparse.ArgumentParser(description="Render the system video to dist/demo.mp4.")
    parser.add_argument("--no-record", action="store_true", help="reuse dist/demo-raw.mp4")
    options = parser.parse_args()

    captions = read_captions(TAPE)
    if not options.no_record:
        print("recording with VHS (about 4 minutes)…", flush=True)
        run(["vhs", str(TAPE.relative_to(ROOT))], cwd=ROOT)

    width, _height, fps = probe(RAW)
    status_top, status_bottom = find_status_line(RAW, width)
    # Cut inside the blank tmux line above the marker: 6 pixels clear of the
    # marker, whose colour bleeds upward in the lossy recording, and an even
    # height for yuv420p.
    top = (status_top - 6) & ~1
    starts, length = step_starts(RAW, width, (status_top + status_bottom) // 2, fps)
    if len(starts) != len(captions):
        sys.exit(f"found {len(starts)} steps in the recording but {len(captions)} captions in the tape")

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        images = render_captions(captions, width, FINAL_HEIGHT - top, folder)
        compose(RAW, images, starts, length, width, top, fps, folder)

    out_width, out_height, _ = probe(OUT)
    print(f"wrote {OUT.relative_to(ROOT)}: {out_width}x{out_height}, {length:.1f} s, {len(captions)} captions")
    if length > LIMIT_SECONDS:
        sys.exit(f"too long: {length:.1f} s is over the brief's {LIMIT_SECONDS} s limit")


if __name__ == "__main__":
    main()
