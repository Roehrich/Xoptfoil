ECHO OFF
SET INSTALLDIR=%CD%\windows
SET XOPTFOIL_VERSION=1.0
SET TARGET_OS=WIN

IF NOT EXIST build        MKDIR build
IF NOT EXIST %INSTALLDIR% MKDIR %INSTALLDIR%

CD build
cmake -G "MinGW Makefiles" ^
  -DCMAKE_INSTALL_PREFIX:PATH=%INSTALLDIR% ^
  -DCMAKE_BUILD_TYPE:STRING="Debug" ^
  ..

mingw32-make VERBOSE=1
mingw32-make install
CD ..