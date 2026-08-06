from pathlib import Path

from rocketserializer.openrocket_runtime import _find_windows_jdk


def test_find_windows_jdk_in_program_files_microsoft(tmp_path):
    jdk_root = tmp_path / "Program Files" / "Microsoft" / "jdk-17.0.10.7-hotspot"
    (jdk_root / "bin").mkdir(parents=True)
    (jdk_root / "bin" / "java.exe").write_bytes(b"")

    found = _find_windows_jdk(
        17,
        search_roots=[tmp_path / "Program Files"],
    )

    assert found == jdk_root
