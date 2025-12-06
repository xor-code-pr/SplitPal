@echo off
call "C:\MyFiles\PythonEnv\.splitpal-env\Scripts\activate.bat"
func host start --address 0.0.0.0 --port 7071 --cors "*"
