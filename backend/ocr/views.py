#backend/ocr/views.py
import cv2
import numpy as np
import easyocr
import re
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import FileSerializer

# Initialize reader with high-accuracy mode
reader = easyocr.Reader(['en'])

class OCRView(APIView):
    def preprocess_for_maximum_accuracy(self, image_path):
        """
        Specialized cleaning for handwritten forms.
        """
        img = cv2.imread(image_path)
        
        # 1. Upscale significantly (4x) so small boxes become clear
        img = cv2.resize(img, None, fx=4, fy=4, interpolation=cv2.INTER_LANCZOS4)
        
        # 2. Convert to Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 3. Increase Contrast: Make ink blacker and paper whiter
        alpha = 1.5 # Contrast control
        beta = -50  # Brightness control
        adjusted = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)

        # 4. Remove Box Lines (Vertical/Horizontal)
        # We use a threshold to find the black lines of the boxes
        thresh = cv2.threshold(adjusted, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        
        # Identify lines
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (80, 1))
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 80))
        
        remove_h = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
        remove_v = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
        
        # Create mask of lines to delete
        mask = cv2.add(remove_h, remove_v)
        
        # Use Inpainting or White-out to remove the grid lines
        # This prevents the '|' symbol from being read as 'I'
        img_final = cv2.cvtColor(adjusted, cv2.COLOR_GRAY2BGR)
        img_final[mask > 0] = (255, 255, 255)
        
        return img_final

    def post(self, request, *args, **kwargs):
        serializer = FileSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            img_path = serializer.instance.image.path
            
            # 1. Apply High-Precision Preprocessing
            clean_img = self.preprocess_and_debug(img_path)
            
            # 2. Run OCR with 'Optimal Search' parameters
            # beamWidth: higher = more accurate but slower
            # min_size: prevents reading tiny dust specs as text
            results = reader.readtext(
                clean_img, 
                detail=1, 
                paragraph=False,
                beamWidth=15, 
                contrast_ths=0.1,
                adjust_contrast=0.7,
                text_threshold=0.6,
                low_text=0.4
            )

            # 3. Group fragments by line for better readability
            lines = {}
            for (bbox, text, prob) in results:
                y_center = int(sum([p[1] for p in bbox]) / 4)
                found = False
                for existing_y in lines.keys():
                    if abs(existing_y - y_center) < 30: # 30px tolerance
                        lines[existing_y].append((bbox[0][0], text, prob))
                        found = True
                        break
                if not found:
                    lines[y_center] = [(bbox[0][0], text, prob)]

            extracted_fields = {}
            for idx, y in enumerate(sorted(lines.keys())):
                # Sort words from left to right on each line
                sorted_line = sorted(lines[y], key=lambda x: x[0])
                
                # Combine text and filter out noise
                text_val = " ".join([it[1] for it in sorted_line]).strip().upper()
                avg_acc = sum([it[2] for it in sorted_line]) / len(sorted_line)
                
                # Filter: Only keep lines that have real data (not just single dots or lines)
                if len(text_val) > 2:
                    # Specific Form 49A fixes:
                    # Merging [G][A][N][G][A] -> GANGA
                    text_val = text_val.replace(" ", "") if len(text_val) < 15 else text_val
                    
                    extracted_fields[f"Row_{idx+1}"] = {
                        "text": text_val,
                        "accuracy": round(avg_acc * 100, 2)
                    }

            return Response({
                "text": "Full extraction complete.",
                "data": {"fields": extracted_fields},
                "image_url": serializer.instance.image.url
            }, status=status.HTTP_201_CREATED)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def preprocess_and_debug(self, path):
        # Helper to ensure the cleaning is applied
        return self.preprocess_for_maximum_accuracy(path)