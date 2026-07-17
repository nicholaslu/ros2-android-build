# ros2-android-build

Build [rcljava](https://github.com/ros2-java/ros2_java) for Android.  

Package versions are pinned to an official ROS 2 Humble patch release, currently release-humble-20260220.

## Environment
Modify [Dockerfile](./Dockerfile) to change environment.
- NDK:  android-ndk-r23b
- ABI: arm64-v8a  
- Android API Level: 24

## ROS2 version  

Modify [repo](./ros2_java_android.repos) to change ROS2 version.

Currently ROS2 Humble is selectd for the building.

## How to build

### 1. Clone repository
```
git clone https://github.com/nicholaslu/ros2-android-build
cd ros2-android-build/
```

### 2. Build docker image
```
docker build -t ros2java-android-build ./
```

### 3. Build
```
python3 run.py ./out/soOut ./out/jarOut
```

### 4. Copy files to Android Studio project
Copy `.jar` files to `app/libs/rcljava` and `.so` files to `app/src/main/jniLibs/arm64-v8a`
and add `implementation fileTree(include: ['*.jar'], dir: 'libs')` to `dependencies{}` of `app/build.gradle`
