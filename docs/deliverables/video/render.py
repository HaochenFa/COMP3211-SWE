"""Render the system video (brief item 3d) to dist/demo.mp4.

Four tools, one command, run from the repository root:

    python3 docs/deliverables/video/render.py            # record, then compose
    python3 docs/deliverables/video/render.py --no-record  # recompose only
    python3 docs/deliverables/video/render.py --no-record --voice am_fenrir
    python3 docs/deliverables/video/render.py --no-record --engine say

1. VHS plays demo.tape against the real curses UI and writes
   dist/demo-raw.mp4. The tmux status line in that recording is a step
   marker that flips between green and magenta at the start of each step.
2. Headless Google Chrome renders one caption bar per ``# caption:`` line
   in the tape, as a PNG. This ffmpeg build has no text filters, so text is
   drawn by the browser instead.
3. A text-to-speech engine speaks each ``# narration:`` line, and the
   clips are laid into one voiceover track, each starting where its step
   starts. A clip that would run into the next step stops the render with
   the step named, so the wording, not the recording, is what gets
   shortened. The default engine is Kokoro, an open neural voice model
   (hexgrad/Kokoro-82M), run as an outside command through ``uv`` like
   ffmpeg; ``--engine say`` uses the older, more robotic macOS voices.
4. ffmpeg crops the marker line off the recording, stacks the caption bar
   underneath, switches captions at the marker flips, adds the voiceover,
   and writes dist/demo.mp4 at 1920x1080.

Needs ``brew install vhs`` (which brings ttyd and ffmpeg), Google Chrome,
and ``brew install uv`` for Kokoro. The first Kokoro run downloads its
Python packages into uv's cache and the model (about 330 MB) from Hugging
Face; later runs work offline. Standard library only; this script is
tooling, not part of the PIM.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import tempfile
import wave
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
NARRATION_LINE = re.compile(r"^# narration: (.+)$")
VOICES = {"kokoro": "am_eric", "say": "Samantha"}  # default voice per engine
# Kokoro 0.9.4 with its dependencies as released by mid-2025: newer
# huggingface_hub and torchvision releases break it. A uv-managed Python
# keeps packages from another Python install (such as Anaconda) out.
KOKORO = [
    "uv", "run", "--quiet", "--no-project", "--managed-python", "--python", "3.12",
    "--exclude-newer", "2025-06-01", "--with", "kokoro==0.9.4", "--with", "pip",
    "python", "-m", "kokoro",
]
SAMPLE_RATE = 24000  # Kokoro's native rate; say is asked for the same
NARRATION_GAP = 0.4  # seconds of quiet a clip must leave before the next step

CAPTION_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><style>
html, body {{ margin: 0; width: {width}px; height: {height}px; overflow: hidden; background: #121316; }}
.band {{
  box-sizing: border-box; height: 100%; display: flex; align-items: center; gap: 18px;
  padding: 0 24px; border-top: 1px solid #3f3f46; color: #e7e5e4;
  font-family: -apple-system, "SF Pro Text", "Helvetica Neue", Helvetica, sans-serif;
}}
.count {{ flex: none; min-width: 52px; font: 18px Menlo, monospace; color: #78716c; }}
.tag {{
  flex: none; padding: 3px 10px; border-radius: 6px; background: #fde68a; color: #1c1917;
  font-size: 18px; font-weight: 600; white-space: nowrap;
}}
.text {{ font-size: 27px; font-weight: 500; line-height: 1.25; }}
.progress {{ position: fixed; left: 0; bottom: 0; height: 3px; width: {progress}%; background: #fde68a; }}
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


def read_narration(tape: Path) -> list[str]:
    """Return the text of every ``# narration: text`` line, in order."""
    return [
        match.group(1).strip()
        for match in map(NARRATION_LINE.match, tape.read_text(encoding="utf-8").splitlines())
        if match
    ]


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
        count = f'<span class="count">{step}/{numbered}</span>' if step else ""
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


def speak(engine: str, voice: str, text: str, clip: Path) -> None:
    """Write ``text`` spoken by ``voice`` to ``clip`` as 16-bit mono WAV at SAMPLE_RATE."""
    if engine == "kokoro":
        run([*KOKORO, "--voice", voice, "--text", text, "--output-file", str(clip)], cwd=clip.parent)
    else:
        run(["say", "-v", voice, f"--data-format=LEI16@{SAMPLE_RATE}", "-o", str(clip), text])


def narrate(lines: list[str], tags: list[str], starts: list[float], length: float,
            engine: str, voice: str, folder: Path) -> Path:
    """Speak each step's narration and lay the clips into one mono WAV of ``length`` seconds.

    Each clip starts at its step's start. Exits naming the step if a clip
    would leave less than NARRATION_GAP before the next step (or the end).
    """
    ends = starts[1:] + [length]
    track = bytearray(2 * round(length * SAMPLE_RATE))  # 16-bit silence
    for index, (text, tag, start, end) in enumerate(zip(lines, tags, starts, ends)):
        print(f"narration {index + 1}/{len(lines)}…", flush=True)
        clip = folder / f"voice{index:02d}.wav"
        speak(engine, voice, text, clip)
        with wave.open(str(clip)) as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, SAMPLE_RATE):
                sys.exit(f"say wrote {clip.name} in an unexpected format")
            samples = audio.readframes(audio.getnframes())
        spoken = len(samples) / 2 / SAMPLE_RATE
        if spoken > end - start - NARRATION_GAP:
            sys.exit(
                f"narration {index} ({tag}) takes {spoken:.1f} s but its step is "
                f"{end - start:.1f} s; shorten it to fit in {end - start - NARRATION_GAP:.1f} s"
            )
        offset = 2 * round(start * SAMPLE_RATE)
        track[offset:offset + len(samples)] = samples
    path = folder / "voice.wav"
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(bytes(track))
    return path


def compose(raw: Path, images: list[Path], starts: list[float], length: float,
            width: int, top: int, fps: Fraction, folder: Path, voice: Path | None) -> None:
    """Stack the cropped recording over the timed caption bars, add the voiceover, and encode."""
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
    inputs = ["-i", str(raw), "-f", "concat", "-safe", "0", "-i", str(listing)]
    maps = ["-map", "[out]"]
    if voice:
        # say speaks quietly; loudnorm brings it to a normal speech level.
        graph += ";[2:a]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[voice]"
        inputs += ["-i", str(voice)]
        maps += ["-map", "[voice]", "-c:a", "aac", "-b:a", "192k"]
    run([
        "ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, *maps,
        "-r", str(fps), "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-movflags", "+faststart", str(OUT),
    ])


def main() -> None:
    """Record (unless --no-record), then compose and check the final video."""
    parser = argparse.ArgumentParser(description="Render the system video to dist/demo.mp4.")
    parser.add_argument("--no-record", action="store_true", help="reuse dist/demo-raw.mp4")
    parser.add_argument("--engine", choices=sorted(VOICES), default="kokoro", help="text-to-speech engine")
    parser.add_argument("--voice", help=f"voice name (default {VOICES['kokoro']} for kokoro, "
                                        f"{VOICES['say']} for say)")
    parser.add_argument("--no-voice", action="store_true", help="leave out the voiceover")
    options = parser.parse_args()
    voice_name = options.voice or VOICES[options.engine]

    captions = read_captions(TAPE)
    narration = read_narration(TAPE)
    # Checked before recording, so a mismatch does not cost a 4-minute take.
    if not options.no_voice and len(narration) != len(captions):
        sys.exit(f"{len(captions)} captions but {len(narration)} narration lines in the tape")
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
        voice = None
        if not options.no_voice:
            tags = [tag for tag, _text in captions]
            voice = narrate(narration, tags, starts, length, options.engine, voice_name, folder)
        images = render_captions(captions, width, FINAL_HEIGHT - top, folder)
        compose(RAW, images, starts, length, width, top, fps, folder, voice)

    out_width, out_height, _ = probe(OUT)
    spoken = "no voiceover" if options.no_voice else f"voiceover by {options.engine} {voice_name}"
    print(f"wrote {OUT.relative_to(ROOT)}: {out_width}x{out_height}, {length:.1f} s, "
          f"{len(captions)} captions, {spoken}")
    if length > LIMIT_SECONDS:
        sys.exit(f"too long: {length:.1f} s is over the brief's {LIMIT_SECONDS} s limit")


if __name__ == "__main__":
    main()
