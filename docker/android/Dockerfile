# Disposable Android build image for Keepsake (Tauri 2). Remove with: docker rmi keepsake-android
FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
ARG CMDLINE_TOOLS_REV=13114758
ARG NDK_VERSION=27.2.12479018
ARG BUILD_TOOLS=37.0.0
ARG PLATFORM=android-37.0
ARG BUN_VERSION=1.4.4

# System packages + JDK 17 + build essentials
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl unzip zip git rsync xz-utils perl \
      build-essential pkg-config libssl-dev clang lld \
      openjdk-17-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV NDK_HOME=/opt/android-sdk/ndk/${NDK_VERSION}
ENV RUSTUP_HOME=/opt/rustup
ENV CARGO_HOME=/opt/cargo
ENV BUN_INSTALL=/opt/bun
ENV PATH=/opt/cargo/bin:/opt/bun/bin:/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:/opt/android-sdk/build-tools/${BUILD_TOOLS}:${PATH}

# Android SDK (cmdline-tools, platform, build-tools, NDK)
RUN mkdir -p ${ANDROID_HOME}/cmdline-tools \
    && curl -fsSL -o /tmp/clt.zip https://dl.google.com/android/repository/commandlinetools-linux-${CMDLINE_TOOLS_REV}_latest.zip \
    && unzip -q /tmp/clt.zip -d ${ANDROID_HOME}/cmdline-tools \
    && mv ${ANDROID_HOME}/cmdline-tools/cmdline-tools ${ANDROID_HOME}/cmdline-tools/latest \
    && rm /tmp/clt.zip \
    && (yes | sdkmanager --licenses >/dev/null || true) \
    && sdkmanager "platform-tools" "platforms;${PLATFORM}" "build-tools;${BUILD_TOOLS}" "ndk;${NDK_VERSION}"

# Rust + Android targets
RUN curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable \
    && rustup target add aarch64-linux-android armv7-linux-androideabi i686-linux-android x86_64-linux-android

# bun
RUN curl -fsSL -o /tmp/bun.zip https://github.com/oven-sh/bun/releases/download/bun-v${BUN_VERSION}/bun-linux-x64.zip \
    && unzip -q /tmp/bun.zip -d /tmp && mkdir -p /opt/bun/bin \
    && mv /tmp/bun-linux-x64/bun /opt/bun/bin/bun && rm -rf /tmp/bun* \
    && bun --version

COPY build.sh /usr/local/bin/build.sh
RUN chmod +x /usr/local/bin/build.sh
WORKDIR /work
ENTRYPOINT ["/usr/local/bin/build.sh"]
