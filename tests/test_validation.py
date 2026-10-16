import subprocess

from app.validation import validate_reel
from app.video_assembler import aac_args, mp4_args, x264_args


def _clip(path, size="1080x1920", rate=30, seconds=4, reels_settings=True):
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "lavfi", "-i", f"testsrc2=size={size}:rate={rate}:duration={seconds}",
           "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={seconds}"]
    cmd += [*x264_args(), *aac_args(), *mp4_args()] if reels_settings else ["-c:v", "libx264", "-c:a", "aac"]
    subprocess.run(cmd + ["-shortest", str(path)], check=True)
    return path


def _by_name(report):
    return {c["name"]: c for c in report["checks"]}


def test_reel_encoded_with_project_settings_passes_hard_checks(tmp_path):
    report = validate_reel(_clip(tmp_path / "good.mp4"))
    assert report["passed"], [c for c in report["checks"] if not c["passed"] and c["severity"] == "hard"]
    checks = _by_name(report)
    assert checks["closed_gop"]["value"] == "open_gop=0"
    assert checks["moov_before_mdat"]["passed"] and checks["no_edit_lists"]["passed"]
    assert "duration_target" in report["warnings"]  # 4 s is outside the 25-30 s target


def test_wrong_format_is_blocked(tmp_path):
    report = validate_reel(_clip(tmp_path / "bad.mp4", size="640x360", rate=15, reels_settings=False))
    checks = _by_name(report)
    assert not report["passed"]
    assert not checks["frame_rate"]["passed"]
    assert not checks["resolution"]["passed"]
    assert not checks["moov_before_mdat"]["passed"]


def test_missing_file_fails(tmp_path):
    assert not validate_reel(tmp_path / "missing.mp4")["passed"]
