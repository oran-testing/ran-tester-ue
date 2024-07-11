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
include lib/src/phy/rf/CMakeFiles/srsran_rf.dir/depend.make
# Include any dependencies generated by the compiler for this target.
include lib/src/phy/rf/CMakeFiles/srsran_rf.dir/compiler_depend.make

# Include the progress variables for this target.
include lib/src/phy/rf/CMakeFiles/srsran_rf.dir/progress.make

# Include the compile flags for this target's objects.
include lib/src/phy/rf/CMakeFiles/srsran_rf.dir/flags.make

# Object files for target srsran_rf
srsran_rf_OBJECTS =

# External object files for target srsran_rf
srsran_rf_EXTERNAL_OBJECTS = \
"/home/ntia/soft-t-ue/build/lib/src/phy/rf/CMakeFiles/srsran_rf_object.dir/rf_imp.c.o" \
"/home/ntia/soft-t-ue/build/lib/src/phy/rf/CMakeFiles/srsran_rf_object.dir/rf_file_imp.c.o" \
"/home/ntia/soft-t-ue/build/lib/src/phy/rf/CMakeFiles/srsran_rf_object.dir/rf_file_imp_tx.c.o" \
"/home/ntia/soft-t-ue/build/lib/src/phy/rf/CMakeFiles/srsran_rf_object.dir/rf_file_imp_rx.c.o"

lib/src/phy/rf/libsrsran_rf.so.23.04.0: lib/src/phy/rf/CMakeFiles/srsran_rf_object.dir/rf_imp.c.o
lib/src/phy/rf/libsrsran_rf.so.23.04.0: lib/src/phy/rf/CMakeFiles/srsran_rf_object.dir/rf_file_imp.c.o
lib/src/phy/rf/libsrsran_rf.so.23.04.0: lib/src/phy/rf/CMakeFiles/srsran_rf_object.dir/rf_file_imp_tx.c.o
lib/src/phy/rf/libsrsran_rf.so.23.04.0: lib/src/phy/rf/CMakeFiles/srsran_rf_object.dir/rf_file_imp_rx.c.o
lib/src/phy/rf/libsrsran_rf.so.23.04.0: lib/src/phy/rf/CMakeFiles/srsran_rf.dir/build.make
lib/src/phy/rf/libsrsran_rf.so.23.04.0: lib/src/phy/rf/libsrsran_rf_utils.a
lib/src/phy/rf/libsrsran_rf.so.23.04.0: lib/src/phy/libsrsran_phy.a
lib/src/phy/rf/libsrsran_rf.so.23.04.0: /usr/lib/x86_64-linux-gnu/libfftw3f.so
lib/src/phy/rf/libsrsran_rf.so.23.04.0: lib/src/phy/rf/CMakeFiles/srsran_rf.dir/link.txt
	@$(CMAKE_COMMAND) -E cmake_echo_color --switch=$(COLOR) --green --bold --progress-dir=/home/ntia/soft-t-ue/build/CMakeFiles --progress-num=$(CMAKE_PROGRESS_1) "Linking CXX shared library libsrsran_rf.so"
	cd /home/ntia/soft-t-ue/build/lib/src/phy/rf && $(CMAKE_COMMAND) -E cmake_link_script CMakeFiles/srsran_rf.dir/link.txt --verbose=$(VERBOSE)
	cd /home/ntia/soft-t-ue/build/lib/src/phy/rf && $(CMAKE_COMMAND) -E cmake_symlink_library libsrsran_rf.so.23.04.0 libsrsran_rf.so.0 libsrsran_rf.so

lib/src/phy/rf/libsrsran_rf.so.0: lib/src/phy/rf/libsrsran_rf.so.23.04.0
	@$(CMAKE_COMMAND) -E touch_nocreate lib/src/phy/rf/libsrsran_rf.so.0

lib/src/phy/rf/libsrsran_rf.so: lib/src/phy/rf/libsrsran_rf.so.23.04.0
	@$(CMAKE_COMMAND) -E touch_nocreate lib/src/phy/rf/libsrsran_rf.so

# Rule to build all files generated by this target.
lib/src/phy/rf/CMakeFiles/srsran_rf.dir/build: lib/src/phy/rf/libsrsran_rf.so
.PHONY : lib/src/phy/rf/CMakeFiles/srsran_rf.dir/build

lib/src/phy/rf/CMakeFiles/srsran_rf.dir/clean:
	cd /home/ntia/soft-t-ue/build/lib/src/phy/rf && $(CMAKE_COMMAND) -P CMakeFiles/srsran_rf.dir/cmake_clean.cmake
.PHONY : lib/src/phy/rf/CMakeFiles/srsran_rf.dir/clean

lib/src/phy/rf/CMakeFiles/srsran_rf.dir/depend:
	cd /home/ntia/soft-t-ue/build && $(CMAKE_COMMAND) -E cmake_depends "Unix Makefiles" /home/ntia/soft-t-ue /home/ntia/soft-t-ue/lib/src/phy/rf /home/ntia/soft-t-ue/build /home/ntia/soft-t-ue/build/lib/src/phy/rf /home/ntia/soft-t-ue/build/lib/src/phy/rf/CMakeFiles/srsran_rf.dir/DependInfo.cmake --color=$(COLOR)
.PHONY : lib/src/phy/rf/CMakeFiles/srsran_rf.dir/depend

