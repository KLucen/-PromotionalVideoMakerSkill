"""Capture exact source timing without assuming CFR or overwriting evidence."""

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess


def probe(path, *options):
    result = subprocess.run(["ffprobe", "-v", "error", *options, "-of", "json", str(path)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode or result.stderr.strip():
        raise ValueError(f"FFprobe failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def frame_clock(frames, time_base):
    if not frames or not all("pts" in frame for frame in frames):
        raise ValueError("All decoded video frames need explicit PTS")
    tb = Fraction(time_base)
    if tb <= 0:
        raise ValueError("Video time base must be positive")
    ticks = [int(frame["pts"]) for frame in frames]
    if any(a >= b for a, b in zip(ticks, ticks[1:])):
        raise ValueError("Video presentation PTS must be strictly increasing")
    return ticks, [str(value * tb) for value in ticks]


def packet_boundary(packets):
    if not packets or any("pts" not in p or "duration" not in p for p in packets):
        raise ValueError("Explicit video packet PTS and duration are needed to observe packet endpoints")
    if any(int(p["duration"]) <= 0 for p in packets):
        raise ValueError("Video packet durations must be positive; do not fabricate packet timing")
    return max(int(p["pts"]) + int(p["duration"]) for p in packets)


def stream_boundary(video, ticks):
    if "duration_ts" not in video or "start_pts" not in video:
        raise ValueError("Video stream needs start_pts and duration_ts; use an appropriate specialist probe")
    start = int(video["start_pts"])
    duration = int(video["duration_ts"])
    if not ticks or ticks[0] != start or duration <= 0 or start + duration <= ticks[-1]:
        raise ValueError("Video stream timing does not cover all decoded presentation PTS")
    return start + duration


def capture(source):
    before = digest(source)
    info = probe(source, "-show_streams", "-show_format")
    videos = [s for s in info["streams"] if s["codec_type"] == "video"]
    if len(videos) != 1:
        raise ValueError("This helper needs exactly one video stream")
    video = videos[0]
    frames = probe(source, "-select_streams", "v:0", "-show_frames",
                   "-show_entries", "frame=pts,duration,pkt_duration")["frames"]
    ticks, seconds = frame_clock(frames, video["time_base"])
    packets = probe(source, "-select_streams", "v:0", "-show_packets",
                    "-show_entries", "packet=pts,duration")["packets"]
    packet_end = packet_boundary(packets)
    end = stream_boundary(video, ticks)
    # Reordered packet durations are not necessarily presentation exposures.
    timing_notes = []
    if packet_end != end:
        timing_notes.append("Packet PTS + duration differs from the declared stream end. "
                            "Preserve both observations; inspect reordered packets/edit lists "
                            "before changing the presentation timeline. The captured end uses "
                            "the explicit stream start_pts + duration_ts, not a guessed fps.")
    if digest(source) != before:
        raise ValueError("Source changed during capture")
    tb = Fraction(video["time_base"])
    return {"schema": "pv-source-exact-timing-v1", "source": str(source.resolve()), "sha256": before,
            "streams": info["streams"], "format": info["format"], "pts": seconds,
            "pts_ticks": ticks, "video_time_base": str(tb), "frames": len(frames),
            "video_start_pts_ticks": ticks[0], "video_end_pts_ticks": end,
            "video_end_boundary_basis": "stream.start_pts + stream.duration_ts",
            "packet_end_pts_ticks": packet_end,
            "packet_end_minus_stream_end_ticks": packet_end - end,
            "timing_notes": timing_notes,
            "last_exposure_ticks": end - ticks[-1], "last_exposure_seconds": str((end - ticks[-1]) * tb),
            "interval_convention": "0-based [start,end)",
            "uniform_pts_step": len(set(b - a for a, b in zip(ticks, ticks[1:]))) <= 1,
            "timing_is_exact_integer_pts": True, "artistic_review": "not_performed"}


def write_metadata(output, data):
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; use a new version instead of overwriting evidence")
    try:
        data = capture(args.source.resolve())
        write_metadata(args.output, data)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Source capture failed: {error}\n")
    print(json.dumps({"metadata": str(args.output.resolve()), "frames": data["frames"],
                      "time_base": data["video_time_base"], "uniform_pts_step": data["uniform_pts_step"],
                      "last_exposure_ticks": data["last_exposure_ticks"]}))


if __name__ == "__main__":
    main()
