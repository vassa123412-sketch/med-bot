import os, sys, subprocess

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

proc = subprocess.Popen([sys.executable, "-m", "bot.main"], cwd=script_dir)
proc.wait()
