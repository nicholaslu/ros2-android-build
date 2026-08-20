package org.ros2.robot_state_publisher;

import org.ros2.rcljava.common.JNIUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Runs the upstream robot_state_publisher node in this process.
 *
 * <p>The node gets its own ROS context and single-threaded executor spinning on a dedicated
 * thread, so it is independent of any rcljava executors in the same process and starting or
 * stopping it never disturbs them.
 *
 * <p>Construction starts the node; it is running by the time the constructor returns. Not
 * thread-safe: serialise {@link #stop()} against construction externally.
 */
public class RobotStatePublisher {
  private static final Logger logger = LoggerFactory.getLogger(RobotStatePublisher.class);

  static {
    try {
      JNIUtils.loadImplementation(RobotStatePublisher.class);
    } catch (UnsatisfiedLinkError ule) {
      // Rethrow rather than exiting: the caller wraps construction and can degrade gracefully.
      logger.error("Native code library failed to load.\n" + ule);
      throw ule;
    }
  }

  private long handle;

  /**
   * Starts the node.
   *
   * @param options configuration; must not be null and must carry a non-empty URDF.
   * @throws IllegalArgumentException if options is null
   * @throws RuntimeException if the URDF is empty or unparseable, the publish frequency is out
   *     of range, or the node otherwise fails to start
   */
  public RobotStatePublisher(final RobotStatePublisherOptions options) {
    if (options == null) {
      throw new IllegalArgumentException("options must not be null");
    }
    this.handle = nativeStart(options);
  }

  /** True while the executor thread is spinning. False once {@link #stop()} has completed. */
  public boolean isRunning() {
    return this.handle != 0 && nativeIsRunning(this.handle);
  }

  /**
   * Shuts the node down and joins its executor thread. Idempotent; safe to call after a failed
   * construction. Blocks until the spin thread has exited.
   */
  public void stop() {
    final long toStop = this.handle;
    if (toStop == 0) {
      return;
    }
    // Clear first so a second stop() cannot double-free even if nativeStop throws.
    this.handle = 0;
    nativeStop(toStop);
  }

  /** Opaque native handle, or 0 once stopped. Exposed for diagnostics. */
  public long getHandle() {
    return this.handle;
  }

  private static native long nativeStart(RobotStatePublisherOptions options);

  private static native void nativeStop(long handle);

  private static native boolean nativeIsRunning(long handle);
}
