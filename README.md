# ros2-android-build

Build [rcljava](https://github.com/ros2-java/ros2_java) for Android.  

**This is the `lyrical` branch.** The repository carries one branch per ROS 2 distro:

| Branch | Distro | Upstream EOL |
|---|---|---|
| [`humble`](../../tree/humble) | Humble Hawksbill | May 2027 |
| [`jazzy`](../../tree/jazzy) | Jazzy Jalisco | May 2029 |
| `lyrical` | Lyrical Luth | May 2031 |

Package versions are pinned to an official ROS 2 Lyrical patch release. The exact
release is recorded in the `# ros2-release:` line at the top of
[`ros2_java_android.repos`](./ros2_java_android.repos), which is the single source
of truth for the pin.

## Releases

Prebuilt libraries are published under [Releases](../../releases). Each release
corresponds to one official [ros2/ros2](https://github.com/ros2/ros2/releases)
patch release, and carries two assets:

- `*-soOut.tar.gz` — native libraries → `app/src/main/jniLibs/arm64-v8a`
- `*-jarOut.tar.gz` — Java libraries → `app/libs/rcljava`

If you only want the libraries, download these instead of building.

## Environment
Modify [Dockerfile](./Dockerfile) to change environment.
- NDK:  android-ndk-r28
- ABI: arm64-v8a  
- Android API Level: 24

## ROS2 version  

Modify [repo](./ros2_java_android.repos) to change ROS2 version.

Currently ROS2 Lyrical is selected for the building. To build a different distro,
check out that distro's branch.

## How to build

### 1. Clone repository
```
git clone -b lyrical https://github.com/nicholaslu/ros2-android-build
cd ros2-android-build/
```

### 2. Build docker image
```
docker build -t ros2java-android-build:lyrical ./
```

### 3. Build
```
python3 run.py ./out/soOut ./out/jarOut
```

### 4. Copy files to Android Studio project
Copy `.jar` files to `app/libs/rcljava` and `.so` files to `app/src/main/jniLibs/arm64-v8a`
and add `implementation fileTree(include: ['*.jar'], dir: 'libs')` to `dependencies{}` of `app/build.gradle`

## How to cut a release

Releases are built by CI from a tag. The tag matches the `ros2/ros2` release
being built:

```
release-lyrical-20260623    # Android build of Lyrical Patch Release 1
```

If the same upstream release has to be rebuilt after an Android-side fix, add a
build number starting at `-2`:

```
release-lyrical-20260623-2  # same upstream packages, patched and rebuilt
```

The `<distro>-<YYYYMMDD>` part must match the `# ros2-release:` pin in
`ros2_java_android.repos`; CI fails the release if it does not. Tag the branch
whose distro you are releasing. The release title
and notes are generated automatically, reusing upstream's own release name.

```
git tag release-lyrical-20260623
git push origin release-lyrical-20260623
```
