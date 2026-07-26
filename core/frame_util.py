"""
Author: Pinar Hazan
Affiliation: Hacettepe University
Year: 2026

Description:
This source code has been developed as part of the thesis titled 
"Optical Tracklet Simulation for Space Surveillance and Tracking". 

Contact: pinarhazan99@gmail.com
"""

from PIL import Image, ImageDraw

def add_frame_to_png(image_path, output_path, color='#FF0000', thickness=5):
    """
    It draws a frame INSIDE the image without changing its size. This preserves the WCS coordinates and Stellarium layout.
    """
    try:
        img = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(img)
        
        width, height = img.size
        
        draw.rectangle([0, 0, width-1, height-1], outline=color, width=thickness)
        
        img.save(output_path)
        print(f"   PNG dosyasına (içe) çerçeve eklendi: {output_path}")

    except Exception as e:
        print(f"   Hata: PNG dosyasına çerçeve eklenemedi. Hata: {e}")