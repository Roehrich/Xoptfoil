@echo on

set Profil=EE-CF-Test

call "C:\Program Files\Anaconda3\Scripts\activate.bat"
python E:\Git\Xoptfoil-JX-EE\Xoptfoil\windows\bin\xoptfoil_visualizer-jx.py -c %Profil% -o 3


pause >nul