import base64

file = "temp.png"

with open(file, "rb") as img_file:
    b64_string = base64.b64encode(img_file.read()).decode('utf-8')
    print(b64_string)