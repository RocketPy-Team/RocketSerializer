import os
from types import SimpleNamespace

from rocketserializer.getDefaultJVMPath import WindowsJVMFinder


def test_windows_finder_uses_java_on_path_when_valid(tmp_path, monkeypatch):
    java_home = tmp_path / "Java" / "jdk-17"
    java_bin_dir = java_home / "bin"
    java_bin_dir.mkdir(parents=True)
    java_exe = java_bin_dir / "java.exe"
    java_exe.write_bytes(b"")

    jvm_dir = java_bin_dir / "server"
    jvm_dir.mkdir(parents=True)
    jvm_path = jvm_dir / "jvm.dll"
    jvm_path.write_bytes(b"MZ\x00")

    monkeypatch.setenv(
        "PATH",
        f"{java_bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
    )
    monkeypatch.setattr(
        "rocketserializer.getDefaultJVMPath.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=f"java.home = {java_home}",
            stderr="",
        ),
    )
    monkeypatch.setattr(
        "rocketserializer.getDefaultJVMPath._checkJVMArch",
        lambda path, maxsize=None: None,
    )

    finder = WindowsJVMFinder()
    assert finder._get_from_path() == str(jvm_path)
