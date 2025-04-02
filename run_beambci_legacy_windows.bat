IF EXIST micromamba\root\envs\beambci\python.exe (
	micromamba\root\envs\beambci\python.exe MainProgram.py
	GOTO exit
)

GOTO errorexit

:errorexit
ECHO ERROR: Can not find python executable.
PAUSE
GOTO exit

:exit