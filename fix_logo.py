from PIL import Image

img = Image.open("lifewise_logo.png").convert("RGBA")
data = img.getdata()

new_data = []
for item in data:
    if item[0] > 240 and item[1] > 240 and item[2] > 240:
        new_data.append((255, 255, 255, 0))
    else:
        new_data.append(item)

img.putdata(new_data)
img.save("lifewise_logo.png", "PNG")
print("Done - background removed")