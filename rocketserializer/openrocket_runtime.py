import logging
import os
import re
from pathlib import Path

import jpype
import jpype.imports
import orhelper

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


class OpenRocketSession(orhelper.OpenRocketInstance):
    def __init__(self, jar_path, log_level="OFF"):
        self.jar_path = Path(jar_path)
        if not self.jar_path.exists():
            raise FileNotFoundError(
                f"Jar file '{self.jar_path.as_posix()}' does not exist"
            )

        # Get the default JVM path early so we can pass it
        jvm_path = jpype.getDefaultJVMPath()
        # Initialize the base class with kwargs to bypass auto-discovery
        super().__init__(jar=str(self.jar_path), jvm=str(jvm_path), loglevel=log_level)
        self.openrocket = None
        # for newest orhelper support
        self.openrocket_core = None
        self.openrocket_swing = None

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
            pass

    def __enter__(self):
        ensure_java_compatibility(self.jar_path)

        jvm_path = jpype.getDefaultJVMPath()
        logger.info(
            "Starting JVM from '%s' with OpenRocket '%s'",
            jvm_path,
            self.jar_path.as_posix(),
        )

        if jpype.isJVMStarted():
            logger.warning(
                "JVM is already running; skipping startJVM. "
                "Ensure the active JVM has '%s' on its classpath.",
                self.jar_path.as_posix(),
            )
        else:
            jpype.startJVM(
                jvm_path,
                "-ea",
                f"-Djava.class.path={self.jar_path.as_posix()}",
            )

        self.openrocket_core, self.openrocket_swing = self._resolve_packages()
        self.openrocket = self.openrocket_core  # for legacy orhelper versions

        guice = jpype.JPackage("com").google.inject.Guice
        logger_factory = jpype.JPackage("org").slf4j.LoggerFactory
        logger_class = jpype.JPackage("ch").qos.logback.classic.Logger

        gui_module = self.openrocket_swing.startup.GuiModule()
        plugin_module = self.openrocket_core.plugin.PluginModule()

        injector = guice.createInjector(gui_module, plugin_module)

        app = self.openrocket_core.startup.Application
        app.setInjector(injector)

        gui_module.startLoader()
        self._block_loader(gui_module, "presetLoader")
        self._block_loader(gui_module, "motorLoader")

        root_logger = logger_factory.getLogger(logger_class.ROOT_LOGGER_NAME)
        root_logger.setLevel(self._translate_log_level())

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
                # Do not call shutdownJVM() here: JPype <1.5 cannot restart the JVM
        finally:
            self.started = False

    def load_doc(self, ork_filename: str):
        if not self.started:
            raise RuntimeError("OpenRocketSession has not been started")
        return orhelper.Helper(self).load_doc(ork_filename)
