from PIL import Image

try:
    import numpy as np
    import cv2
except Exception:  # pragma: no cover
    np = None
    cv2 = None


def remove_watermark_heuristic(img: Image.Image) -> Image.Image:
    if cv2 is None or np is None:
        return img
    try:
        arr = np.array(img)
        gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 80, 180)
        kernel = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=1)
        inpainted = cv2.inpaint(arr, dilated, 3, cv2.INPAINT_TELEA)
        return Image.fromarray(inpainted)
    except Exception:
        return img
