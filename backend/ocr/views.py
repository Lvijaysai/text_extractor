import cv2
import numpy as np
import easyocr
import re
import os
import traceback
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils.text import get_valid_filename
from .serializers import FileSerializer

# Initialize OCR Engine once at startup
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
    # SMART PREPROCESSING: Box Detection with Fallback
    # ---------------------------------------------------------
    def isolate_boxes(self, img):
        # A. Binarize (Invert: Text/Lines = White, BG = Black)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

        # B. Detect Lines
        # Use slightly longer kernels to ensure we don't miss parts of the grid
        hor_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        ver_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
        
        hor_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, hor_kernel, iterations=2)
        ver_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, ver_kernel, iterations=2)
        
        # C. Create Grid Mask (White Lines on Black Background)
        grid_mask = cv2.addWeighted(hor_lines, 1, ver_lines, 1, 0)
        
        # D. CRITICAL FIX: Find the "Holes", not the "Lines"
        # 1. We dilate the lines to make them thicker/stronger (closing any tiny gaps)
        kernel = np.ones((3,3), np.uint8)
        grid_mask = cv2.dilate(grid_mask, kernel, iterations=1)

        # 2. Subtract the grid from the original image logic? 
        # Easier: Just look for contours in the INVERTED grid mask?
        # No, because the borders might not be closed.
        
        # RELIABLE METHOD: Use cv2.findContours on the grid_mask using RETR_CCOMP
        # RETR_CCOMP finds both the outer lines AND the inner holes.
        cnts, hierarchy = cv2.findContours(grid_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        
        # E. Create Clean Canvas
        final_img = np.ones_like(gray) * 255 
        
        box_count = 0
        
        # F. Iterate through contours
        if hierarchy is not None:
            for i, c in enumerate(cnts):
                # hierarchy[0][i] = [Next, Previous, First_Child, Parent]
                # We typically want contours that have NO children (inner-most boxes) 
                # OR contours that ARE children (holes).
                
                x, y, w, h = cv2.boundingRect(c)
                
                # Filter: Must be box-sized
                if w > 15 and h > 15 and w < 400 and h < 200:
                    aspect = w / float(h)
                    
                    # PAN boxes are usually roughly square (0.5 to 2.0)
                    if 0.5 < aspect < 2.5:
                        
                        # Logic check: Is this a black box or a white hole?
                        # We only want to copy the content if it's a valid region
                        
                        pad = 4
                        # Safety bounds
                        y1, y2 = max(0, y+pad), min(gray.shape[0], y+h-pad)
                        x1, x2 = max(0, x+pad), min(gray.shape[1], x+w-pad)
                        
                        roi = gray[y1:y2, x1:x2]
                        
                        if roi.size > 0:
                            # Verify roi isn't just pure black (a line artifact)
                            if np.mean(roi) > 50: 
                                final_img[y1:y2, x1:x2] = roi
                                box_count += 1

        print(f"   --> Found {box_count} valid character boxes.")
        
        # Fallback if it failed
        if box_count < 10: 
            print("   --> ⚠️ Low box count. Trying inverted contour method...")
            
            # ALTERNATIVE METHOD: INVERT THE GRID
            # If the grid is White lines, Inverting it makes lines Black and boxes White.
            # Then we can find the white boxes.
            inverted_grid = cv2.bitwise_not(grid_mask)
            cnts_inv, _ = cv2.findContours(inverted_grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            box_count_2 = 0
            for c in cnts_inv:
                x, y, w, h = cv2.boundingRect(c)
                if w > 15 and h > 15 and w < 400 and h < 200:
                    pad = 4
                    y1, y2 = max(0, y+pad), min(gray.shape[0], y+h-pad)
                    x1, x2 = max(0, x+pad), min(gray.shape[1], x+w-pad)
                    roi = gray[y1:y2, x1:x2]
                    final_img[y1:y2, x1:x2] = roi
                    box_count_2 += 1
            
            print(f"   --> Method 2 Found {box_count_2} boxes.")
            if box_count_2 < 10:
                print("   --> Both methods failed. Returning full image.")
                return gray

        return final_img

    def preprocess_handwriting(self, image_path):
        try:
            img = cv2.imread(image_path)
            if img is None: return None, None

            # 1. Upscale (Crucial for small text)
            img = cv2.resize(img, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

            # 2. Try Smart Isolation
            processed_img = self.isolate_boxes(img)

            # 3. Denoise (Clean up paper grain)
            denoised = cv2.fastNlMeansDenoising(processed_img, None, 10, 7, 21)
            
            # 4. Save Debug Image
            base_name = self.strip_extensions(os.path.basename(image_path))
            debug_name = f"debug_clean_{base_name}.jpg"
            debug_path = os.path.join(os.path.dirname(image_path), debug_name)
            cv2.imwrite(debug_path, denoised)
            
            rel_path = os.path.relpath(debug_path, settings.MEDIA_ROOT)
            debug_url = f"{settings.MEDIA_URL}{rel_path}".replace("\\", "/")

            return denoised, debug_url
        except Exception as e:
            print(f"Error in preprocessing: {e}")
            traceback.print_exc()
            return None, None

    # ---------------------------------------------------------
    # MAIN LOGIC
    # ---------------------------------------------------------
    def post(self, request, *args, **kwargs):
        serializer = FileSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        file_obj = request.FILES['image']
        clean_name = self.strip_extensions(get_valid_filename(file_obj.name))
        file_obj.name = f"{clean_name}.jpg"
        
        try:
            serializer.save()
            img_path = serializer.instance.image.path
            
            # A. PREPROCESS
            processed_img, debug_url = self.preprocess_handwriting(img_path)
            
            if processed_img is None:
                return Response({"error": "Failed to process image"}, status=500)

            print(f"\n🚀 Scanning: {file_obj.name}")

            # B. INFERENCE
            # Using 'greedy' decoder for block letters
            results = reader.readtext(
                processed_img,
                detail=1,
                paragraph=False,
                mag_ratio=1.0, 
                text_threshold=0.4, 
                width_ths=0.3, # Allow some space between letters
                decoder='greedy'
            )

            # C. VISUALIZATION
            vis_img = cv2.cvtColor(processed_img, cv2.COLOR_GRAY2BGR)
            for (bbox, text, prob) in results:
                tl = tuple(map(int, bbox[0]))
                br = tuple(map(int, bbox[2]))
                cv2.rectangle(vis_img, tl, br, (0, 0, 255), 2)
            
            vis_name = f"vis_{clean_name}.jpg"
            vis_path = os.path.join(os.path.dirname(img_path), vis_name)
            cv2.imwrite(vis_path, vis_img)
            vis_url = f"{settings.MEDIA_URL}documents/{vis_name}".replace("\\", "/")

            # D. DATA STRUCTURING
            extracted_fields = {}
            lines = {}

            # Group by Row (Y-Coordinate)
            for (bbox, text, prob) in results:
                y_center = int((bbox[0][1] + bbox[2][1]) / 2)
                x_start = int(bbox[0][0])
                
                matched = False
                for existing_y in lines:
                    if abs(existing_y - y_center) < 35: # Vertical tolerance
                        lines[existing_y].append((x_start, text, prob))
                        matched = True
                        break
                if not matched:
                    lines[y_center] = [(x_start, text, prob)]

            row_counter = 1
            sorted_y_keys = sorted(lines.keys())

            for y in sorted_y_keys:
                row_items = sorted(lines[y], key=lambda x: x[0])
                full_line_text = ""
                total_conf = 0
                count = 0

                for item in row_items:
                    # STRICT CLEANUP: Only A-Z and 0-9
                    txt = item[1].upper()
                    txt = re.sub(r'[^A-Z0-9]', '', txt) 
                    
                    if txt:
                        full_line_text += txt
                        total_conf += item[2]
                        count += 1
                
                # FILTERING:
                # Remove common form labels if they survived
                ignored = ["FORM", "NO49", "ONLY", "NAME", "LAST", "FIRST", "MIDDLE", "DATE"]
                is_junk = any(x in full_line_text for x in ignored)

                if count > 0 and len(full_line_text) > 2 and not is_junk:
                    avg_conf = round((total_conf / count) * 100, 1)
                    extracted_fields[f"Data_Row_{row_counter}"] = {
                        "text": full_line_text,
                        "accuracy": avg_conf
                    }
                    row_counter += 1

            return Response({
                "status": "success",
                "data": extracted_fields,
                "image_url": serializer.instance.image.url,
                "debug_image": debug_url,
                "detection_image": vis_url
            }, status=201)

        except Exception as e:
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)