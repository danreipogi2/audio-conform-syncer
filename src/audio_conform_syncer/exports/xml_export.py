from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from audio_conform_syncer.exports.timeline_model import TimelineClip, TimelineProject, TimelineTrack

DEFAULT_FRAME_RATE = 30


def export_premiere_xml(
    project: TimelineProject,
    output_path: Path,
    frame_rate: int = DEFAULT_FRAME_RATE,
) -> Path:
    return _write_xmeml(
        project=project,
        output_path=output_path,
        frame_rate=frame_rate,
        sequence_name=f"{project.reference_video_name} - Premiere Sync",
        application_name="Audio Conform Syncer Premiere XML",
    )


def export_resolve_xml(
    project: TimelineProject,
    output_path: Path,
    frame_rate: int = DEFAULT_FRAME_RATE,
) -> Path:
    return _write_xmeml(
        project=project,
        output_path=output_path,
        frame_rate=frame_rate,
        sequence_name=f"{project.reference_video_name} - Resolve Sync",
        application_name="Audio Conform Syncer Resolve XML",
    )


def _write_xmeml(
    project: TimelineProject,
    output_path: Path,
    frame_rate: int,
    sequence_name: str,
    application_name: str,
) -> Path:
    if frame_rate <= 0:
        raise ValueError("frame_rate must be positive")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("xmeml", {"version": "5"})
    sequence = ET.SubElement(root, "sequence", {"id": _xml_id(sequence_name)})
    ET.SubElement(sequence, "name").text = sequence_name
    ET.SubElement(sequence, "duration").text = str(_seconds_to_frames(project.duration_seconds, frame_rate))
    _append_rate(sequence, frame_rate)
    ET.SubElement(sequence, "appname").text = application_name

    media = ET.SubElement(sequence, "media")
    video = ET.SubElement(media, "video")
    video_track = ET.SubElement(video, "track")
    for clip in project.video_track.clips:
        _append_clipitem(video_track, clip, project.video_track, frame_rate, media_type="video")

    audio = ET.SubElement(media, "audio")
    guide_track = ET.SubElement(audio, "track")
    guide_clip = TimelineClip(
        id="guide-audio-clip",
        source_path=project.guide_audio_track.source_path,
        source_name=project.guide_audio_track.source_name,
        timeline_in_seconds=0.0,
        timeline_out_seconds=project.duration_seconds,
        source_in_seconds=0.0,
        source_out_seconds=project.duration_seconds,
        confidence="reference",
        score=1.0,
        score_margin=1.0,
        track_index=1,
    )
    _append_clipitem(guide_track, guide_clip, project.guide_audio_track, frame_rate, media_type="audio")

    for source_track in project.audio_tracks:
        track_element = ET.SubElement(audio, "track")
        ET.SubElement(track_element, "enabled").text = "TRUE"
        ET.SubElement(track_element, "locked").text = "FALSE"
        for clip in source_track.clips:
            _append_clipitem(track_element, clip, source_track, frame_rate, media_type="audio")

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    return output_path


def _append_clipitem(
    parent: ET.Element,
    clip: TimelineClip,
    track: TimelineTrack,
    frame_rate: int,
    media_type: str,
) -> None:
    clip_id = _xml_id(f"{media_type}-{track.id}-{clip.id}")
    clip_item = ET.SubElement(parent, "clipitem", {"id": clip_id})
    ET.SubElement(clip_item, "name").text = clip.source_name
    ET.SubElement(clip_item, "enabled").text = "TRUE"
    ET.SubElement(clip_item, "duration").text = str(
        _seconds_to_frames(max(track.duration_seconds, clip.source_out_seconds), frame_rate)
    )
    ET.SubElement(clip_item, "start").text = str(_seconds_to_frames(clip.timeline_in_seconds, frame_rate))
    ET.SubElement(clip_item, "end").text = str(_seconds_to_frames(clip.timeline_out_seconds, frame_rate))
    ET.SubElement(clip_item, "in").text = str(_seconds_to_frames(clip.source_in_seconds, frame_rate))
    ET.SubElement(clip_item, "out").text = str(_seconds_to_frames(clip.source_out_seconds, frame_rate))
    _append_file(clip_item, clip, track, frame_rate)


def _append_file(
    clip_item: ET.Element,
    clip: TimelineClip,
    track: TimelineTrack,
    frame_rate: int,
) -> None:
    file_element = ET.SubElement(clip_item, "file", {"id": _xml_id(f"file-{track.id}")})
    ET.SubElement(file_element, "name").text = track.source_name or clip.source_name
    ET.SubElement(file_element, "pathurl").text = _path_url(Path(clip.source_path))
    _append_rate(file_element, frame_rate)
    ET.SubElement(file_element, "duration").text = str(_seconds_to_frames(track.duration_seconds, frame_rate))


def _append_rate(parent: ET.Element, frame_rate: int) -> None:
    rate = ET.SubElement(parent, "rate")
    ET.SubElement(rate, "timebase").text = str(frame_rate)
    ET.SubElement(rate, "ntsc").text = "FALSE"


def _seconds_to_frames(seconds: float, frame_rate: int) -> int:
    return max(0, int(round(seconds * frame_rate)))


def _path_url(path: Path) -> str:
    try:
        return path.resolve().as_uri()
    except ValueError:
        return path.as_posix()


def _xml_id(value: str) -> str:
    cleaned = "".join(character if character.isalnum() else "-" for character in value)
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned[:120] or "item"
