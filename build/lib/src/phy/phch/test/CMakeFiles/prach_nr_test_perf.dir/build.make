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
include lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/compiler_depend.make

# Include the progress variables for this target.
include lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/progress.make

# Include the compile flags for this target's objects.
include lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/flags.make

lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/prach_nr_test_perf.c.o: lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/flags.make
lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/prach_nr_test_perf.c.o: ../lib/src/phy/phch/test/prach_nr_test_perf.c
lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/prach_nr_test_perf.c.o: lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --progress-dir=/home/ntia/soft-t-ue/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building C object lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/prach_nr_test_perf.c.o"
	cd /home/ntia/soft-t-ue/build/lib/src/phy/phch/test && /usr/bin/ccache /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -MD -MT lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/prach_nr_test_perf.c.o -MF CMakeFiles/prach_nr_test_perf.dir/prach_nr_test_perf.c.o.d -o CMakeFiles/prach_nr_test_perf.dir/prach_nr_test_perf.c.o -c /home/ntia/soft-t-ue/lib/src/phy/phch/test/prach_nr_test_perf.c

lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/prach_nr_test_perf.c.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green "Preprocessing C source to CMakeFiles/prach_nr_test_perf.dir/prach_nr_test_perf.c.i"
	cd /home/ntia/soft-t-ue/build/lib/src/phy/phch/test && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -E /home/ntia/soft-t-ue/lib/src/phy/phch/test/prach_nr_test_perf.c > CMakeFiles/prach_nr_test_perf.dir/prach_nr_test_perf.c.i

lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/prach_nr_test_perf.c.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green "Compiling C source to assembly CMakeFiles/prach_nr_test_perf.dir/prach_nr_test_perf.c.s"
	cd /home/ntia/soft-t-ue/build/lib/src/phy/phch/test && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -S /home/ntia/soft-t-ue/lib/src/phy/phch/test/prach_nr_test_perf.c -o CMakeFiles/prach_nr_test_perf.dir/prach_nr_test_perf.c.s

# Object files for target prach_nr_test_perf
prach_nr_test_perf_OBJECTS = \
"CMakeFiles/prach_nr_test_perf.dir/prach_nr_test_perf.c.o"

# External object files for target prach_nr_test_perf
prach_nr_test_perf_EXTERNAL_OBJECTS =

lib/src/phy/phch/test/prach_nr_test_perf: lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/prach_nr_test_perf.c.o
lib/src/phy/phch/test/prach_nr_test_perf: lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/build.make
lib/src/phy/phch/test/prach_nr_test_perf: lib/src/phy/libsrsran_phy.a
lib/src/phy/phch/test/prach_nr_test_perf: /usr/lib/x86_64-linux-gnu/libfftw3f.so
lib/src/phy/phch/test/prach_nr_test_perf: lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --bold --progress-dir=/home/ntia/soft-t-ue/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Linking CXX executable prach_nr_test_perf"
	cd /home/ntia/soft-t-ue/build/lib/src/phy/phch/test && $(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/prach_nr_test_perf.dir/link.txt --verbose=$(VERBOSE)

# Rule to build all files generated by this target.
lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/build: lib/src/phy/phch/test/prach_nr_test_perf
.PHONY : lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/build

lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/clean:
	cd /home/ntia/soft-t-ue/build/lib/src/phy/phch/test && $(CMAKE_COMMAND) -P CMakeFiles/prach_nr_test_perf.dir/cmake_clean.cmake
.PHONY : lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/clean

lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/depend:
	cd /home/ntia/soft-t-ue/build && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/ntia/soft-t-ue /home/ntia/soft-t-ue/lib/src/phy/phch/test /home/ntia/soft-t-ue/build /home/ntia/soft-t-ue/build/lib/src/phy/phch/test /home/ntia/soft-t-ue/build/lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/DependInfo.cmake --color=$(COLOR)
.PHONY : lib/src/phy/phch/test/CMakeFiles/prach_nr_test_perf.dir/depend

