# ros2-android-build

Build [rcljava](https://github.com/ros2-java/ros2_java) for Android.  

**This is the `jazzy` branch.** The repository carries one branch per ROS 2 distro:

| Branch | Distro | Upstream EOL |
|---|---|---|
| [`humble`](../../tree/humble) | Humble Hawksbill | May 2027 |
| `jazzy` | Jazzy Jalisco | May 2029 |
| [`lyrical`](../../tree/lyrical) | Lyrical Luth | May 2031 |

Package versions are pinned to an official ROS 2 Jazzy patch release. The exact
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

Currently ROS2 Jazzy is selected for the building. To build a different distro,
check out that distro's branch.

## Message array fields differ from upstream ros2_java

Sequence and array members of basic type (`uint8[]`, `float64[]`, `float64[9]`, …)
are generated as Java **primitive arrays** — `byte[]`, `double[]` — not the
`java.util.List<Byte>` / `List<Double>` that upstream `rosidl_generator_java`
produces. See [`patches/ros2_java.patch`](./patches/ros2_java.patch).

Upstream marshals these one element at a time: three JNI calls per element when
publishing, and one boxed object allocated per element when receiving. For bulk
data that dominates everything else — a 42 KB `uint8[]` measured ~69 ms per
`publish()` on an Android phone, capping a 60 fps video topic near 12 Mbps. As
primitive arrays the same field is a single bulk copy.

| Accessor | Change |
|---|---|
| `setX(byte[])` | Same signature. No longer copies element by element. |
| `getX()` | Returns `byte[]` instead of `List<Byte>`. |
| `getXAsList()` | Added, for callers that still want the boxed list. |
| `setX(List<Byte>)` | Still accepted. |

Note that `setX(byte[])` now **stores the array by reference** rather than copying
it. Do not mutate a buffer after handing it to a message. Use `setX(List<Byte>)`
if you need the old copying behaviour.

`string[]` and arrays of messages are unaffected — they remain `List<String>` and
`List<MessageType>`, since their per-element JNI cost is inherent.

## zenoh-bridge-ros2dds

Releases include [zenoh-bridge-ros2dds](https://github.com/eclipse-zenoh/zenoh-plugin-ros2dds)
1.10.2, which bridges ROS 2 DDS traffic to [Zenoh](https://zenoh.io). It is a standalone
executable rather than a library, but it ships in `soOut` as `libzenoh_bridge_ros2dds.so`:
since Android 10 an app may only execute binaries from its `nativeLibraryDir`, and the
installer only extracts files named `lib*.so` there.

It needs only Android system libraries (Cyclone DDS is linked in statically), so it
can be dropped into `jniLibs/arm64-v8a` on its own. The APK must extract native
libraries to disk for the file to be executable:

```groovy
android {
    packaging { jniLibs { useLegacyPackaging = true } }
}
```

Then start it as a child process:

```kotlin
val bridge = File(applicationInfo.nativeLibraryDir, "libzenoh_bridge_ros2dds.so")
val process = ProcessBuilder(bridge.path, "-e", "tcp/192.168.1.10:7447")
    .redirectErrorStream(true)
    .apply { environment()["ROS_DISTRO"] = "jazzy" }
    .start()
```

Set `ROS_DISTRO` to `jazzy`. The binary is the same for every distro and picks its
ROS 2 conventions from this variable at startup (before Iron: no type hash in the QoS
user data, legacy discovery). When it is unset, the bridge warns and assumes Iron or
later. Pass it through `environment()`: `Os.setenv` changes made at runtime don't reach
child processes, because `ProcessBuilder` copies the JVM's startup environment. The same
applies to `ROS_DOMAIN_ID`; pass `-d <id>` or set it the same way.

The bridge talks DDS to local nodes, so those nodes must use a DDS RMW
(`rmw_cyclonedds_cpp` is what upstream tests against), not `rmw_zenoh_cpp`. On the
Zenoh side it speaks to other zenoh-bridge-ros2dds instances or a `zenohd` router;
it is not a drop-in peer for `rmw_zenoh` nodes, which use a different key format.

## How to build

### 1. Clone repository
```
git clone -b jazzy https://github.com/nicholaslu/ros2-android-build
cd ros2-android-build/
```

### 2. Build docker image
```
docker build -t ros2java-android-build:jazzy ./
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
release-jazzy-20260618      # Android build of Jazzy Patch Release 8
```

If the same upstream release has to be rebuilt after an Android-side fix, add a
build number starting at `-2`:

```
release-jazzy-20260618-2    # same upstream packages, patched and rebuilt
```

The `<distro>-<YYYYMMDD>` part must match the `# ros2-release:` pin in
`ros2_java_android.repos`; CI fails the release if it does not. Tag the branch
whose distro you are releasing. The release title
and notes are generated automatically, reusing upstream's own release name.

```
git tag release-jazzy-20260618
git push origin release-jazzy-20260618
```
