from PIL import Image

def has_alpha_channel(image_path: str) -> bool:
    try:
        with Image.open(image_path) as img:
            return img.mode in ("RGBA", "LA")
    except:
        return False