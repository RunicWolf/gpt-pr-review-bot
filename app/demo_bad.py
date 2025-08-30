import subprocess

def bad():
    password = "hardcoded"  # gpt bot should flag this
    subprocess.run("rm -rf /", shell=True)  # gpt bot should flag this
