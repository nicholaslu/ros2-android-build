# ros2-android-build

Cross-compile [rcljava](https://github.com/ros2-java/ros2_java) — the ROS 2 Java
client library — and its dependencies for Android.

**This branch carries no build files.** The build lives on one branch per ROS 2
distro, each self-contained: its own pinned `.repos` file, patch set, Dockerfile
and CI workflow. Pick the branch for the distro you want.

| Branch | Distro | Upstream pin | Base image | Upstream EOL |
|---|---|---|---|---|
| [`humble`](../../tree/humble)   | Humble Hawksbill | `release-humble-20260914`  | Ubuntu 22.04 | May 2027 |
| [`jazzy`](../../tree/jazzy)     | Jazzy Jalisco    | `release-jazzy-20260618`   | Ubuntu 24.04 | May 2029 |
| [`lyrical`](../../tree/lyrical) | Lyrical Luth     | `release-lyrical-20260807` | Ubuntu 26.04 | May 2031 |

Each branch's pin is recorded in the `# ros2-release:` line at the top of its
`ros2_java_android.repos` and matches an official
[ros2/ros2 release](https://github.com/ros2/ros2/releases) tag. That line is the
single source of truth: CI refuses to publish a release whose tag disagrees with it.

## Prebuilt libraries

Most people want [Releases](../../releases) rather than a build. Each release is
tagged `release-<distro>-<YYYYMMDD>` and carries:

- `*-soOut.tar.gz` — native libraries → `app/src/main/jniLibs/arm64-v8a`
- `*-jarOut.tar.gz` — Java libraries → `app/libs/rcljava`
- `SHA256SUMS.txt` — checksums for both

All builds target NDK r28, ABI `arm64-v8a`, Android API level 24, and include the
Fast-DDS, Cyclone DDS and Zenoh RMW implementations, plus the
[zenoh-bridge-ros2dds](https://github.com/eclipse-zenoh/zenoh-plugin-ros2dds)
executable — see a branch README for how to run it on Android.

## Building

```
git clone https://github.com/nicholaslu/ros2-android-build
cd ros2-android-build/
git switch lyrical                              # or humble / jazzy
docker build -t ros2java-android-build:lyrical ./
python3 run.py ./out/soOut ./out/jarOut
```

See that branch's README for the full instructions, including how to add your own
packages to the workspace and how to cut a release.
