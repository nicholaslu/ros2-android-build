#!/bin/bash
set -eu

cd /home/user/workspace

export PYTHON3_EXEC="$( which python3 )"
# stdlib sysconfig, not distutils.sysconfig -- distutils was removed in Python 3.12,
# which is the default on Ubuntu 24.04. Both return identical values for these keys.
export PYTHON3_LIBRARY="$( ${PYTHON3_EXEC} -c 'import os.path, sysconfig; print(os.path.realpath(os.path.join(sysconfig.get_config_var("LIBPL"), sysconfig.get_config_var("LDLIBRARY"))))' )"
export PYTHON3_INCLUDE_DIR="$( ${PYTHON3_EXEC} -c 'import sysconfig; print(sysconfig.get_config_var("INCLUDEPY"))' )"
export CMAKE_PREFIX_PATH="/usr/share/eigen3/cmake:${PWD}/install:${CMAKE_PREFIX_PATH:-}"

colcon build \
    --packages-ignore rcl_logging_log4cxx rcl_logging_spdlog rosidl_generator_py rclandroid ros2_talker_android ros2_listener_android performance_test_fixture osrf_testing_tools_cpp google_benchmark_vendor launch_testing_ament_cmake \
    tf2_kdl tf2_eigen tf2_eigen_kdl tf2_py python_orocos_kdl_vendor tf2_bullet \
    zenoh_security_tools test_rmw_zenoh_cpp \
    lttngpy \
    --cmake-args \
    -DPython3_EXECUTABLE=${PYTHON3_EXEC} \
    -DPython3_LIBRARY=${PYTHON3_LIBRARY} \
    -DPython3_INCLUDE_DIR=${PYTHON3_INCLUDE_DIR} \
    -DCMAKE_TOOLCHAIN_FILE=${CMAKE_TOOLCHAIN_FILE} \
    -DANDROID=ON \
    -DANDROID_FUNCTION_LEVEL_LINKING=OFF \
    -DANDROID_PLATFORM=${ANDROID_TARGET} \
    -DANDROID_NATIVE_API_LEVEL=${ANDROID_TARGET} \
    -DANDROID_TOOLCHAIN_NAME=${ANDROID_TOOLCHAIN_NAME} \
    -DANDROID_STL=c++_shared \
    -DANDROID_ABI=${ANDROID_ABI} \
    -DANDROID_NDK=${ANDROID_NDK} \
    -DTHIRDPARTY=ON  \
    -DCOMPILE_EXAMPLES=OFF \
    -DCMAKE_FIND_ROOT_PATH="${PWD}/install" \
    -DBUILD_TESTING=OFF \
    -DRCL_LOGGING_IMPLEMENTATION=rcl_logging_noop \
    -DEIGEN3_INCLUDE_DIR=/usr/include/eigen3 \
    -DEigen3_DIR=/usr/share/eigen3/cmake \
    -DZENOHC_CUSTOM_TARGET=${ANDROID_TOOLCHAIN_NAME}

## copy libc++_shared.so
# cp /opt/android/android-ndk-r23b/sources/cxx-stl/llvm-libc++/libs/${ANDROID_ABI}/libc++_shared.so /home/user/workspace
cp ${ANDROID_NDK}/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/aarch64-linux-android/libc++_shared.so /home/user/workspace
