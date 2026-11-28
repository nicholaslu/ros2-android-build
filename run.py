import argparse
from importlib.resources import path
import sys
import os
import pathlib
import urllib.request
import shutil
import subprocess
import glob
import shlex

# --srcDir
#    package src directory in addition to rcljava related packages.
#     one of the srcDir or repoDir is required
# --repoFilePath
#    repo file path in addition to rcljava's repo file.

# --soOutDir
# --jarOutDir
# --symbolsOutDir
# --clean


def getArgs():
    parser = argparse.ArgumentParser()

    parser.add_argument("soOutDir", help="output directory path of .so files", type=str)
    parser.add_argument("jarOutDir", help="output directory path of .jar files", type=str)
    parser.add_argument("--symbolsOutDir", help="output directory for unstripped copies of the .so files (soOutDir gets stripped ones)", type=str)
    parser.add_argument("--clean", help="clean build", action='store_true')

    additionalPackagesGroup = parser.add_mutually_exclusive_group()
    additionalPackagesGroup.add_argument("--srcDir", help="package src directory which contains packages in addition to rcljava related packages. rcljava related packages are automatically built.", type=str)
    additionalPackagesGroup.add_argument("--repoFile", help="repo file path which contains packages in addition to rcljava's repo file. rcljava related packages are automatically built.", type=str)
    

    args = parser.parse_args()
    return(args)


# -t allocates a TTY, which does not exist on CI runners
DOCKER_RUN = 'docker run -it' if sys.stdout.isatty() else 'docker run -i'

# One branch per ROS 2 distro. Both the image tag and the workspace directory are
# namespaced by distro, because tmp/ and the image tag would otherwise be shared
# across branches -- and setupRos2Java() skips the import when src/ already exists,
# so a branch switch would silently build the other distro's sources.
DISTRO = 'lyrical'
IMAGE = f'ros2java-android-build:{DISTRO}'


def setupRos2Java(workspacePath: pathlib.Path):
    repoFilePath = pathlib.Path(workspacePath, "ros2_java_android.repos")
    srcDirPath = pathlib.Path(workspacePath, "src")

    shutil.copyfile("./ros2_java_android.repos", repoFilePath)
    if not os.path.exists(srcDirPath):
        os.makedirs(srcDirPath)
        print('start cloning ros2java related packages')
        command = f'{DOCKER_RUN} --rm --net=host -v {workspacePath}:/home/user/workspace {IMAGE} vcs import --input /home/user/workspace/ros2_java_android.repos /home/user/workspace/src'
        subprocess.run(command, shell=True, check=True)


def setupLocalPackages(workspacePath: pathlib.Path):
    """Copy the packages/ directory into the workspace source tree.

    These are packages maintained here rather than imported by vcs: they have no upstream to
    pull from and no upstream file to patch. Copied fresh on every run so edits take effect
    without a --clean, and kept under src/local/ so vcs import never touches them.
    """
    projectPath = pathlib.Path(__file__).resolve().parent
    packagesPath = projectPath.joinpath("packages")
    if not packagesPath.is_dir():
        return

    destRoot = workspacePath.joinpath("src", "local")
    if destRoot.exists():
        shutil.rmtree(destRoot)

    for package in sorted(packagesPath.iterdir()):
        if not package.is_dir():
            continue
        print(f"Adding local package: {package.name}")
        shutil.copytree(package, destRoot.joinpath(package.name))


def build(workspacePath: pathlib.Path):
    print('start building packages')
    command = f'{DOCKER_RUN} --rm --net=host -v {workspacePath}:/home/user/workspace {IMAGE} /home/user/build-android.sh'
    subprocess.run(command, shell=True, check=True)

def output(workspacePath: pathlib.Path, soOutPath: pathlib.Path, jarOutPath: pathlib.Path, symbolsOutPath: "pathlib.Path | None"):
    soFiles = [f for f in glob.glob(str(workspacePath) + "/install/**/*.so", recursive=True)]
    jarFiles = [f for f in glob.glob(str(workspacePath) + "/install/**/*.jar", recursive=True)]

    for file in soFiles:
        filepath = pathlib.Path(file)
        distFilePath = soOutPath.joinpath(filepath.name)
        shutil.copyfile(file, distFilePath)
        if symbolsOutPath is not None:
            shutil.copyfile(file, symbolsOutPath.joinpath(filepath.name))

    strip(soOutPath, [pathlib.Path(f).name for f in soFiles])
    
    for file in jarFiles:
        filepath = pathlib.Path(file)
        distFilePath = jarOutPath.joinpath(filepath.name)
        shutil.copyfile(file, distFilePath)

    # copy stdlib -- after strip(), and never stripped: apps pair the ROS libraries with
    # this exact stock NDK binary.
    filepath = workspacePath.joinpath("libc++_shared.so")
    distFilePath = soOutPath.joinpath(filepath.name)
    shutil.copyfile(filepath, distFilePath)

def strip(soOutPath: pathlib.Path, names: "list[str]"):
    """Strip debug info and .symtab from the given libraries in soOutPath, in place.

    --strip-unneeded keeps .dynsym, which linking and crash reports' function names need.
    Uses the NDK's llvm-strip from the image. Runs as the calling user, so the rewritten
    files keep their owner.
    """
    if not names:
        return
    print('stripping libraries')
    files = ' '.join(f'/out/{shlex.quote(n)}' for n in sorted(set(names)))
    command = (f'{DOCKER_RUN} --rm -u {os.getuid()}:{os.getgid()} -v {soOutPath}:/out {IMAGE} '
               f'bash -c \'"$ANDROID_NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip" --strip-unneeded "$@"\' strip {files}')
    subprocess.run(command, shell=True, check=True)

def patch(workspacePath: pathlib.Path, repoPath: pathlib.Path, patchPath: pathlib.Path):
    projectPath = pathlib.Path(__file__).resolve().parent
    repoPath = workspacePath.joinpath(*repoPath)
    patchPath = projectPath.joinpath(*patchPath)

    if not repoPath.exists():
        print(f"Patch skipped: repository not found: {repoPath}")
        return

    if not patchPath.exists():
        print(f"Patch skipped: patch file not found: {patchPath}")
        return

    print(f"Applying patch: {patchPath}")

    # skip if the patch is already applied
    # Stop git's repository discovery at repoPath. A source imported from a tarball
    # has no .git of its own, so git would otherwise find this project's repository
    # above it and resolve the patch's paths against that top level -- then silently
    # drop them all as "outside the current directory". Both the check and the apply
    # would succeed while changing nothing, and this function would report the patch
    # as already applied. Git clones still find their own .git first.
    git_env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(repoPath.parent))

    reverse_check = subprocess.run(
        ["git", "-C", str(repoPath), "apply", "--reverse", "--check", str(patchPath)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=git_env,
    )
    if reverse_check.returncode == 0:
        print("Patch already applied, skipping.")
        return

    apply_result = subprocess.run(
        ["git", "-C", str(repoPath), "apply", str(patchPath)],
        env=git_env,
    )
    if apply_result.returncode != 0:
        raise RuntimeError(f"Failed to apply patch: {patchPath}")

    print("Patch applied successfully.")


def main():
    args = getArgs()

    workspacePath = pathlib.Path(pathlib.Path(__file__).resolve().parent, "tmp", DISTRO)
    workspaceAdditionalSrcDirPath = pathlib.Path(workspacePath, "additional-src")
    soOutPath = pathlib.Path(args.soOutDir).resolve()
    jarOutPath = pathlib.Path(args.jarOutDir).resolve()
    symbolsOutPath = pathlib.Path(args.symbolsOutDir).resolve() if args.symbolsOutDir else None

    if workspaceAdditionalSrcDirPath.exists():
        shutil.rmtree(workspaceAdditionalSrcDirPath)

    if args.clean:
        if os.path.exists(workspacePath):
            shutil.rmtree(workspacePath)

    os.makedirs(workspacePath, exist_ok=True)
    os.makedirs(soOutPath, exist_ok=True)
    os.makedirs(jarOutPath, exist_ok=True)
    if symbolsOutPath is not None:
        os.makedirs(symbolsOutPath, exist_ok=True)

    setupRos2Java(workspacePath)
    setupLocalPackages(workspacePath)

    if args.srcDir is not None:
        additionalSrcDirPath = pathlib.Path(args.srcDir).resolve()
        shutil.copytree(additionalSrcDirPath, workspaceAdditionalSrcDirPath)

    if args.repoFile is not None:
        # TODO: need to implement
        raise NotImplementedError()
    
    # tinyxml_vendor was dropped from ROS 2 after Humble. tinyxml2_vendor and
    # orocos_kdl_vendor left ros2.repos before Lyrical -- desktop gets those via
    # rosdep, but an Android cross-build has no system tinyxml2 / orocos_kdl, so
    # they stay pinned by hand in the repos file and still need their patches.
    patch(workspacePath, ["src", "ros2", "orocos_kdl_vendor"], ["patches", "orocos_kdl_vendor.patch"])
    patch(workspacePath, ["src", "yaml", "libyaml"], ["patches", "libyaml.patch"])
    patch(workspacePath, ["src", "ros", "pluginlib"], ["patches", "pluginlib.patch"])
    patch(workspacePath, ["src", "ros", "urdfdom"], ["patches", "urdfdom.patch"])
    patch(workspacePath, ["src", "ros", "kdl_parser"], ["patches", "kdl_parser.patch"])
    patch(workspacePath, ["src", "ros", "robot_state_publisher"], ["patches", "robot_state_publisher.patch"])
    patch(workspacePath, ["src", "ros2", "tinyxml2_vendor"], ["patches", "tinyxml2_vendor.patch"])
    patch(workspacePath, ["src", "ros2", "rcutils"], ["patches", "rcutils.patch"])
    patch(workspacePath, ["src", "ros2", "rcpputils"], ["patches", "rcpputils.patch"])
    patch(workspacePath, ["src", "ros2", "rclcpp"], ["patches", "rclcpp.patch"])
    patch(workspacePath, ["src", "ros2", "geometry2"], ["patches", "geometry2.patch"])
    patch(workspacePath, ["src", "ros2", "urdf"], ["patches", "urdf.patch"])
    patch(workspacePath, ["src", "ros2-java", "ros2_java"], ["patches", "ros2_java.patch"])
    patch(workspacePath, ["src", "ros2", "rmw_zenoh"], ["patches", "rmw_zenoh.patch"])
    patch(workspacePath, ["src", "eclipse-cyclonedds", "cyclonedds"], ["patches", "cyclonedds.patch"])
    patch(workspacePath, ["src", "eProsima", "Fast-DDS"], ["patches", "fastdds.patch"])
    patch(workspacePath, ["src", "ZettaScaleLabs", "cyclors"], ["patches", "cyclors.patch"])
    patch(workspacePath, ["src", "eclipse-zenoh", "zenoh-plugin-ros2dds"], ["patches", "zenoh_plugin_ros2dds.patch"])
    build(workspacePath)
    output(workspacePath, soOutPath, jarOutPath, symbolsOutPath)


if __name__ == '__main__':
    main()