import argparse
from importlib.resources import path
import sys
import os
import pathlib
import urllib.request
import shutil
import subprocess
import glob

# --srcDir
#    package src directory in addition to rcljava related packages.
#     one of the srcDir or repoDir is required
# --repoFilePath
#    repo file path in addition to rcljava's repo file.

# --soOutDir
# --jarOutDir
# --clean


def getArgs():
    parser = argparse.ArgumentParser()

    parser.add_argument("soOutDir", help="output directory path of .so files", type=str)
    parser.add_argument("jarOutDir", help="output directory path of .jar files", type=str)
    parser.add_argument("--clean", help="clean build", action='store_true')

    additionalPackagesGroup = parser.add_mutually_exclusive_group()
    additionalPackagesGroup.add_argument("--srcDir", help="package src directory which contains packages in addition to rcljava related packages. rcljava related packages are automatically built.", type=str)
    additionalPackagesGroup.add_argument("--repoFile", help="repo file path which contains packages in addition to rcljava's repo file. rcljava related packages are automatically built.", type=str)
    

    args = parser.parse_args()
    return(args)


# -t allocates a TTY, which does not exist on CI runners
DOCKER_RUN = 'docker run -it' if sys.stdout.isatty() else 'docker run -i'


def setupRos2Java(workspacePath: pathlib.Path):
    repoFilePath = pathlib.Path(workspacePath, "ros2_java_android.repos")
    srcDirPath = pathlib.Path(workspacePath, "src")

    shutil.copyfile("./ros2_java_android.repos", repoFilePath)
    if not os.path.exists(srcDirPath):
        os.makedirs(srcDirPath)
        print('start cloning ros2java related packages')
        command = f'{DOCKER_RUN} --rm --net=host -v {workspacePath}:/home/user/workspace ros2java-android-build vcs import --input /home/user/workspace/ros2_java_android.repos /home/user/workspace/src'
        subprocess.run(command, shell=True, check=True)


def build(workspacePath: pathlib.Path):
    print('start building packages')
    command = f'{DOCKER_RUN} --rm --net=host -v {workspacePath}:/home/user/workspace ros2java-android-build /home/user/build-android.sh'
    subprocess.run(command, shell=True, check=True)

def output(workspacePath: pathlib.Path, soOutPath: pathlib.Path, jarOutPath: pathlib.Path):
    soFiles = [f for f in glob.glob(str(workspacePath) + "/install/**/*.so", recursive=True)]
    jarFiles = [f for f in glob.glob(str(workspacePath) + "/install/**/*.jar", recursive=True)]

    for file in soFiles:
        filepath = pathlib.Path(file)
        distFilePath = soOutPath.joinpath(filepath.name)
        shutil.copyfile(file, distFilePath)
    
    for file in jarFiles:
        filepath = pathlib.Path(file)
        distFilePath = jarOutPath.joinpath(filepath.name)
        shutil.copyfile(file, distFilePath)

    # copy stdlib
    filepath = workspacePath.joinpath("libc++_shared.so")
    distFilePath = soOutPath.joinpath(filepath.name)
    shutil.copyfile(filepath, distFilePath)

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
    reverse_check = subprocess.run(
        ["git", "-C", str(repoPath), "apply", "--reverse", "--check", str(patchPath)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if reverse_check.returncode == 0:
        print("Patch already applied, skipping.")
        return

    apply_result = subprocess.run(
        ["git", "-C", str(repoPath), "apply", str(patchPath)]
    )
    if apply_result.returncode != 0:
        raise RuntimeError(f"Failed to apply patch: {patchPath}")

    print("Patch applied successfully.")


def main():
    args = getArgs()

    workspacePath = pathlib.Path(pathlib.Path(__file__).resolve().parent, "tmp")
    workspaceAdditionalSrcDirPath = pathlib.Path(workspacePath, "additional-src")
    soOutPath = pathlib.Path(args.soOutDir).resolve()
    jarOutPath = pathlib.Path(args.jarOutDir).resolve()

    if workspaceAdditionalSrcDirPath.exists():
        shutil.rmtree(workspaceAdditionalSrcDirPath)

    if args.clean:
        if os.path.exists(workspacePath):
            shutil.rmtree(workspacePath)

    os.makedirs(workspacePath, exist_ok=True)
    os.makedirs(soOutPath, exist_ok=True)
    os.makedirs(jarOutPath, exist_ok=True)

    setupRos2Java(workspacePath)

    if args.srcDir is not None:
        additionalSrcDirPath = pathlib.Path(args.srcDir).resolve()
        shutil.copytree(additionalSrcDirPath, workspaceAdditionalSrcDirPath)

    if args.repoFile is not None:
        # TODO: need to implement
        raise NotImplementedError()
    
    patch(workspacePath, ["src", "ros2", "orocos_kdl_vendor"], ["patches", "orocos_kdl_vendor.patch"])
    patch(workspacePath, ["src", "ros2", "tinyxml_vendor"], ["patches", "tinyxml_vendor.patch"])
    patch(workspacePath, ["src", "ros2", "tinyxml2_vendor"], ["patches", "tinyxml2_vendor.patch"])
    patch(workspacePath, ["src", "ros2", "geometry2"], ["patches", "geometry2.patch"])
    patch(workspacePath, ["src", "ros2", "urdf"], ["patches", "urdf.patch"])
    patch(workspacePath, ["src", "ros2-java", "ros2_java"], ["patches", "ros2_java.patch"])
    patch(workspacePath, ["src", "ros2", "rmw_zenoh"], ["patches", "rmw_zenoh.patch"])
    patch(workspacePath, ["src", "eclipse-cyclonedds", "cyclonedds"], ["patches", "cyclonedds.patch"])
    patch(workspacePath, ["src", "eProsima", "Fast-DDS"], ["patches", "fastdds.patch"])
    build(workspacePath)
    output(workspacePath, soOutPath, jarOutPath)


if __name__ == '__main__':
    main()