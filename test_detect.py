import requests
from PIL import Image
import io

img = Image.new('RGB', (100, 100), color = 'green')
buf = io.BytesIO()
img.save(buf, format='JPEG')
buf.seek(0)

try:
    res = requests.post("http://127.0.0.1:5000/api/detect", files={"image": ("test.jpg", buf, "image/jpeg")})
    print("Status code:", res.status_code)
    print("Response:", res.text)
except Exception as e:
    print("Error:", e)
