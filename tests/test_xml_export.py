from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audio_conform_syncer.exports.timeline_model import build_timeline_project
from audio_conform_syncer.exports.xml_export import export_premiere_xml, export_resolve_xml
from audio_conform_syncer.models import AudioSummary, MatchCandidate, ReportSummary, SyncReport


class XmlExportTests(unittest.TestCase):
    def test_premiere_and_resolve_xml_files_include_synced_audio_clip(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_path = root / "boom.wav"
            video_path = root / "edit.mov"
            guide_path = root / "guide.wav"
            source_path.write_bytes(b"audio")
            video_path.write_bytes(b"video")
            guide_path.write_bytes(b"guide")

            report = _report(video_path=video_path, guide_path=guide_path, source_path=source_path)
            project = build_timeline_project(report, job_id="job-xml", include_waveforms=False)

            premiere_path = export_premiere_xml(project, root / "premiere.xml")
            resolve_path = export_resolve_xml(project, root / "resolve.xml")

            premiere_root = ET.parse(premiere_path).getroot()
            resolve_root = ET.parse(resolve_path).getroot()
            premiere_text = premiere_path.read_text(encoding="utf-8")
            resolve_text = resolve_path.read_text(encoding="utf-8")

        self.assertEqual(premiere_root.tag, "xmeml")
        self.assertEqual(resolve_root.tag, "xmeml")
        self.assertIn("Premiere", premiere_text)
        self.assertIn("Resolve", resolve_text)
        self.assertIn("boom.wav", premiere_text)
        self.assertGreaterEqual(len(premiere_root.findall(".//clipitem")), 3)


def _report(video_path: Path, guide_path: Path, source_path: Path) -> SyncReport:
    return SyncReport(
        tool_name="Audio Conform Syncer",
        author="@danreipogi",
        created_at_utc="2026-05-21T00:00:00+00:00",
        reference_media=str(video_path.resolve()),
        audio_directory=str(source_path.parent.resolve()),
        reference_audio=AudioSummary(str(guide_path.resolve()), 16000, 160000, 10.0),
        source_audio=[AudioSummary(str(source_path.resolve()), 16000, 80000, 5.0)],
        settings={"sample_rate": 16000},
        matches=[
            MatchCandidate(
                source_path=str(source_path.resolve()),
                reference_start_seconds=1.0,
                reference_end_seconds=3.0,
                source_start_seconds=0.25,
                source_end_seconds=2.25,
                score=0.88,
                score_margin=0.2,
                confidence="medium",
            )
        ],
        unmatched_regions=[],
        summary=ReportSummary(
            source_count=1,
            match_count=1,
            unmatched_region_count=0,
            reference_duration_seconds=10.0,
            matched_duration_seconds=2.0,
            unmatched_duration_seconds=8.0,
            coverage_percent=20.0,
            average_match_score=0.88,
            highest_match_score=0.88,
            ambiguous_match_count=0,
        ),
    )


if __name__ == "__main__":
    unittest.main()
