from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, filename):
    img = Image.new('RGB', (size, size), color = (20, 20, 20))
    d = ImageDraw.Draw(img)
    text = "J"
    # Simple centered text
    # Assuming default font if segoe ui fails
    try:
        font = ImageFont.truetype("arial.ttf", int(size * 0.6))
    except:
        font = ImageFont.load_default()
    
    # get text bounding box
    bbox = d.textbbox((0,0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    x = (size - w) / 2
    y = (size - h) / 2 - bbox[1]
    d.text((x, y), text, fill=(255, 255, 255), font=font)
    
    img.save(filename)

os.makedirs('dist/msix_content/Assets', exist_ok=True)
create_icon(150, 'dist/msix_content/Assets/Square150x150Logo.png')
create_icon(44, 'dist/msix_content/Assets/Square44x44Logo.png')
os.makedirs('dist/msix_content/Public', exist_ok=True)
