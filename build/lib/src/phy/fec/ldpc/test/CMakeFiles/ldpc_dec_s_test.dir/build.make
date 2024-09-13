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
include lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/compiler_depend.make

# Include the progress variables for this target.
include lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/progress.make

# Include the compile flags for this target's objects.
include lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/flags.make

lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/ldpc_dec_s_test.c.o: lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/flags.make
lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/ldpc_dec_s_test.c.o: ../lib/src/phy/fec/ldpc/test/ldpc_dec_s_test.c
lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/ldpc_dec_s_test.c.o: lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --progress-dir=/home/prab/soft-t-ue/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building C object lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/ldpc_dec_s_test.c.o"
	cd /home/prab/soft-t-ue/build/lib/src/phy/fec/ldpc/test && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -MD -MT lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/ldpc_dec_s_test.c.o -MF CMakeFiles/ldpc_dec_s_test.dir/ldpc_dec_s_test.c.o.d -o CMakeFiles/ldpc_dec_s_test.dir/ldpc_dec_s_test.c.o -c /home/prab/soft-t-ue/lib/src/phy/fec/ldpc/test/ldpc_dec_s_test.c

lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/ldpc_dec_s_test.c.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green "Preprocessing C source to CMakeFiles/ldpc_dec_s_test.dir/ldpc_dec_s_test.c.i"
	cd /home/prab/soft-t-ue/build/lib/src/phy/fec/ldpc/test && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -E /home/prab/soft-t-ue/lib/src/phy/fec/ldpc/test/ldpc_dec_s_test.c > CMakeFiles/ldpc_dec_s_test.dir/ldpc_dec_s_test.c.i

lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/ldpc_dec_s_test.c.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green "Compiling C source to assembly CMakeFiles/ldpc_dec_s_test.dir/ldpc_dec_s_test.c.s"
	cd /home/prab/soft-t-ue/build/lib/src/phy/fec/ldpc/test && /usr/bin/cc $(C_DEFINES) $(C_INCLUDES) $(C_FLAGS) -S /home/prab/soft-t-ue/lib/src/phy/fec/ldpc/test/ldpc_dec_s_test.c -o CMakeFiles/ldpc_dec_s_test.dir/ldpc_dec_s_test.c.s

# Object files for target ldpc_dec_s_test
ldpc_dec_s_test_OBJECTS = \
"CMakeFiles/ldpc_dec_s_test.dir/ldpc_dec_s_test.c.o"

# External object files for target ldpc_dec_s_test
ldpc_dec_s_test_EXTERNAL_OBJECTS =

lib/src/phy/fec/ldpc/test/ldpc_dec_s_test: lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/ldpc_dec_s_test.c.o
lib/src/phy/fec/ldpc/test/ldpc_dec_s_test: lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/build.make
lib/src/phy/fec/ldpc/test/ldpc_dec_s_test: lib/src/phy/libsrsran_phy.a
lib/src/phy/fec/ldpc/test/ldpc_dec_s_test: /usr/lib/x86_64-linux-gnu/libfftw3f.so
lib/src/phy/fec/ldpc/test/ldpc_dec_s_test: lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --bold --progress-dir=/home/prab/soft-t-ue/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Linking CXX executable ldpc_dec_s_test"
	cd /home/prab/soft-t-ue/build/lib/src/phy/fec/ldpc/test && $(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/ldpc_dec_s_test.dir/link.txt --verbose=$(VERBOSE)

# Rule to build all files generated by this target.
lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/build: lib/src/phy/fec/ldpc/test/ldpc_dec_s_test
.PHONY : lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/build

lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/clean:
	cd /home/prab/soft-t-ue/build/lib/src/phy/fec/ldpc/test && $(CMAKE_COMMAND) -P CMakeFiles/ldpc_dec_s_test.dir/cmake_clean.cmake
.PHONY : lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/clean

lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/depend:
	cd /home/prab/soft-t-ue/build && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/prab/soft-t-ue /home/prab/soft-t-ue/lib/src/phy/fec/ldpc/test /home/prab/soft-t-ue/build /home/prab/soft-t-ue/build/lib/src/phy/fec/ldpc/test /home/prab/soft-t-ue/build/lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/DependInfo.cmake --color=$(COLOR)
.PHONY : lib/src/phy/fec/ldpc/test/CMakeFiles/ldpc_dec_s_test.dir/depend

