"""Verify strict-source timing and copied AAC; never grant artistic acceptance.

Adapted from the Klee PV engineering verifier. Supports zero-origin sources
with exactly one video and one AAC stream, including source-exact clips.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess

def run(command):
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe(path, *options):
    result = run(["ffprobe", "-v", "error", *options, "-of", "json", str(path)])
    if result.returncode or result.stderr.strip():
        raise ValueError(f"ffprobe failed for {path}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def packet_time(packet, key, time_base):
    return int(packet[key]) * time_base


def quantized_audio_origin(origin, time_base):
    """AAC timestamps can only shift by whole ticks, unlike millisecond video PTS."""
    if origin < 0 or time_base <= 0:
        raise ValueError("Audio origin and time base must be nonnegative/positive")
    ticks = origin / time_base
    nearest = (2 * ticks.numerator + ticks.denominator) // (2 * ticks.denominator)
    return nearest * time_base


def packet_timing_matches(actual, source, actual_time_base, source_time_base, audio_origin):
    return all(packet_time(actual, key, actual_time_base) ==
               packet_time(source, key, source_time_base) - (audio_origin if key != "duration" else 0)
               for key in ("pts", "dts", "duration"))


def sequence_mismatches(actual, expected):
    return [{"index": i, "actual": str(a), "expected": str(b)}
            for i, (a, b) in enumerate(zip(actual, expected)) if a != b]


def copied_packet_start(original, actual):
    if not actual:
        raise ValueError("AAC interval contains no packets")
    signature = lambda p: (p.get("data_hash"), p.get("size"))
    wanted = [signature(p) for p in actual]
    matches = [i for i in range(len(original)-len(actual)+1)
               if signature(original[i]) == wanted[0]
               and [signature(p) for p in original[i:i+len(actual)]] == wanted]
    if len(matches) != 1:
        raise ValueError(f"AAC interval needs one unique source-payload match, found {len(matches)}")
    return matches[0]


def source_timing_matches(expected_pts, frames, actual_video, metadata_video):
    if not frames or not all("pts" in f for f in frames):
        return False
    actual = [int(f["pts"]) * Fraction(actual_video["time_base"]) for f in frames]
    return (actual == expected_pts and all(a < b for a, b in zip(actual, actual[1:]))
            and all(actual_video.get(key) == metadata_video.get(key)
                    for key in ("width", "height", "time_base", "duration_ts", "start_pts")))


def presentation_end_matches(stream, pts, expected_boundary):
    if not pts or "start_pts" not in stream or "duration_ts" not in stream:
        return False
    start, duration = int(stream["start_pts"]), int(stream["duration_ts"])
    end = (start + duration) * Fraction(stream["time_base"])
    return start == 0 and duration > 0 and end == expected_boundary and pts[-1] < end


def verify(video, metadata_path, start, end, side_by_side, source_override=None):
    metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    source = Path(source_override or metadata["source"])
    if not source.is_absolute():
        source = (Path.cwd() if source_override else metadata_path.parent) / source
    source_pts = [Fraction(str(value)) for value in metadata["pts"]]
    if not 0 <= start < end <= len(source_pts):
        raise ValueError("Expected interval must be within source frames; end is exclusive")
    expected_pts = [value - source_pts[start] for value in source_pts[start:end]]
    source_video = next(s for s in metadata["streams"] if s["codec_type"] == "video")
    actual_source = probe(source, "-show_streams")["streams"]
    source_videos = [s for s in actual_source if s["codec_type"] == "video"]
    source_audios = [s for s in actual_source if s["codec_type"] == "audio"]
    if (len(source_videos) != 1 or len(source_audios) != 1
            or source_audios[0].get("codec_name") != "aac"
            or source_pts[0] != 0 or int(source_videos[0].get("start_pts", -1)) != 0):
        raise ValueError("Unsupported source: this verifier needs zero-origin video and exactly one video/one AAC stream")
    source_frames = probe(source, "-select_streams", "v:0", "-show_frames",
                          "-show_entries", "frame=pts")["frames"]
    if not source_timing_matches(source_pts, source_frames, source_videos[0], source_video):
        raise ValueError("Metadata does not match the actual decoded source timing; do not relax the check")
    source_time_base = Fraction(source_video["time_base"])
    if end < len(source_pts):
        boundary = source_pts[end] - source_pts[start]
    else:
        boundary = int(source_video["duration_ts"]) * source_time_base - source_pts[start]
    video_hash = sha256(video)
    report = {"video": str(video.resolve()), "video_sha256": video_hash, "source": str(source.resolve()),
              "metadata": str(metadata_path.resolve()), "source_interval": [start, end],
              "expected_frames": end - start, "expected_boundary_seconds": float(boundary),
              "checks": {}, "artistic_review": "not_performed_by_this_technical_verifier",
              "limitations": ["AAC packet copying retains whole packets. The final audio packet may "
                              "extend beyond the exact video boundary by less than one AAC packet.",
                              "A nonzero video cut origin may fall between AAC timestamp ticks. "
                              "Only its deterministic nearest-tick shift is permitted; the residual "
                              "is reported, while video PTS remain source-exact.",
                              "The presentation end uses explicit video stream timing. Packet "
                              "PTS + duration is recorded separately because reordered packet "
                              "durations need not equal presentation exposures.",
                              "Decode integrity does not verify drawing quality, occlusion, captions, "
                              "shot identity, or visual continuity."]}
    checks = report["checks"]
    checks["source_identity"] = sha256(source) == metadata["sha256"]
    streams = probe(video, "-show_streams", "-show_format", "-show_data_hash", "sha256")
    video_streams = [s for s in streams["streams"] if s["codec_type"] == "video"]
    audio_streams = [s for s in streams["streams"] if s["codec_type"] == "audio"]
    checks["one_video_one_audio_stream"] = len(video_streams) == len(audio_streams) == 1
    if not checks["one_video_one_audio_stream"]:
        report["technical_pass"] = False
        return report
    vstream, astream = video_streams[0], audio_streams[0]
    vtb, atb = Fraction(vstream["time_base"]), Fraction(astream["time_base"])
    dimensions = (int(source_video["width"]) * (2 if side_by_side else 1), int(source_video["height"]))
    frames = probe(video, "-select_streams", "v:0", "-show_frames", "-show_entries",
                   "frame=pts,best_effort_timestamp,width,height")["frames"]
    checks["decoded_frame_count"] = len(frames) == end - start
    checks["all_frame_dimensions"] = all((f["width"], f["height"]) == dimensions for f in frames)
    checks["explicit_video_pts"] = all("pts" in f for f in frames)
    actual_pts = [int(f["pts"]) * vtb for f in frames if "pts" in f]
    pts_errors = sequence_mismatches(actual_pts, expected_pts)
    checks["strict_source_frame_pts"] = len(actual_pts) == len(expected_pts) and not pts_errors
    checks["strictly_increasing_pts"] = all(a < b for a, b in zip(actual_pts, actual_pts[1:]))
    report["video_timing"] = {"time_base": str(vtb), "decoded_frames": len(frames),
                              "dimensions": list(dimensions), "pts_mismatches": pts_errors[:20],
                              "pts_mismatch_count": len(pts_errors)}
    packets = probe(video, "-select_streams", "v:0", "-show_packets", "-show_entries",
                    "packet=pts,duration")["packets"]
    packet_ends = [packet_time(p, "pts", vtb) + packet_time(p, "duration", vtb)
                   for p in packets if "pts" in p and "duration" in p]
    packet_boundary = max(packet_ends) if packet_ends else None
    actual_boundary = ((int(vstream["start_pts"]) + int(vstream["duration_ts"])) * vtb
                       if "start_pts" in vstream and "duration_ts" in vstream else None)
    checks["strict_video_end_boundary"] = presentation_end_matches(vstream, actual_pts, boundary)
    report["video_timing"].update({"stream_end_seconds": float(actual_boundary) if actual_boundary is not None else None,
                                   "end_boundary_basis": "stream.start_pts + stream.duration_ts",
                                   "packet_end_seconds": float(packet_boundary) if packet_boundary is not None else None,
                                   "packet_minus_stream_end_seconds": float(packet_boundary - actual_boundary)
                                   if packet_boundary is not None and actual_boundary is not None else None,
                                   "end_difference_seconds": float(actual_boundary - boundary)
                                   if actual_boundary is not None else None})
    source_audio = probe(source, "-select_streams", "a:0", "-show_streams", "-show_data_hash", "sha256")["streams"][0]
    satb = Fraction(source_audio["time_base"])
    fields = ("codec_name", "sample_rate", "channels", "channel_layout", "extradata_hash")
    checks["aac_stream_configuration"] = (astream["codec_name"] == "aac" and
                                            all(astream.get(key) == source_audio.get(key) for key in fields))
    options = ("-select_streams", "a:0", "-show_packets", "-show_data_hash", "sha256",
               "-show_entries", "packet=pts,dts,duration,size,data_hash,side_data_list")
    original_audio = probe(source, *options)["packets"]
    actual_audio = probe(video, *options)["packets"]
    origin = source_pts[start]
    audio_origin = quantized_audio_origin(origin, atb)
    first_packet = copied_packet_start(original_audio, actual_audio) if start else 0
    expected_audio = [p for p in original_audio[first_packet:]
                      if packet_time(p, "pts", satb) < origin+boundary]
    payload_errors, timing_errors, side_data_errors = [], [], []
    for i, (a, b) in enumerate(zip(actual_audio, expected_audio)):
        if not a.get("data_hash") or (a["data_hash"], a["size"]) != (b["data_hash"], b["size"]):
            payload_errors.append(i)
        if not packet_timing_matches(a, b, atb, satb, audio_origin):
            timing_errors.append(i)
        expected_side_data = b.get("side_data_list", [])
        if start and i == 0:
            skip_samples = -packet_time(a, "pts", atb)*int(astream["sample_rate"])
            if skip_samples.denominator != 1:
                raise ValueError("AAC cut origin is not an exact sample boundary")
            skip = int(skip_samples)
            if skip < 0:
                side_data_errors.append(i)
            expected_side_data = ([{"side_data_type": "Skip Samples", "skip_samples": skip,
                                   "discard_padding": 0, "skip_reason": 0, "discard_reason": 0}]
                                  if skip > 0 else [])
        if a.get("side_data_list", []) != expected_side_data:
            side_data_errors.append(i)
    checks["aac_interval_packet_count"] = len(actual_audio) == len(expected_audio) and bool(actual_audio)
    checks["aac_packet_payload_hashes"] = checks["aac_interval_packet_count"] and not payload_errors
    checks["aac_packet_timestamps_and_durations"] = checks["aac_interval_packet_count"] and not timing_errors
    checks["aac_origin_nearest_tick_only"] = abs(audio_origin - origin) <= atb / 2
    checks["aac_priming_side_data"] = checks["aac_interval_packet_count"] and not side_data_errors
    audio_end = (packet_time(actual_audio[-1], "pts", atb) + packet_time(actual_audio[-1], "duration", atb)) if actual_audio else None
    audio_last_start = packet_time(actual_audio[-1], "pts", atb) if actual_audio else None
    checks["audio_covers_boundary_without_extra_packet"] = (audio_end is not None and audio_last_start < boundary <= audio_end)
    report["audio_copy"] = {"actual_packets": len(actual_audio), "expected_packets": len(expected_audio),
                             "first_source_packet_index": first_packet,
                             "preroll_skip_samples": -int(actual_audio[0]["pts"]) if actual_audio else None,
                             "time_base": str(atb), "payload_mismatch_indices": payload_errors[:20],
                             "source_video_origin_seconds": float(origin),
                             "audio_origin_seconds": float(audio_origin),
                             "audio_origin_quantization_ticks": str((audio_origin-origin)/atb),
                             "audio_origin_quantization_seconds": float(audio_origin-origin),
                             "timing_mismatch_indices": timing_errors[:20], "side_data_mismatch_indices": side_data_errors[:20],
                             "packet_end_seconds": float(audio_end) if audio_end is not None else None,
                             "whole_packet_tail_seconds": float(audio_end - boundary) if audio_end is not None else None,
                             "sample_rate": astream["sample_rate"], "channels": astream["channels"]}
    decoded = run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-err_detect", "explode", "-i", str(video),
                   "-map", "0:v:0", "-map", "0:a:0", "-fps_mode", "passthrough", "-progress", "pipe:1",
                   "-nostats", "-f", "null", "-"])
    progress = [line.split("=", 1)[1].strip() for line in decoded.stdout.splitlines() if line.startswith("frame=")]
    decode_count = int(progress[-1]) if progress else None
    checks["full_video_audio_decode"] = decoded.returncode == 0 and not decoded.stderr.strip() and decode_count == end - start
    report["full_decode"] = {"exit_code": decoded.returncode, "frames": decode_count, "errors": decoded.stderr.strip()}
    checks["preview_unchanged_during_verification"] = sha256(video) == video_hash
    report["container_duration_seconds"] = float(streams["format"]["duration"])
    report["technical_pass"] = all(checks.values())
    return report


def self_test():
    assert not sequence_mismatches([Fraction(0), Fraction(42, 1000)], [Fraction(0), Fraction(42, 1000)])
    assert sequence_mismatches([Fraction(0), Fraction(1, 24)], [Fraction(0), Fraction(42, 1000)])
    assert Fraction(77995, 16000) != Fraction(4875, 1000)
    assert packet_time({"pts": 1024}, "pts", Fraction(1, 44100)) == Fraction(256, 11025)
    assert packet_time({"pts": 672}, "pts", Fraction(1, 16000)) == Fraction(42, 1000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, nargs="?")
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--source", type=Path, help="Relocated source with the same recorded SHA-256")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int)
    parser.add_argument("--side-by-side", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print("Verification self-test passed")
        if args.video is None:
            return
    if args.video is None or args.metadata is None:
        parser.error("video and --metadata are required")
    output = args.report or args.video.parent / f"{args.video.stem}-technical-verification.json"
    if output.exists():
        parser.error("Report already exists; select a new path instead of overwriting evidence")
    try:
        end = args.end if args.end is not None else len(json.loads(args.metadata.read_text(encoding="utf-8-sig"))["pts"])
        report = verify(args.video, args.metadata, args.start, end, args.side_by_side, args.source)
    except (ValueError, KeyError, OSError) as error:
        report = {"video": str(args.video.resolve()), "technical_pass": False, "fatal_error": str(error),
                  "artistic_review": "not_performed_by_this_technical_verifier"}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({"report": str(output.resolve()), "technical_pass": report["technical_pass"],
                      "failed_checks": [name for name, passed in report.get("checks", {}).items() if not passed],
                      "fatal_error": report.get("fatal_error")}))
    raise SystemExit(0 if report["technical_pass"] else 1)


if __name__ == "__main__":
    main()
