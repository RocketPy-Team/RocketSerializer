import logging
import os
import re
from pathlib import Path

import jpype
import jpype.imports

logger = logging.getLogger(__name__)


def _jar_version_tuple(jar_path: Path):
    match = re.search(r"OpenRocket[-_]?(\d+(?:\.\d+)*)", jar_path.name, re.IGNORECASE)
    if not match:
        return (0,)

    version = []
    for token in match.group(1).split("."):
        if token.isdigit():
            version.append(int(token))
    return tuple(version) if version else (0,)


def select_latest_openrocket_jar(search_dir: Path):
    jars = [
        path
        for path in search_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() == ".jar"
        and path.name.lower().startswith("openrocket")
    ]

    if not jars:
        raise FileNotFoundError(
            "It was not possible to find an OpenRocket .jar file in the current "
            "directory. Please specify one explicitly with --ork_jar."
        )

    jars.sort(
        key=lambda path: (_jar_version_tuple(path), path.name.lower()), reverse=True
    )
    return jars[0]


def _extract_java_major(value: str):
    if not value:
        return None

    normalized = value.replace("\\", "/").lower()

    legacy = re.search(r"(?:jdk|jre)[-_]?1\.(\d+)", normalized)
    if legacy:
        return int(legacy.group(1))

    modern = re.search(r"(?:jdk|jre|java)[-_]?(\d{2})", normalized)
    if modern:
        return int(modern.group(1))

    return None


def _minimum_java_required(jar_path: Path):
    version = _jar_version_tuple(jar_path)
    if version and version[0] >= 23:
        return 17
    return 8


def _find_windows_jdk(minimum_major: int):
    search_roots = [
        Path("C:/Program Files/Java"),
        Path("C:/Program Files/Eclipse Adoptium"),
        Path("C:/Program Files/AdoptOpenJDK"),
    ]

    candidates = []
    for root in search_roots:
        if not root.exists():
            continue

        for child in root.iterdir():
            if not child.is_dir():
                continue
            major = _extract_java_major(child.name)
            if major is None:
                continue
            if major >= minimum_major and (child / "bin" / "java.exe").exists():
                candidates.append((major, child))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def ensure_java_compatibility(jar_path: Path):
    required_major = _minimum_java_required(jar_path)
    if required_major <= 8:
        return

    java_home_major = _extract_java_major(os.environ.get("JAVA_HOME", ""))
    if java_home_major and java_home_major >= required_major:
        return

    default_jvm_major = None
    try:
        default_jvm_major = _extract_java_major(jpype.getDefaultJVMPath())
    except (
        jpype.JVMNotFoundException,
        jpype.JVMNotSupportedException,
        OSError,
    ):
        default_jvm_major = None

    if default_jvm_major and default_jvm_major >= required_major:
        return

    if os.name != "nt":
        logger.warning(
            "OpenRocket %s requires Java %d+, but no compatible JVM was detected.",
            jar_path.name,
            required_major,
        )
        return

    selected_jdk = _find_windows_jdk(required_major)
    if not selected_jdk:
        logger.warning(
            "OpenRocket %s requires Java %d+, but no compatible JDK was found in "
            "standard Windows locations.",
            jar_path.name,
            required_major,
        )
        return

    os.environ["JAVA_HOME"] = str(selected_jdk)
    os.environ["PATH"] = (
        str(selected_jdk / "bin") + os.pathsep + os.environ.get("PATH", "")
    )
    logger.info(
        "Using Java from '%s' for OpenRocket compatibility.", selected_jdk.as_posix()
    )


class OpenRocketSession:
    def __init__(self, jar_path, log_level="OFF"):
        self.jar_path = Path(jar_path)
        if not self.jar_path.exists():
            raise FileNotFoundError(
                f"Jar file '{self.jar_path.as_posix()}' does not exist"
            )

        self.log_level = log_level
        self.openrocket = None
        self.started = False

    def _resolve_packages(self):
        try:
            legacy = jpype.JPackage("net").sf.openrocket
            _ = legacy.startup.Application
            return legacy, legacy
        except (AttributeError, TypeError, RuntimeError):
            modern = jpype.JPackage("info").openrocket
            return modern.core, modern.swing

    @staticmethod
    def _block_loader(gui_module, field_name):
        try:
            field = gui_module.getClass().getDeclaredField(field_name)
            field.setAccessible(True)
            loader = field.get(gui_module)
            field.setAccessible(False)
            loader.blockUntilLoaded()
        except (AttributeError, TypeError, RuntimeError, jpype.JException):
            # New OpenRocket versions can change internals; loading still works
            # without explicitly waiting in most cases.
            pass

    def __enter__(self):
        ensure_java_compatibility(self.jar_path)

        jvm_path = jpype.getDefaultJVMPath()
        logger.info(
            "Starting JVM from '%s' with OpenRocket '%s'",
            jvm_path,
            self.jar_path.as_posix(),
        )

        jpype.startJVM(
            jvm_path,
            "-ea",
            f"-Djava.class.path={self.jar_path.as_posix()}",
        )

        self.openrocket, swing = self._resolve_packages()

        guice = jpype.JPackage("com").google.inject.Guice
        logger_factory = jpype.JPackage("org").slf4j.LoggerFactory
        logger_class = jpype.JPackage("ch").qos.logback.classic.Logger
        logger_level = jpype.JPackage("ch").qos.logback.classic.Level

        gui_module = swing.startup.GuiModule()
        plugin_module = self.openrocket.plugin.PluginModule()

        injector = guice.createInjector(gui_module, plugin_module)

        app = self.openrocket.startup.Application
        app.setInjector(injector)

        gui_module.startLoader()
        self._block_loader(gui_module, "presetLoader")
        self._block_loader(gui_module, "motorLoader")

        root_logger = logger_factory.getLogger(logger_class.ROOT_LOGGER_NAME)
        root_logger.setLevel(
            getattr(logger_level, str(self.log_level), logger_level.ERROR)
        )

        self.started = True
        return self

    def __exit__(self, ex_type, ex, tb):
        try:
            if jpype.isJVMStarted():
                try:
                    for window in jpype.java.awt.Window.getWindows():
                        window.dispose()
                except (AttributeError, TypeError, RuntimeError, jpype.JException):
                    pass
                jpype.shutdownJVM()
        finally:
            self.started = False

    def load_doc(self, ork_filename: str):
        if not self.started:
            raise RuntimeError("OpenRocketSession has not been started")

        java_file = jpype.java.io.File(ork_filename)
        loader = self.openrocket.file.GeneralRocketLoader(java_file)
        return loader.load()
