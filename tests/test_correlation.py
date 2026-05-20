from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audio_conform_syncer.core.audio_features import _fft_correlate_valid, best_alignment


class CorrelationTests(unittest.TestCase):
    def test_best_alignment_finds_query_offset(self) -> None:
        sample_rate = 100
        time = np.linspace(0.0, 1.0, sample_rate, endpoint=False)
        query = np.sin(2 * np.pi * 7 * time).astype(np.float32)
        target = np.zeros(500, dtype=np.float32)
        target[230 : 230 + len(query)] = query

        result = best_alignment(query, target)

        self.assertEqual(result.offset_samples, 230)
        self.assertGreater(result.score, 0.99)

    def test_best_alignment_returns_zero_for_silent_query(self) -> None:
        result = best_alignment(np.zeros(20, dtype=np.float32), np.ones(100, dtype=np.float32))

        self.assertEqual(result.offset_samples, 0)
        self.assertEqual(result.score, 0.0)

    def test_fft_correlation_matches_numpy_valid_correlation(self) -> None:
        rng = np.random.default_rng(123)
        target = rng.normal(size=64)
        query = rng.normal(size=11)

        expected = np.correlate(target, query, mode="valid")
        actual = _fft_correlate_valid(target, query)

        np.testing.assert_allclose(actual, expected, atol=1e-10)


if __name__ == "__main__":
    unittest.main()
