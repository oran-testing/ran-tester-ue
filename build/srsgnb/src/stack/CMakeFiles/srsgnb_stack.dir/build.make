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
include srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/compiler_depend.make

# Include the progress variables for this target.
include srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/progress.make

# Include the compile flags for this target's objects.
include srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/flags.make

srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/gnb_stack_nr.cc.o: srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/flags.make
srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/gnb_stack_nr.cc.o: ../srsgnb/src/stack/gnb_stack_nr.cc
srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/gnb_stack_nr.cc.o: srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/compiler_depend.ts
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --progress-dir=/home/ntia/soft-t-ue/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Building CXX object srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/gnb_stack_nr.cc.o"
	cd /home/ntia/soft-t-ue/build/srsgnb/src/stack && /usr/bin/ccache /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -MD -MT srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/gnb_stack_nr.cc.o -MF CMakeFiles/srsgnb_stack.dir/gnb_stack_nr.cc.o.d -o CMakeFiles/srsgnb_stack.dir/gnb_stack_nr.cc.o -c /home/ntia/soft-t-ue/srsgnb/src/stack/gnb_stack_nr.cc

srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/gnb_stack_nr.cc.i: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green "Preprocessing CXX source to CMakeFiles/srsgnb_stack.dir/gnb_stack_nr.cc.i"
	cd /home/ntia/soft-t-ue/build/srsgnb/src/stack && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -E /home/ntia/soft-t-ue/srsgnb/src/stack/gnb_stack_nr.cc > CMakeFiles/srsgnb_stack.dir/gnb_stack_nr.cc.i

srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/gnb_stack_nr.cc.s: cmake_force
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green "Compiling CXX source to assembly CMakeFiles/srsgnb_stack.dir/gnb_stack_nr.cc.s"
	cd /home/ntia/soft-t-ue/build/srsgnb/src/stack && /usr/bin/c++ $(CXX_DEFINES) $(CXX_INCLUDES) $(CXX_FLAGS) -S /home/ntia/soft-t-ue/srsgnb/src/stack/gnb_stack_nr.cc -o CMakeFiles/srsgnb_stack.dir/gnb_stack_nr.cc.s

# Object files for target srsgnb_stack
srsgnb_stack_OBJECTS = \
"CMakeFiles/srsgnb_stack.dir/gnb_stack_nr.cc.o"

# External object files for target srsgnb_stack
srsgnb_stack_EXTERNAL_OBJECTS =

srsgnb/src/stack/libsrsgnb_stack.a: srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/gnb_stack_nr.cc.o
srsgnb/src/stack/libsrsgnb_stack.a: srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/build.make
srsgnb/src/stack/libsrsgnb_stack.a: srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --bold --progress-dir=/home/ntia/soft-t-ue/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_2) "Linking CXX static library libsrsgnb_stack.a"
	cd /home/ntia/soft-t-ue/build/srsgnb/src/stack && $(CMAKE_COMMAND) -P CMakeFiles/srsgnb_stack.dir/cmake_clean_target.cmake
	cd /home/ntia/soft-t-ue/build/srsgnb/src/stack && $(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/srsgnb_stack.dir/link.txt --verbose=$(VERBOSE)

# Rule to build all files generated by this target.
srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/build: srsgnb/src/stack/libsrsgnb_stack.a
.PHONY : srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/build

srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/clean:
	cd /home/ntia/soft-t-ue/build/srsgnb/src/stack && $(CMAKE_COMMAND) -P CMakeFiles/srsgnb_stack.dir/cmake_clean.cmake
.PHONY : srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/clean

srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/depend:
	cd /home/ntia/soft-t-ue/build && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/ntia/soft-t-ue /home/ntia/soft-t-ue/srsgnb/src/stack /home/ntia/soft-t-ue/build /home/ntia/soft-t-ue/build/srsgnb/src/stack /home/ntia/soft-t-ue/build/srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/DependInfo.cmake --color=$(COLOR)
.PHONY : srsgnb/src/stack/CMakeFiles/srsgnb_stack.dir/depend

