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
include srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/compiler_depend.make

# Include the progress variables for this target.
include srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/progress.make

# Include the compile flags for this target's objects.
include srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/flags.make

srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/sched_benchmark.cc.o: srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/flags.make
srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/sched_benchmark.cc.o: ../srsenb/test/mac/sched_benchmark.cc
srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/sched_benchmark.cc.o: srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --progress-dir=/home/ntia/soft-t-ue/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building CXX object srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/sched_benchmark.cc.o"
	cd /home/ntia/soft-t-ue/build/srsenb/test/mac && /usr/bin/ccache /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -MD -MT srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/sched_benchmark.cc.o -MF CMakeFiles/sched_benchmark_test.dir/sched_benchmark.cc.o.d -o CMakeFiles/sched_benchmark_test.dir/sched_benchmark.cc.o -c /home/ntia/soft-t-ue/srsenb/test/mac/sched_benchmark.cc

srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/sched_benchmark.cc.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green "Preprocessing CXX source to CMakeFiles/sched_benchmark_test.dir/sched_benchmark.cc.i"
	cd /home/ntia/soft-t-ue/build/srsenb/test/mac && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -E /home/ntia/soft-t-ue/srsenb/test/mac/sched_benchmark.cc > CMakeFiles/sched_benchmark_test.dir/sched_benchmark.cc.i

srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/sched_benchmark.cc.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green "Compiling CXX source to assembly CMakeFiles/sched_benchmark_test.dir/sched_benchmark.cc.s"
	cd /home/ntia/soft-t-ue/build/srsenb/test/mac && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -S /home/ntia/soft-t-ue/srsenb/test/mac/sched_benchmark.cc -o CMakeFiles/sched_benchmark_test.dir/sched_benchmark.cc.s

# Object files for target sched_benchmark_test
sched_benchmark_test_OBJECTS = \
"CMakeFiles/sched_benchmark_test.dir/sched_benchmark.cc.o"

# External object files for target sched_benchmark_test
sched_benchmark_test_EXTERNAL_OBJECTS =

srsenb/test/mac/sched_benchmark_test: srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/sched_benchmark.cc.o
srsenb/test/mac/sched_benchmark_test: srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/build.make
srsenb/test/mac/sched_benchmark_test: lib/src/common/libsrsran_common.a
srsenb/test/mac/sched_benchmark_test: srsenb/src/stack/mac/libsrsenb_mac.a
srsenb/test/mac/sched_benchmark_test: lib/src/mac/libsrsran_mac.a
srsenb/test/mac/sched_benchmark_test: srsenb/test/mac/libsched_test_common.a
srsenb/test/mac/sched_benchmark_test: srsenb/src/stack/mac/libsrsenb_mac.a
srsenb/test/mac/sched_benchmark_test: srsenb/src/stack/mac/common/libsrsenb_mac_common.a
srsenb/test/mac/sched_benchmark_test: lib/src/mac/libsrsran_mac.a
srsenb/test/mac/sched_benchmark_test: lib/src/common/libsrsran_common.a
srsenb/test/mac/sched_benchmark_test: lib/src/phy/libsrsran_phy.a
srsenb/test/mac/sched_benchmark_test: /usr/lib/x86_64-linux-gnu/libfftw3f.so
srsenb/test/mac/sched_benchmark_test: lib/src/support/libsupport.a
srsenb/test/mac/sched_benchmark_test: lib/src/srslog/libsrslog.a
srsenb/test/mac/sched_benchmark_test: /usr/lib/x86_64-linux-gnu/libmbedcrypto.so
srsenb/test/mac/sched_benchmark_test: srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --bold --progress-dir=/home/ntia/soft-t-ue/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Linking CXX executable sched_benchmark_test"
	cd /home/ntia/soft-t-ue/build/srsenb/test/mac && $(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/sched_benchmark_test.dir/link.txt --verbose=$(VERBOSE)

# Rule to build all files generated by this target.
srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/build: srsenb/test/mac/sched_benchmark_test
.PHONY : srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/build

srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/clean:
	cd /home/ntia/soft-t-ue/build/srsenb/test/mac && $(CMAKE_COMMAND) -P CMakeFiles/sched_benchmark_test.dir/cmake_clean.cmake
.PHONY : srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/clean

srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/depend:
	cd /home/ntia/soft-t-ue/build && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/ntia/soft-t-ue /home/ntia/soft-t-ue/srsenb/test/mac /home/ntia/soft-t-ue/build /home/ntia/soft-t-ue/build/srsenb/test/mac /home/ntia/soft-t-ue/build/srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/DependInfo.cmake --color=$(COLOR)
.PHONY : srsenb/test/mac/CMakeFiles/sched_benchmark_test.dir/depend

