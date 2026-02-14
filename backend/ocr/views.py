from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status  # Needed for HTTP status codes
from .models import ScannedDocument
from .serializers import FileSerializer # Ensure you have this serializer created
import easyocr

# Initialize the reader once
reader = easyocr.Reader(['en'])

class OCRView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        # Use the serializer to handle file validation and saving
        file_serializer = FileSerializer(data=request.data)
        
        if file_serializer.is_valid():
            # Save the file to the database
            file_serializer.save()
            
            # Get the path of the saved file
            # Note: Ensure your Serializer field is named 'file' or 'image' matches your model
            # If your model field is 'image', use: file_serializer.instance.image.path
            try:
                # Attempt to get path from 'image' field (based on your previous code)
                image_path = file_serializer.instance.image.path
            except AttributeError:
                # Fallback if the serializer field is named differently
                image_path = file_serializer.instance.file.path

            try:
                # --- OPTIMIZATION START ---
                # detail=0: Returns only text strings (no coordinates)
                # paragraph=True: key setting that groups nearby words into sentences
                result = reader.readtext(image_path, detail=0, paragraph=True)
                
                # Join the paragraphs with double newlines for distinct blocks
                cleaned_text = "\n\n".join(result)
                # --- OPTIMIZATION END ---

                # Update the database record with the extracted text
                file_serializer.instance.extracted_text = cleaned_text
                file_serializer.instance.save()

                return Response({
                    'id': file_serializer.instance.id,
                    'text': cleaned_text,
                    'image_url': file_serializer.instance.image.url
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(file_serializer.errors, status=status.HTTP_400_BAD_REQUEST)