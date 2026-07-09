FROM ubuntu:22.04

# setup non-root user
ARG USERNAME=user
ARG USER_UID=1001
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME
#--------------------------------------------------------------------------------------------

ENV ANDROID_NDK_VERSION android-ndk-r28
ENV ANDROID_TARGET android-24
ENV ANDROID_ABI arm64-v8a
ENV ANDROID_TOOLCHAIN_NAME aarch64-linux-android

ENV ANDROID_NDK /opt/android/${ANDROID_NDK_VERSION}
ENV CMAKE_TOOLCHAIN_FILE=${ANDROID_NDK}/build/cmake/android.toolchain.cmake
ENV TZ=Asia/Tokyo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# setup ROS2
RUN apt-get update && apt-get install -y \
    curl gnupg lsb-release software-properties-common && \
    add-apt-repository universe && \
    ROS_APT_SOURCE_VERSION=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F "tag_name" | awk -F'"' '{print $4}') && \
    curl -L -o /tmp/ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.$(. /etc/os-release && echo ${UBUNTU_CODENAME:-${VERSION_CODENAME}})_all.deb" && \
    dpkg -i /tmp/ros2-apt-source.deb && \
    rm -f /tmp/ros2-apt-source.deb

RUN apt update
RUN apt install -y \
    git \
    vim \
    build-essential \
    openjdk-8-jdk \
    cmake \
    unzip \
    wget \
    gradle \
    python3-dev \
    python3-pip \
    python3-empy \
    python3-colcon-common-extensions \
    python3-vcstool \
    python3-lark \
    libeigen3-dev \
    libbullet-dev

# RUN apt install -y git vim cmake build-essential openjdk-8-jdk
# RUN apt install -y unzip wget gradle python3-pip
# RUN pip3 install -U colcon-common-extensions vcstool lark colcon-ros-gradle

RUN wget -O /tmp/android-ndk.zip https://dl.google.com/android/repository/${ANDROID_NDK_VERSION}-linux.zip && mkdir -p /opt/android/ && cd /opt/android/ && unzip -q /tmp/android-ndk.zip && rm /tmp/android-ndk.zip

RUN mkdir -p /home/${USERNAME}/workspace/

COPY ./build-android.sh /home/${USERNAME}/
RUN chmod +x /home/${USERNAME}/build-android.sh


#Android SDK
#only needed if you want to build android related packages
#ENV ANDROID_SDK_ROOT "/opt/android/sdk"
#ENV ANDROID_HOME "/opt/android/sdk"
#RUN mkdir -p ${ANDROID_SDK_ROOT}/cmdline-tools
#RUN wget -O /tmp/android-sdk.zip https://dl.google.com/android/repository/commandlinetools-linux-8092744_latest.zip && unzip /tmp/android-sdk.zip -d $ANDROID_SDK_ROOT/cmdline-tools && mv ${ANDROID_SDK_ROOT}/cmdline-tools/cmdline-tools ${ANDROID_SDK_ROOT}/cmdline-tools/tools && rm /tmp/android-sdk.zip

#RUN yes | ${ANDROID_SDK_ROOT}/cmdline-tools/tools/bin/sdkmanager --licenses
#RUN yes | ${ANDROID_SDK_ROOT}/cmdline-tools/tools/bin/sdkmanager --verbose "platform-tools" "platforms;${ANDROID_TARGET}"

USER $USERNAME
WORKDIR /home/$USERNAME/

# rmw_zenoh's zenoh_cpp_vendor package builds zenoh-c, a Rust crate, via cargo.
# The exact zenoh-c commit it vendors (picked by its own CMake based on the
# detected cargo version) ships its own rust-toolchain.toml pinning some other
# Rust version, which would need its own aarch64-linux-android target added on
# every bump. Sidestep that entirely by forcing every cargo invocation in this
# image to always use our `stable` toolchain regardless of any rust-toolchain
# file a vendored crate ships.
ENV RUSTUP_HOME=/home/${USERNAME}/.rustup
ENV CARGO_HOME=/home/${USERNAME}/.cargo
ENV PATH=${CARGO_HOME}/bin:${PATH}
ENV RUSTUP_TOOLCHAIN=stable

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable --profile minimal \
    && rustup target add aarch64-linux-android

# crates with a C component (e.g. ring, used by rustls) build via the `cc` crate,
# which doesn't read cargo's own linker config below -- it needs its own env vars.
ENV CC_aarch64_linux_android=${ANDROID_NDK}/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang
ENV CXX_aarch64_linux_android=${ANDROID_NDK}/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang++
ENV AR_aarch64_linux_android=${ANDROID_NDK}/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-ar
ENV CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER=${ANDROID_NDK}/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android24-clang

# point cargo at the NDK's clang wrapper for the ABI/API level configured above.
# rustflags forces a DT_SONAME onto any cdylib built for this target (e.g.
# zenoh-c's libzenohc.so) -- without it, rustc emits no soname, so a consumer
# linked against it (rmw_zenoh_cpp) records the absolute build-machine install
# path in its own DT_NEEDED instead of a bare filename, which only resolves on
# the machine that built it and fails to dlopen anywhere else (e.g. Android).
RUN mkdir -p ${CARGO_HOME} \
    && printf '[target.aarch64-linux-android]\nlinker = "%s"\nar = "%s"\nrustflags = ["-C", "link-arg=-Wl,-soname,libzenohc.so"]\n' \
        "${ANDROID_NDK}/toolchains/llvm/prebuilt/linux-x86_64/bin/${ANDROID_TOOLCHAIN_NAME}${ANDROID_TARGET#android-}-clang" \
        "${ANDROID_NDK}/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-ar" \
        > ${CARGO_HOME}/config.toml
