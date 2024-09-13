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
CMAKE_SOURCE_DIR = /home/prab/soft-t-ue

# The top-level build directory on which CMake was run.
CMAKE_BINARY_DIR = /home/prab/soft-t-ue/build

# Include any dependencies generated for this target.
include lib/examples/CMakeFiles/usrp_capture.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include lib/examples/CMakeFiles/usrp_capture.dir/compiler_depend.make

# Include the progress variables for this target.
include lib/examples/CMakeFiles/usrp_capture.dir/progress.make

# Include the compile flags for this target's objects.
include lib/examples/CMakeFiles/usrp_capture.dir/flags.make

lib/examples/CMakeFiles/usrp_capture.dir/usrp_capture.c.o: lib/examples/CMakeFiles/usrp_capture.dir/flags.make
lib/examples/CMakeFiles/usrp_capture.dir/usrp_capture.c.o: ../lib/examples/usrp_capture.c
lib/examples/CMakeFiles/usrp_capture.dir/usrp_capture.c.o: lib/examples/CMakeFiles/usrp_capture.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --progress-dir=/home/prab/soft-t-ue/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building C object lib/examples/CMakeFiles/usrp_capture.dir/usrp_capture.c.o"
	cd /home/prab/soft-t-ue/build/lib/examples && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -MD -MT lib/examples/CMakeFiles/usrp_capture.dir/usrp_capture.c.o -MF CMakeFiles/usrp_capture.dir/usrp_capture.c.o.d -o CMakeFiles/usrp_capture.dir/usrp_capture.c.o -c /home/prab/soft-t-ue/lib/examples/usrp_capture.c

lib/examples/CMakeFiles/usrp_capture.dir/usrp_capture.c.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green "Preprocessing C source to CMakeFiles/usrp_capture.dir/usrp_capture.c.i"
	cd /home/prab/soft-t-ue/build/lib/examples && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -E /home/prab/soft-t-ue/lib/examples/usrp_capture.c > CMakeFiles/usrp_capture.dir/usrp_capture.c.i

lib/examples/CMakeFiles/usrp_capture.dir/usrp_capture.c.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green "Compiling C source to assembly CMakeFiles/usrp_capture.dir/usrp_capture.c.s"
	cd /home/prab/soft-t-ue/build/lib/examples && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -S /home/prab/soft-t-ue/lib/examples/usrp_capture.c -o CMakeFiles/usrp_capture.dir/usrp_capture.c.s

# Object files for target usrp_capture
usrp_capture_OBJECTS = \
"CMakeFiles/usrp_capture.dir/usrp_capture.c.o"

# External object files for target usrp_capture
usrp_capture_EXTERNAL_OBJECTS =

lib/examples/usrp_capture: lib/examples/CMakeFiles/usrp_capture.dir/usrp_capture.c.o
lib/examples/usrp_capture: lib/examples/CMakeFiles/usrp_capture.dir/build.make
lib/examples/usrp_capture: lib/src/phy/libsrsran_phy.a
lib/examples/usrp_capture: lib/src/phy/rf/libsrsran_rf.so.23.04.0
lib/examples/usrp_capture: lib/src/phy/rf/libsrsran_rf_utils.a
lib/examples/usrp_capture: lib/src/phy/libsrsran_phy.a
lib/examples/usrp_capture: /usr/lib/x86_64-linux-gnu/libfftw3f.so
lib/examples/usrp_capture: lib/examples/CMakeFiles/usrp_capture.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --bold --progress-dir=/home/prab/soft-t-ue/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Linking CXX executable usrp_capture"
	cd /home/prab/soft-t-ue/build/lib/examples && $(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/usrp_capture.dir/link.txt --verbose=$(VERBOSE)

# Rule to build all files generated by this target.
lib/examples/CMakeFiles/usrp_capture.dir/build: lib/examples/usrp_capture
.PHONY : lib/examples/CMakeFiles/usrp_capture.dir/build

lib/examples/CMakeFiles/usrp_capture.dir/clean:
	cd /home/prab/soft-t-ue/build/lib/examples && $(CMAKE_COMMAND) -P CMakeFiles/usrp_capture.dir/cmake_clean.cmake
.PHONY : lib/examples/CMakeFiles/usrp_capture.dir/clean

lib/examples/CMakeFiles/usrp_capture.dir/depend:
	cd /home/prab/soft-t-ue/build && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/prab/soft-t-ue /home/prab/soft-t-ue/lib/examples /home/prab/soft-t-ue/build /home/prab/soft-t-ue/build/lib/examples /home/prab/soft-t-ue/build/lib/examples/CMakeFiles/usrp_capture.dir/DependInfo.cmake --color=$(COLOR)
.PHONY : lib/examples/CMakeFiles/usrp_capture.dir/depend

