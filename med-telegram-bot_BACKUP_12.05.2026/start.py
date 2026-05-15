import os, sys, subprocess

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
print("Starting MedAssistant Bot...")
print(f"Working directory: {script_dir}")
print()

proc = subprocess.Popen([sys.executable, "-m", "bot.main"], cwd=script_dir)
proc.wait()
