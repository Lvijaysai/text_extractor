
# VisionOCR: AI-Powered Document Scanner

**VisionOCR** is a full-stack web application that allows users to upload images of documents and instantly extract text using local AI processing. Built with a robust Django backend and a modern React frontend, it features a clean dashboard interface and privacy-focused local execution.

## 🚀 Key Features

* **📄 AI Text Extraction:** Uses `EasyOCR` (PyTorch) to accurately read text from images.
* **🔒 Privacy First:** All processing happens locally on your machine; no data is sent to the cloud.
* **🖥️ Modern Dashboard:** A responsive React UI for uploading files and viewing results side-by-side.
* **⚡ Real-Time Feedback:** Instant status updates and error handling.
* **📝 Paragraph Optimization:** Intelligent text post-processing to group words into readable paragraphs.

## 🛠️ Tech Stack

### **Backend**
* **Framework:** Django & Django REST Framework (DRF)
* **AI Engine:** EasyOCR (PyTorch)
* **Database:** SQLite (Default)
* **API:** RESTful API endpoints for file handling

### **Frontend**
* **Framework:** React.js
* **HTTP Client:** Axios
* **Styling:** CSS3 (Custom Dashboard Design)


## ⚙️ Installation & Setup

Follow these steps to run the project locally.

### 1. Clone the Repository
```bash
git clone 
cd text_extractor

```

### 2. Backend Setup (Django)

Open a terminal and navigate to the backend folder:

```bash
cd backend

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
# source venv/bin/activate

# Install dependencies
pip install django djangorestframework django-cors-headers easyocr

# Run migrations
python manage.py migrate

# Start the server
python manage.py runserver

```

*The backend will run at `http://127.0.0.1:8000/*`

### 3. Frontend Setup (React)

Open a **new terminal** (keep the backend running) and navigate to the frontend folder:

```bash
cd frontend

# Install Node modules
npm install

# Start the React app
npm start

```

*The frontend will launch at `http://localhost:3000/*`

---

## 📸 How to Use

1. Open your browser to `http://localhost:3000`.
2. Click **"Choose Document"** and select an image (JPG, PNG) containing text.
3. Click **"Extract Text"**.
4. Wait for the AI to process (1-5 seconds depending on your hardware).
5. View the original image and the extracted text side-by-side!

---

## 📂 Project Structure

```text
text_extractor/
├── backend/                # Django Backend
│   ├── ocr/                # Main app for OCR logic
│   ├── media/              # Stores uploaded images
│   ├── db.sqlite3          # Local database
│   └── manage.py
├── frontend/               # React Frontend
│   ├── src/                # React components (App.js)
│   ├── public/
│   └── package.json
└── README.md

```

