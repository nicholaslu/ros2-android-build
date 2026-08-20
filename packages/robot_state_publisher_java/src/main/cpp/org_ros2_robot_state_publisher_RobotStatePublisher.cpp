// Copyright 2026 Open Source Robotics Foundation, Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <jni.h>

#include <atomic>
#include <exception>
#include <memory>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "robot_state_publisher/robot_state_publisher.hpp"

namespace
{

std::string
to_string(JNIEnv * env, jstring value)
{
  if (value == nullptr) {
    return std::string();
  }
  const char * chars = env->GetStringUTFChars(value, nullptr);
  std::string result(chars == nullptr ? "" : chars);
  if (chars != nullptr) {
    env->ReleaseStringUTFChars(value, chars);
  }
  return result;
}

void
throw_java(JNIEnv * env, const char * class_name, const std::string & message)
{
  jclass cls = env->FindClass(class_name);
  if (cls != nullptr) {
    env->ThrowNew(cls, message.c_str());
    env->DeleteLocalRef(cls);
  }
}

std::string
string_field(JNIEnv * env, jclass cls, jobject obj, const char * name)
{
  jfieldID fid = env->GetFieldID(cls, name, "Ljava/lang/String;");
  if (fid == nullptr) {
    return std::string();
  }
  jstring value = static_cast<jstring>(env->GetObjectField(obj, fid));
  std::string result = to_string(env, value);
  if (value != nullptr) {
    env->DeleteLocalRef(value);
  }
  return result;
}

/// Everything one running node owns, so stop() tears it all down in one place.
struct Instance
{
  rclcpp::Context::SharedPtr context;
  std::shared_ptr<robot_state_publisher::RobotStatePublisher> node;
  std::shared_ptr<rclcpp::executors::SingleThreadedExecutor> executor;
  std::thread spin_thread;
  std::atomic<bool> running;

  Instance()
  : running(false) {}
};

}  // namespace

extern "C" JNIEXPORT jlong JNICALL
Java_org_ros2_robot_1state_1publisher_RobotStatePublisher_nativeStart(
  JNIEnv * env, jclass, jobject joptions)
{
  if (joptions == nullptr) {
    throw_java(env, "java/lang/IllegalArgumentException", "options must not be null");
    return 0;
  }

  jclass options_cls = env->GetObjectClass(joptions);
  if (options_cls == nullptr) {
    throw_java(env, "java/lang/RuntimeException", "could not resolve options class");
    return 0;
  }

  const std::string urdf = string_field(env, options_cls, joptions, "robotDescription");
  const std::string frame_prefix = string_field(env, options_cls, joptions, "framePrefix");
  const std::string node_name = string_field(env, options_cls, joptions, "nodeName");
  const std::string node_namespace = string_field(env, options_cls, joptions, "namespace");

  jfieldID frequency_fid = env->GetFieldID(options_cls, "publishFrequency", "D");
  jfieldID ignore_fid = env->GetFieldID(options_cls, "ignoreTimestamp", "Z");
  jfieldID arguments_fid = env->GetFieldID(options_cls, "rosArguments", "[Ljava/lang/String;");
  if (frequency_fid == nullptr || ignore_fid == nullptr || arguments_fid == nullptr) {
    throw_java(env, "java/lang/RuntimeException", "options is missing an expected field");
    return 0;
  }

  const double publish_frequency = env->GetDoubleField(joptions, frequency_fid);
  const bool ignore_timestamp = env->GetBooleanField(joptions, ignore_fid) == JNI_TRUE;

  // Caller-supplied ROS arguments go in the global (context) position.
  std::vector<std::string> context_arguments;
  context_arguments.push_back(node_name.empty() ? "robot_state_publisher" : node_name);
  jobjectArray jarguments =
    static_cast<jobjectArray>(env->GetObjectField(joptions, arguments_fid));
  if (jarguments != nullptr) {
    const jsize count = env->GetArrayLength(jarguments);
    for (jsize i = 0; i < count; ++i) {
      jstring element = static_cast<jstring>(env->GetObjectArrayElement(jarguments, i));
      context_arguments.push_back(to_string(env, element));
      if (element != nullptr) {
        env->DeleteLocalRef(element);
      }
    }
    env->DeleteLocalRef(jarguments);
  }
  env->DeleteLocalRef(options_cls);

  // The upstream node hardcodes its name as "robot_state_publisher" and takes no namespace
  // argument, so both are applied as remappings scoped to this node.
  std::vector<std::string> node_arguments;
  node_arguments.push_back("--ros-args");
  if (!node_name.empty()) {
    node_arguments.push_back("-r");
    node_arguments.push_back("__node:=" + node_name);
  }
  if (!node_namespace.empty()) {
    node_arguments.push_back("-r");
    node_arguments.push_back("__ns:=" + node_namespace);
  }

  std::unique_ptr<Instance> instance(new Instance());
  try {
    // A private context keeps this node off the global one, so an rcljava executor running in
    // the same process is unaffected by our init/shutdown.
    instance->context = std::make_shared<rclcpp::Context>();
    std::vector<const char *> context_argv;
    context_argv.reserve(context_arguments.size());
    for (const std::string & argument : context_arguments) {
      context_argv.push_back(argument.c_str());
    }
    rclcpp::InitOptions init_options;
    // An app owns its own signal handling; installing ROS handlers would hijack the process.
    init_options.shutdown_on_signal = false;
    instance->context->init(
      static_cast<int>(context_argv.size()), context_argv.data(), init_options);

    rclcpp::NodeOptions node_options;
    node_options.context(instance->context);
    node_options.arguments(node_arguments);
    node_options.parameter_overrides(
    {
      rclcpp::Parameter("robot_description", urdf),
      rclcpp::Parameter("publish_frequency", publish_frequency),
      rclcpp::Parameter("frame_prefix", frame_prefix),
      rclcpp::Parameter("ignore_timestamp", ignore_timestamp),
    });

    // Throws if the URDF is empty or unparseable, or the frequency is out of range.
    instance->node = std::make_shared<robot_state_publisher::RobotStatePublisher>(node_options);

    rclcpp::ExecutorOptions executor_options;
    executor_options.context = instance->context;
    instance->executor =
      std::make_shared<rclcpp::executors::SingleThreadedExecutor>(executor_options);
    instance->executor->add_node(instance->node);

    Instance * raw = instance.get();
    raw->running.store(true);
    instance->spin_thread = std::thread(
      [raw]() {
        try {
          raw->executor->spin();
        } catch (const std::exception &) {
          // spin() throws if the context is torn down underneath it; stop() is authoritative.
        }
        raw->running.store(false);
      });
  } catch (const std::exception & e) {
    if (instance->context && instance->context->is_valid()) {
      instance->context->shutdown("robot_state_publisher_java failed to start");
    }
    // ~thread() on a joinable thread calls std::terminate, so never unwind past a live one.
    if (instance->spin_thread.joinable()) {
      instance->spin_thread.join();
    }
    throw_java(env, "java/lang/RuntimeException", std::string("failed to start: ") + e.what());
    return 0;
  }

  return reinterpret_cast<jlong>(instance.release());
}

extern "C" JNIEXPORT void JNICALL
Java_org_ros2_robot_1state_1publisher_RobotStatePublisher_nativeStop(
  JNIEnv *, jclass, jlong handle)
{
  if (handle == 0) {
    return;
  }
  std::unique_ptr<Instance> instance(reinterpret_cast<Instance *>(handle));

  if (instance->executor) {
    instance->executor->cancel();
  }
  // Shut the context down before joining, not after. cancel() only clears the executor's
  // spinning flag, so a stop() that lands before spin() has started is lost and join() would
  // block forever; an invalid context also breaks spin()'s loop condition, which cannot race.
  if (instance->context && instance->context->is_valid()) {
    instance->context->shutdown("robot_state_publisher_java stopped");
  }
  if (instance->spin_thread.joinable()) {
    instance->spin_thread.join();
  }
  if (instance->executor && instance->node) {
    instance->executor->remove_node(instance->node);
  }
  // Destroy the node before the context it was created on.
  instance->node.reset();
  instance->executor.reset();
  instance->context.reset();
}

extern "C" JNIEXPORT jboolean JNICALL
Java_org_ros2_robot_1state_1publisher_RobotStatePublisher_nativeIsRunning(
  JNIEnv *, jclass, jlong handle)
{
  if (handle == 0) {
    return JNI_FALSE;
  }
  const Instance * instance = reinterpret_cast<const Instance *>(handle);
  return instance->running.load() ? JNI_TRUE : JNI_FALSE;
}
