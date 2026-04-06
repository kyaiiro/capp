import base64, subprocess

file = "server.png"

with open(file, "rb") as img_file:
    b64_string = base64.b64encode(img_file.read()).decode('utf-8')
    subprocess.getoutput(f"echo {b64_string} >> img.txt")