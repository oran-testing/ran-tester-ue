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
include srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/compiler_depend.make

# Include the progress variables for this target.
include srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/progress.make

# Include the compile flags for this target's objects.
include srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/flags.make

srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/tft_test.cc.o: srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/flags.make
srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/tft_test.cc.o: ../srsue/src/stack/upper/test/tft_test.cc
srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/tft_test.cc.o: srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --progress-dir=/home/ntia/soft-t-ue/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building CXX object srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/tft_test.cc.o"
	cd /home/ntia/soft-t-ue/build/srsue/src/stack/upper/test && /usr/bin/ccache /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -MD -MT srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/tft_test.cc.o -MF CMakeFiles/tft_test.dir/tft_test.cc.o.d -o CMakeFiles/tft_test.dir/tft_test.cc.o -c /home/ntia/soft-t-ue/srsue/src/stack/upper/test/tft_test.cc

srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/tft_test.cc.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green "Preprocessing CXX source to CMakeFiles/tft_test.dir/tft_test.cc.i"
	cd /home/ntia/soft-t-ue/build/srsue/src/stack/upper/test && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -E /home/ntia/soft-t-ue/srsue/src/stack/upper/test/tft_test.cc > CMakeFiles/tft_test.dir/tft_test.cc.i

srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/tft_test.cc.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green "Compiling CXX source to assembly CMakeFiles/tft_test.dir/tft_test.cc.s"
	cd /home/ntia/soft-t-ue/build/srsue/src/stack/upper/test && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -S /home/ntia/soft-t-ue/srsue/src/stack/upper/test/tft_test.cc -o CMakeFiles/tft_test.dir/tft_test.cc.s

# Object files for target tft_test
tft_test_OBJECTS = \
"CMakeFiles/tft_test.dir/tft_test.cc.o"

# External object files for target tft_test
tft_test_EXTERNAL_OBJECTS =

srsue/src/stack/upper/test/tft_test: srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/tft_test.cc.o
srsue/src/stack/upper/test/tft_test: srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/build.make
srsue/src/stack/upper/test/tft_test: srsue/src/stack/upper/libsrsue_upper.a
srsue/src/stack/upper/test/tft_test: lib/src/common/libsrsran_common.a
srsue/src/stack/upper/test/tft_test: lib/src/phy/libsrsran_phy.a
srsue/src/stack/upper/test/tft_test: lib/src/asn1/libsrsran_asn1.a
srsue/src/stack/upper/test/tft_test: lib/src/asn1/libnas_5g_msg.a
srsue/src/stack/upper/test/tft_test: lib/src/asn1/libasn1_utils.a
srsue/src/stack/upper/test/tft_test: lib/src/common/libsrsran_common.a
srsue/src/stack/upper/test/tft_test: lib/src/phy/libsrsran_phy.a
srsue/src/stack/upper/test/tft_test: /usr/lib/x86_64-linux-gnu/libfftw3f.so
srsue/src/stack/upper/test/tft_test: lib/src/support/libsupport.a
srsue/src/stack/upper/test/tft_test: lib/src/srslog/libsrslog.a
srsue/src/stack/upper/test/tft_test: /usr/lib/x86_64-linux-gnu/libmbedcrypto.so
srsue/src/stack/upper/test/tft_test: srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --bold --progress-dir=/home/ntia/soft-t-ue/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Linking CXX executable tft_test"
	cd /home/ntia/soft-t-ue/build/srsue/src/stack/upper/test && $(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/tft_test.dir/link.txt --verbose=$(VERBOSE)

# Rule to build all files generated by this target.
srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/build: srsue/src/stack/upper/test/tft_test
.PHONY : srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/build

srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/clean:
	cd /home/ntia/soft-t-ue/build/srsue/src/stack/upper/test && $(CMAKE_COMMAND) -P CMakeFiles/tft_test.dir/cmake_clean.cmake
.PHONY : srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/clean

srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/depend:
	cd /home/ntia/soft-t-ue/build && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/ntia/soft-t-ue /home/ntia/soft-t-ue/srsue/src/stack/upper/test /home/ntia/soft-t-ue/build /home/ntia/soft-t-ue/build/srsue/src/stack/upper/test /home/ntia/soft-t-ue/build/srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/DependInfo.cmake --color=$(COLOR)
.PHONY : srsue/src/stack/upper/test/CMakeFiles/tft_test.dir/depend

