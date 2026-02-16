import cv2
import numpy as np
import easyocr
import re
import os
import traceback
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils.text import get_valid_filename
from .serializers import FileSerializer

# ---------------------------------------------------------
# 1. INITIALIZATION
# ---------------------------------------------------------
# 'en' for English. gpu=False is slower but safer if you don't have CUDA.
print("⏳ Initializing EasyOCR Engine...")
reader = easyocr.Reader(['en'], gpu=False)
print("✅ EasyOCR Ready.")

class OCRView(APIView):
    def strip_extensions(self, filename):
        name = filename
        while True:
            name, ext = os.path.splitext(name)
            if not ext: break
        return name

    # ---------------------------------------------------------
    # 2. PREPROCESSING (Simpler is Better)
    # ---------------------------------------------------------
    def preprocess_handwriting(self, image_path):
        """
        Does NOT remove lines (which deletes text).
        Instead, zooms in so the AI sees boxes as 'borders' not 'text'.
        """
        try:
            img = cv2.imread(image_path)
            if img is None: return None, None

            # Upscale 2.5x: This makes each grid box huge, separating letters clearly
            img = cv2.resize(img, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)

            # Grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Denoise: gentle smoothing to remove paper grain
            denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)

            # Contrast Stretch (Normalizing brightness)
            # This helps if the photo was taken in bad lighting
            norm_img = np.zeros((denoised.shape[0], denoised.shape[1]))
            final_img = cv2.normalize(denoised, norm_img, 0, 255, cv2.NORM_MINMAX)

            # SAVE DEBUG IMAGE (So you can see what the AI sees)
            base_name = self.strip_extensions(os.path.basename(image_path))
            debug_name = f"debug_input_{base_name}.jpg"
            debug_dir = os.path.dirname(image_path)
            debug_path = os.path.join(debug_dir, debug_name)
            cv2.imwrite(debug_path, final_img)
            
            # Construct URL for the frontend
            rel_path = os.path.relpath(debug_path, settings.MEDIA_ROOT)
            debug_url = f"{settings.MEDIA_URL}{rel_path}".replace("\\", "/")

            return final_img, debug_url
        except Exception as e:
            print(f"Error in preprocessing: {e}")
            return None, None

    # ---------------------------------------------------------
    # 3. MAIN LOGIC
    # ---------------------------------------------------------
    def post(self, request, *args, **kwargs):
        serializer = FileSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        # Handle file names
        file_obj = request.FILES['image']
        clean_name = self.strip_extensions(get_valid_filename(file_obj.name))
        file_obj.name = f"{clean_name}.jpg"
        
        try:
            serializer.save()
            img_path = serializer.instance.image.path
            
            # A. PREPROCESS
            processed_img, debug_url = self.preprocess_handwriting(img_path)
            if processed_img is None:
                return Response({"error": "Image processing failed"}, status=500)

            print(f"\n🚀 Scanning: {file_obj.name}")

            # B. EASYOCR INFERENCE (Tuned for Boxed Handwriting)
            results = reader.readtext(
                processed_img,
                detail=1,
                
                # CRITICAL SETTINGS FOR FORMS:
                paragraph=False,      # Treat every box as separate text
                canvas_size=2560,     # Allow processing larger (upscaled) images
                mag_ratio=1.5,        # Zoom in further internally
                
                # SENSITIVITY SETTINGS:
                text_threshold=0.3,   # Lower = detect fainter handwriting
                low_text=0.2,         # Keep low-confidence text (don't discard)
                link_threshold=0.1,   # Don't try to merge text across far-away boxes
                
                # DECODER:
                decoder='greedy'      # 'greedy' is often better for simple block letters than 'beamsearch'
            )

            # C. VISUALIZATION (Draw Green Boxes)
            vis_img = cv2.cvtColor(processed_img, cv2.COLOR_GRAY2BGR)
            for (bbox, text, prob) in results:
                # bbox = [[tl], [tr], [br], [bl]]
                tl = tuple(map(int, bbox[0]))
                br = tuple(map(int, bbox[2]))
                cv2.rectangle(vis_img, tl, br, (0, 255, 0), 3) # Green Box
            
            vis_name = f"vis_{clean_name}.jpg"
            vis_path = os.path.join(os.path.dirname(img_path), vis_name)
            cv2.imwrite(vis_path, vis_img)
            vis_url = f"{settings.MEDIA_URL}documents/{vis_name}".replace("\\", "/")

            # D. DATA STRUCTURING
            extracted_fields = {}
            lines = {}

            for (bbox, text, prob) in results:
                y_center = int((bbox[0][1] + bbox[2][1]) / 2)
                x_start = int(bbox[0][0])
                
                # Group text into "Rows" based on Y-position (within 40px tolerance)
                matched_row = None
                for existing_y in lines:
                    if abs(existing_y - y_center) < 40:
                        matched_row = existing_y
                        break
                
                if matched_row:
                    lines[matched_row].append((x_start, text, prob))
                else:
                    lines[y_center] = [(x_start, text, prob)]

            # Clean and sort the rows
            for idx, y in enumerate(sorted(lines.keys())):
                # Sort row by X position (left to right)
                sorted_row = sorted(lines[y], key=lambda item: item[0])
                
                # Join text (e.g. "G" "A" "N" -> "GAN")
                raw_text = " ".join([item[1] for item in sorted_row]).upper()
                
                # Filter: Keep only letters, numbers, and basic symbols
                clean_text = re.sub(r'[^A-Z0-9\-\.\/]', ' ', raw_text)
                
                # Merge spaced letters (e.g., "G A N G A" -> "GANGA")
                # Heuristic: If we have many spaces but short words, it's likely a boxed field
                if len(clean_text) > 3 and clean_text.count(' ') > len(clean_text) / 3:
                     clean_text = clean_text.replace(" ", "")

                # Remove extra whitespace
                clean_text = " ".join(clean_text.split())

                if len(clean_text) > 1:
                    extracted_fields[f"Row_{idx+1}"] = {
                        "text": clean_text,
                        "accuracy": round(sum(i[2] for i in sorted_row)/len(sorted_row)*100, 1)
                    }

            print(f"✅ Found {len(extracted_fields)} rows of data.")
            print("="*40)

            return Response({
                "status": "success",
                "data": extracted_fields,
                "image_url": serializer.instance.image.url,
                "debug_image": debug_url,   # Input image AI saw
                "detection_image": vis_url  # Output image with green boxes
            }, status=201)

        except Exception as e:
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)