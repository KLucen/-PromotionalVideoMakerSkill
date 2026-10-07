"""Test source precision, evidence protection and the AAC cut invariants."""

from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest

import probe_source
import verify_encoded


class MediaTests(unittest.TestCase):
    def test_quantized_clock_is_not_nominal_fps(self):
        ticks, seconds = probe_source.frame_clock([{"pts": 0}, {"pts": 672}, {"pts": 1328}], "1/16000")
        self.assertEqual(ticks, [0, 672, 1328])
        self.assertEqual(list(map(Fraction, seconds)), [Fraction(0), Fraction(42, 1000), Fraction(83, 1000)])
        self.assertNotEqual(Fraction(seconds[1]), Fraction(1, 24))

    def test_missing_or_duplicate_pts_fails(self):
        for frames in ([], [{}], [{"pts": 0}, {"pts": 0}], [{"pts": 2}, {"pts": 1}]):
            with self.assertRaises(ValueError):
                probe_source.frame_clock(frames, "1/16000")

    def test_packet_endpoint_is_observed_without_guessing(self):
        self.assertEqual(probe_source.packet_boundary([{"pts": 0, "duration": 672}, {"pts": 672, "duration": 666}]), 1338)
        for packets in ([], [{"pts": 0}], [{"pts": 0, "duration": 0}]):
            with self.assertRaises(ValueError):
                probe_source.packet_boundary(packets)

    def test_reordered_packet_duration_does_not_define_final_exposure(self):
        video = {"start_pts": 0, "duration_ts": 2438666}
        ticks = [0, 2437328, 2438000]
        packets = [{"pts": 2438000, "duration": 656}, {"pts": 2437328, "duration": 666}]
        stream_end = probe_source.stream_boundary(video, ticks)
        self.assertEqual(stream_end - ticks[-1], 666)
        self.assertEqual(probe_source.packet_boundary(packets) - stream_end, -10)
        for bad in ({}, {"start_pts": 1, "duration_ts": 2438666},
                    {"start_pts": 0, "duration_ts": 2438000}):
            with self.assertRaises(ValueError):
                probe_source.stream_boundary(bad, ticks)

    def test_source_metadata_cannot_substitute_nominal_clock(self):
        stream = {"width": 1920, "height": 1080, "time_base": "1/16000", "duration_ts": 1338, "start_pts": 0}
        frames = [{"pts": 0}, {"pts": 672}]
        exact = [Fraction(0), Fraction(42, 1000)]
        self.assertTrue(verify_encoded.source_timing_matches(exact, frames, stream, stream))
        self.assertFalse(verify_encoded.source_timing_matches([Fraction(0), Fraction(1, 24)], frames, stream, stream))
        self.assertFalse(verify_encoded.source_timing_matches(exact, [{}], stream, stream))
        self.assertFalse(verify_encoded.source_timing_matches(exact, frames, stream, {**stream, "duration_ts": 1344}))

    def test_exact_presentation_end_is_independent_of_packet_duration(self):
        stream = {"time_base": "1/16000", "start_pts": 0, "duration_ts": 2438666}
        pts = [Fraction(0), Fraction(2438000, 16000)]
        boundary = Fraction(2438666, 16000)
        self.assertTrue(verify_encoded.presentation_end_matches(stream, pts, boundary))
        self.assertFalse(verify_encoded.presentation_end_matches(stream, pts, Fraction(2438656, 16000)))
        self.assertFalse(verify_encoded.presentation_end_matches(stream, [], boundary))
        self.assertFalse(verify_encoded.presentation_end_matches(stream, [boundary], boundary))
        self.assertFalse(verify_encoded.presentation_end_matches({}, pts, boundary))

    def test_reports_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "record.json"
            probe_source.write_metadata(path, {"original": True})
            with self.assertRaises(FileExistsError):
                probe_source.write_metadata(path, {"original": False})
            self.assertEqual(json.loads(path.read_text()), {"original": True})

    def test_nearest_audio_tick_is_unique(self):
        tick = Fraction(1, 44100)
        for origin in (Fraction(33833, 1000), Fraction(35833, 1000)):
            chosen = verify_encoded.quantized_audio_origin(origin, tick)
            self.assertLessEqual(abs(chosen - origin), tick / 2)
            self.assertGreater(abs(chosen + tick - origin), tick / 2)

    def test_extra_audio_sample_is_not_tolerated(self):
        tick = Fraction(1, 44100)
        source = {"pts": 1491968, "dts": 1491968, "duration": 1024}
        origin = verify_encoded.quantized_audio_origin(Fraction(33833, 1000), tick)
        shift = int(origin / tick)
        good = {"pts": source["pts"] - shift, "dts": source["dts"] - shift, "duration": 1024}
        self.assertTrue(verify_encoded.packet_timing_matches(good, source, tick, tick, origin))
        self.assertFalse(verify_encoded.packet_timing_matches({**good, "pts": good["pts"] + 1}, source, tick, tick, origin))

    def test_aac_payload_mapping_requires_unique_nonempty_match(self):
        a = {"data_hash": "SHA256:a", "size": "12"}
        b = {"data_hash": "SHA256:b", "size": "13"}
        self.assertEqual(verify_encoded.copied_packet_start([a, b], [b]), 1)
        for actual in ([], [{"data_hash": "SHA256:c", "size": "12"}]):
            with self.assertRaises(ValueError):
                verify_encoded.copied_packet_start([a, b], actual)
        with self.assertRaises(ValueError):
            verify_encoded.copied_packet_start([a, a], [a])


if __name__ == "__main__":
    unittest.main()
