import os
import subprocess
import shutil

class OCRProvider:
    @staticmethod
    def get_tesseract_path():
        if "TESSERACT_CMD" in os.environ:
            return os.environ["TESSERACT_CMD"]
        tess = shutil.which("tesseract")
        if tess:
            return tess
        
        common_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Users\ashwi\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
        ]
        for p in common_paths:
            if os.path.exists(p):
                return p
        return None

    @staticmethod
    def perform_ocr(image_path: str) -> str:
        tess_path = OCRProvider.get_tesseract_path()
        if not tess_path:
            return "OCR is unavailable because Tesseract is not installed."
            
        try:
            res = subprocess.run([tess_path, image_path, "stdout"], capture_output=True, text=True)
            return res.stdout.strip()
        except Exception as e:
            return f"OCR is unavailable: {e}"
