import jpype

# Retrieve the path to the default JVM shared library
jvm_path = jpype.getDefaultJVMPath()
print(f"Default JVM Path: {jvm_path}")

# Start the JVM using the default path automatically
jpype.startJVM()
