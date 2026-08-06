# Build from the repository root:
#   docker build -f service/Dockerfile -t ork-serializer .
#
# Java 17 is the floor: openrocket_runtime._minimum_java_required() demands it
# for OpenRocket 23.x jars, and jpype needs a JVM it can dlopen in-process.
FROM eclipse-temurin:17-jdk-jammy

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        curl \
    && rm -rf /var/lib/apt/lists/*

# OpenRocket's startup path constructs a Swing GuiModule and touches
# java.awt.Window, which aborts without a display unless headless is forced.
ENV JAVA_TOOL_OPTIONS="-Djava.awt.headless=true" \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ORK_JAR=/opt/openrocket/OpenRocket-23.09.jar

WORKDIR /app

# Dependencies first so application edits don't re-resolve rocketpy/numpy.
COPY requirements.in service/requirements.txt ./deps/
RUN pip3 install --no-cache-dir -r deps/requirements.in -r deps/requirements.txt

COPY pyproject.toml README.md LICENSE.md ./
COPY rocketserializer ./rocketserializer
COPY service ./service
RUN pip3 install --no-cache-dir --no-deps -e .

# Only the pinned jar ships; the version is baked into SERIALIZER_VERSION so a
# parse can always be traced back to the parser that produced it.
COPY OpenRocket-23.09.jar /opt/openrocket/OpenRocket-23.09.jar

RUN useradd --create-home --uid 1001 serializer
USER serializer

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000"]
