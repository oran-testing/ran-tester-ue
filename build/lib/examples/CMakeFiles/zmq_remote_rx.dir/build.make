# CMAKE generated file: DO NOT EDIT!
# Generated by "Unix Makefiles" Generator, CMake Version 3.22

# Delete rule output on recipe failure.
.DELETE_ON_ERROR:

#=============================================================================
# Special targets provided by cmake.

# Disable implicit rules so canonical targets will work.
.SUFFIXES:

# Disable VCS-based implicit rules.
% : %,v

# Disable VCS-based implicit rules.
% : RCS/%

# Disable VCS-based implicit rules.
% : RCS/%,v

# Disable VCS-based implicit rules.
% : SCCS/s.%

# Disable VCS-based implicit rules.
% : s.%

.SUFFIXES: .hpux_make_needs_suffix_list

# Command-line flag to silence nested $(MAKE).
$(VERBOSE)MAKESILENT = -s

#Suppress display of executed commands.
$(VERBOSE).SILENT:

# A target that is always out of date.
cmake_force:
.PHONY : cmake_force

#=============================================================================
# Set environment variables for the build.

# The shell in which to execute make rules.
SHELL = /bin/sh

# The CMake executable.
CMAKE_COMMAND = /usr/bin/cmake

# The command to remove a file.
RM = /usr/bin/cmake -E rm -f

# Escaping for special characters.
EQUALS = =

# The top-level source directory on which CMake was run.
CMAKE_SOURCE_DIR = /home/ntia/soft-t-ue

# The top-level build directory on which CMake was run.
CMAKE_BINARY_DIR = /home/ntia/soft-t-ue/build

# Include any dependencies generated for this target.
include lib/examples/CMakeFiles/zmq_remote_rx.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include lib/examples/CMakeFiles/zmq_remote_rx.dir/compiler_depend.make

# Include the progress variables for this target.
include lib/examples/CMakeFiles/zmq_remote_rx.dir/progress.make

# Include the compile flags for this target's objects.
include lib/examples/CMakeFiles/zmq_remote_rx.dir/flags.make

lib/examples/CMakeFiles/zmq_remote_rx.dir/zmq_remote_rx.c.o: lib/examples/CMakeFiles/zmq_remote_rx.dir/flags.make
lib/examples/CMakeFiles/zmq_remote_rx.dir/zmq_remote_rx.c.o: ../lib/examples/zmq_remote_rx.c
lib/examples/CMakeFiles/zmq_remote_rx.dir/zmq_remote_rx.c.o: lib/examples/CMakeFiles/zmq_remote_rx.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --progress-dir=/home/ntia/soft-t-ue/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building C object lib/examples/CMakeFiles/zmq_remote_rx.dir/zmq_remote_rx.c.o"
	cd /home/ntia/soft-t-ue/build/lib/examples && /usr/bin/ccache /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -MD -MT lib/examples/CMakeFiles/zmq_remote_rx.dir/zmq_remote_rx.c.o -MF CMakeFiles/zmq_remote_rx.dir/zmq_remote_rx.c.o.d -o CMakeFiles/zmq_remote_rx.dir/zmq_remote_rx.c.o -c /home/ntia/soft-t-ue/lib/examples/zmq_remote_rx.c

lib/examples/CMakeFiles/zmq_remote_rx.dir/zmq_remote_rx.c.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green "Preprocessing C source to CMakeFiles/zmq_remote_rx.dir/zmq_remote_rx.c.i"
	cd /home/ntia/soft-t-ue/build/lib/examples && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -E /home/ntia/soft-t-ue/lib/examples/zmq_remote_rx.c > CMakeFiles/zmq_remote_rx.dir/zmq_remote_rx.c.i

lib/examples/CMakeFiles/zmq_remote_rx.dir/zmq_remote_rx.c.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green "Compiling C source to assembly CMakeFiles/zmq_remote_rx.dir/zmq_remote_rx.c.s"
	cd /home/ntia/soft-t-ue/build/lib/examples && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -S /home/ntia/soft-t-ue/lib/examples/zmq_remote_rx.c -o CMakeFiles/zmq_remote_rx.dir/zmq_remote_rx.c.s

# Object files for target zmq_remote_rx
zmq_remote_rx_OBJECTS = \
"CMakeFiles/zmq_remote_rx.dir/zmq_remote_rx.c.o"

# External object files for target zmq_remote_rx
zmq_remote_rx_EXTERNAL_OBJECTS =

lib/examples/zmq_remote_rx: lib/examples/CMakeFiles/zmq_remote_rx.dir/zmq_remote_rx.c.o
lib/examples/zmq_remote_rx: lib/examples/CMakeFiles/zmq_remote_rx.dir/build.make
lib/examples/zmq_remote_rx: lib/src/phy/libsrsran_phy.a
lib/examples/zmq_remote_rx: lib/src/phy/rf/libsrsran_rf.so.23.04.0
lib/examples/zmq_remote_rx: /usr/local/lib/libzmq.so
lib/examples/zmq_remote_rx: lib/src/phy/rf/libsrsran_rf_utils.a
lib/examples/zmq_remote_rx: lib/src/phy/libsrsran_phy.a
lib/examples/zmq_remote_rx: /usr/lib/x86_64-linux-gnu/libfftw3f.so
lib/examples/zmq_remote_rx: lib/examples/CMakeFiles/zmq_remote_rx.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --bold --progress-dir=/home/ntia/soft-t-ue/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Linking CXX executable zmq_remote_rx"
	cd /home/ntia/soft-t-ue/build/lib/examples && $(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/zmq_remote_rx.dir/link.txt --verbose=$(VERBOSE)

# Rule to build all files generated by this target.
lib/examples/CMakeFiles/zmq_remote_rx.dir/build: lib/examples/zmq_remote_rx
.PHONY : lib/examples/CMakeFiles/zmq_remote_rx.dir/build

lib/examples/CMakeFiles/zmq_remote_rx.dir/clean:
	cd /home/ntia/soft-t-ue/build/lib/examples && $(CMAKE_COMMAND) -P CMakeFiles/zmq_remote_rx.dir/cmake_clean.cmake
.PHONY : lib/examples/CMakeFiles/zmq_remote_rx.dir/clean

lib/examples/CMakeFiles/zmq_remote_rx.dir/depend:
	cd /home/ntia/soft-t-ue/build && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/ntia/soft-t-ue /home/ntia/soft-t-ue/lib/examples /home/ntia/soft-t-ue/build /home/ntia/soft-t-ue/build/lib/examples /home/ntia/soft-t-ue/build/lib/examples/CMakeFiles/zmq_remote_rx.dir/DependInfo.cmake --color=$(COLOR)
.PHONY : lib/examples/CMakeFiles/zmq_remote_rx.dir/depend

