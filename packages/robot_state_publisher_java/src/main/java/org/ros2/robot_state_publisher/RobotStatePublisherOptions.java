package org.ros2.robot_state_publisher;

/**
 * Configuration for a {@link RobotStatePublisher}.
 *
 * <p>The field names here are read directly by the native code, so renaming a field is a
 * breaking change even though it looks private. Defaults match the upstream node's own
 * parameter defaults.
 */
public class RobotStatePublisherOptions {
  private String robotDescription = "";
  private double publishFrequency = 20.0;
  private boolean ignoreTimestamp = false;
  private String framePrefix = "";
  private String nodeName = "robot_state_publisher";
  private String namespace = "";
  private String[] rosArguments = new String[0];

  public String getRobotDescription() {
    return this.robotDescription;
  }

  /** The URDF XML to publish and derive transforms from. Must not be empty. */
  public RobotStatePublisherOptions setRobotDescription(final String robotDescription) {
    this.robotDescription = robotDescription;
    return this;
  }

  public double getPublishFrequency() {
    return this.publishFrequency;
  }

  /** Rate for the fixed transforms, in Hz. The node requires 0 &lt; frequency &lt; 1000. */
  public RobotStatePublisherOptions setPublishFrequency(final double publishFrequency) {
    this.publishFrequency = publishFrequency;
    return this;
  }

  public boolean isIgnoreTimestamp() {
    return this.ignoreTimestamp;
  }

  /** When true, joint_states are accepted regardless of their timestamp. */
  public RobotStatePublisherOptions setIgnoreTimestamp(final boolean ignoreTimestamp) {
    this.ignoreTimestamp = ignoreTimestamp;
    return this;
  }

  public String getFramePrefix() {
    return this.framePrefix;
  }

  /**
   * Prepended to every published frame id. Include the trailing separator yourself, e.g.
   * {@code "mavic_0/"} -- the node concatenates without inserting one.
   */
  public RobotStatePublisherOptions setFramePrefix(final String framePrefix) {
    this.framePrefix = framePrefix;
    return this;
  }

  public String getNodeName() {
    return this.nodeName;
  }

  /**
   * Node name. The upstream node hardcodes "robot_state_publisher", so this is applied as a
   * {@code __node} remapping rather than a constructor argument.
   */
  public RobotStatePublisherOptions setNodeName(final String nodeName) {
    this.nodeName = nodeName;
    return this;
  }

  public String getNamespace() {
    return this.namespace;
  }

  /** Node namespace, e.g. {@code "/mavic_0"}. Applied as a {@code __ns} remapping. */
  public RobotStatePublisherOptions setNamespace(final String namespace) {
    this.namespace = namespace;
    return this;
  }

  public String[] getRosArguments() {
    return this.rosArguments;
  }

  /**
   * Extra arguments passed through to ROS at context initialisation, before the node name and
   * namespace remappings are appended. Never null; use an empty array for none.
   */
  public RobotStatePublisherOptions setRosArguments(final String[] rosArguments) {
    this.rosArguments = rosArguments == null ? new String[0] : rosArguments;
    return this;
  }
}
