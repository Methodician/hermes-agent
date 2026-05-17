import json
from pathlib import Path


def test_convert_to_opus_uses_distinct_output_for_ogg_input(monkeypatch, tmp_path):
    from tools import tts_tool

    source = tmp_path / "clip.ogg"
    source.write_bytes(b"mp3 bytes despite ogg suffix")
    observed = {}

    def fake_run(cmd, capture_output, timeout):
        observed["cmd"] = cmd
        output_path = Path(cmd[-2])
        output_path.write_bytes(b"opus bytes")

        class Result:
            returncode = 0
            stderr = b""

        return Result()

    monkeypatch.setattr(tts_tool, "_has_ffmpeg", lambda: True)
    monkeypatch.setattr(tts_tool.subprocess, "run", fake_run)

    converted = tts_tool._convert_to_opus(str(source))

    assert converted == str(tmp_path / "clip.voice.ogg")
    assert observed["cmd"][2] == str(source)
    assert observed["cmd"][-2] == converted
    assert observed["cmd"][2] != observed["cmd"][-2]


def test_edge_output_path_ending_ogg_is_converted_to_voice_compatible_file(monkeypatch, tmp_path):
    from tools import tts_tool

    async def fake_edge_tts(text, output_path, tts_config):
        Path(output_path).write_bytes(b"mp3 bytes despite ogg suffix")
        return output_path

    def fake_convert(path):
        assert path.endswith("clip.ogg")
        converted = tmp_path / "clip.voice.ogg"
        converted.write_bytes(b"opus bytes")
        return str(converted)

    monkeypatch.setattr(tts_tool, "_import_edge_tts", lambda: object())
    monkeypatch.setattr(tts_tool, "_generate_edge_tts", fake_edge_tts)
    monkeypatch.setattr(tts_tool, "_convert_to_opus", fake_convert)

    result = json.loads(
        tts_tool.text_to_speech_tool("hello", output_path=str(tmp_path / "clip.ogg"))
    )

    assert result["success"] is True
    assert result["file_path"].endswith("clip.voice.ogg")
    assert result["voice_compatible"] is True
    assert result["media_tag"].startswith("[[audio_as_voice]]\nMEDIA:")
