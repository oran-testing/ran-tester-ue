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
include srsenb/test/upper/CMakeFiles/plmn_test.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include srsenb/test/upper/CMakeFiles/plmn_test.dir/compiler_depend.make

# Include the progress variables for this target.
include srsenb/test/upper/CMakeFiles/plmn_test.dir/progress.make

# Include the compile flags for this target's objects.
include srsenb/test/upper/CMakeFiles/plmn_test.dir/flags.make

srsenb/test/upper/CMakeFiles/plmn_test.dir/plmn_test.cc.o: srsenb/test/upper/CMakeFiles/plmn_test.dir/flags.make
srsenb/test/upper/CMakeFiles/plmn_test.dir/plmn_test.cc.o: ../srsenb/test/upper/plmn_test.cc
srsenb/test/upper/CMakeFiles/plmn_test.dir/plmn_test.cc.o: srsenb/test/upper/CMakeFiles/plmn_test.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --progress-dir=/home/ntia/soft-t-ue/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building CXX object srsenb/test/upper/CMakeFiles/plmn_test.dir/plmn_test.cc.o"
	cd /home/ntia/soft-t-ue/build/srsenb/test/upper && /usr/bin/ccache /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -MD -MT srsenb/test/upper/CMakeFiles/plmn_test.dir/plmn_test.cc.o -MF CMakeFiles/plmn_test.dir/plmn_test.cc.o.d -o CMakeFiles/plmn_test.dir/plmn_test.cc.o -c /home/ntia/soft-t-ue/srsenb/test/upper/plmn_test.cc

srsenb/test/upper/CMakeFiles/plmn_test.dir/plmn_test.cc.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green "Preprocessing CXX source to CMakeFiles/plmn_test.dir/plmn_test.cc.i"
	cd /home/ntia/soft-t-ue/build/srsenb/test/upper && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -E /home/ntia/soft-t-ue/srsenb/test/upper/plmn_test.cc > CMakeFiles/plmn_test.dir/plmn_test.cc.i

srsenb/test/upper/CMakeFiles/plmn_test.dir/plmn_test.cc.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green "Compiling CXX source to assembly CMakeFiles/plmn_test.dir/plmn_test.cc.s"
	cd /home/ntia/soft-t-ue/build/srsenb/test/upper && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -S /home/ntia/soft-t-ue/srsenb/test/upper/plmn_test.cc -o CMakeFiles/plmn_test.dir/plmn_test.cc.s

# Object files for target plmn_test
plmn_test_OBJECTS = \
"CMakeFiles/plmn_test.dir/plmn_test.cc.o"

# External object files for target plmn_test
plmn_test_EXTERNAL_OBJECTS =

srsenb/test/upper/plmn_test: srsenb/test/upper/CMakeFiles/plmn_test.dir/plmn_test.cc.o
srsenb/test/upper/plmn_test: srsenb/test/upper/CMakeFiles/plmn_test.dir/build.make
srsenb/test/upper/plmn_test: lib/src/asn1/librrc_asn1.a
srsenb/test/upper/plmn_test: lib/src/asn1/libasn1_utils.a
srsenb/test/upper/plmn_test: lib/src/common/libsrsran_common.a
srsenb/test/upper/plmn_test: lib/src/phy/libsrsran_phy.a
srsenb/test/upper/plmn_test: /usr/lib/x86_64-linux-gnu/libfftw3f.so
srsenb/test/upper/plmn_test: lib/src/support/libsupport.a
srsenb/test/upper/plmn_test: lib/src/srslog/libsrslog.a
srsenb/test/upper/plmn_test: /usr/lib/x86_64-linux-gnu/libmbedcrypto.so
srsenb/test/upper/plmn_test: srsenb/test/upper/CMakeFiles/plmn_test.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --bold --progress-dir=/home/ntia/soft-t-ue/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Linking CXX executable plmn_test"
	cd /home/ntia/soft-t-ue/build/srsenb/test/upper && $(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/plmn_test.dir/link.txt --verbose=$(VERBOSE)

# Rule to build all files generated by this target.
srsenb/test/upper/CMakeFiles/plmn_test.dir/build: srsenb/test/upper/plmn_test
.PHONY : srsenb/test/upper/CMakeFiles/plmn_test.dir/build

srsenb/test/upper/CMakeFiles/plmn_test.dir/clean:
	cd /home/ntia/soft-t-ue/build/srsenb/test/upper && $(CMAKE_COMMAND) -P CMakeFiles/plmn_test.dir/cmake_clean.cmake
.PHONY : srsenb/test/upper/CMakeFiles/plmn_test.dir/clean

srsenb/test/upper/CMakeFiles/plmn_test.dir/depend:
	cd /home/ntia/soft-t-ue/build && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/ntia/soft-t-ue /home/ntia/soft-t-ue/srsenb/test/upper /home/ntia/soft-t-ue/build /home/ntia/soft-t-ue/build/srsenb/test/upper /home/ntia/soft-t-ue/build/srsenb/test/upper/CMakeFiles/plmn_test.dir/DependInfo.cmake --color=$(COLOR)
.PHONY : srsenb/test/upper/CMakeFiles/plmn_test.dir/depend

