
# VisionOCR: AI-Powered Document Scanner

**VisionOCR** is a full-stack web application that allows users to upload images of documents and instantly extract text using local AI processing. Built with a robust Django backend and a modern React frontend, it features a clean dashboard interface and privacy-focused local execution.

## 🚀 Key Features

* **📄 AI Text Extraction:** Uses `PaddleOCR` (CPU) to accurately read text from images.
* **🔒 Privacy First:** All processing happens locally on your machine; no data is sent to the cloud.
* **🖥️ Modern Dashboard:** A responsive React UI for uploading files and viewing results side-by-side.
* **⚡ Real-Time Feedback:** Instant status updates and error handling.
* **📝 Paragraph Optimization:** Intelligent text post-processing to group words into readable paragraphs.

## 🛠️ Tech Stack

### **Backend**
* **Framework:** Django & Django REST Framework (DRF)
* **AI Engine:** PaddleOCR (CPU)
* **Computer Vision:** OpenCV (`cv2`), NumPy
* **Matching Engine:** RapidFuzz
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
pip install django djangorestframework django-cors-headers paddleocr paddlepaddle opencv-python rapidfuzz python-dotenv

# Run migrations
python manage.py migrate

# Create a superuser to add mock Bank Account data
python manage.py createsuperuser

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

#### Setting up Test Data

Before testing the Cheque Validator, log into the Django Admin (`http://127.0.0.1:8000/admin/`) and create a mock `BankAccount` entry with an Account Number and the Account Holder's Name.

#### Using the Dashboard

1. Open your browser to `http://localhost:3000`.
2. **Tab 1: Cheque Validation**
* Upload a Cheque, a PAN Card (Person A), and an Aadhaar Card (Person B).
* Click **Validate Cheque** to run the 4-step security check against your database.
* View the instant Approved/Rejected decision.


3. **Tab 2: PAN Form Extraction**
* Upload a handwritten PAN application form.
* Click **Extract Data** to digitize the profile (Name, DOB, Father's Name, Address).
* View the original image alongside the structured JSON data.



---

### 📂 Project Structure

```text
text_extractor/
├── backend/                # Django Backend
│   ├── ocr/                # API App & SQLite Models
│   ├── ocr_engine/         # Core AI & Vision Logic
│   │   ├── align.py        # Perspective warping
│   │   ├── cheque_validator.py # Business logic & Fuzzy matching
│   │   ├── extractor.py    # Form extraction orchestrator
│   │   ├── ocr_runner.py   # PaddleOCR singleton
│   │   ├── postprocess.py  # Regex cleaning & Date fixing
│   │   └── preprocess.py   # OpenCV Grid-melting & Contrast
│   ├── media/              # Debug image storage (Forms only)
│   ├── db.sqlite3          # Local database
│   └── manage.py
├── frontend/               # React Frontend
│   ├── src/                
│   │   ├── App.js          # Tabbed Navigation Router
│   │   ├── ChequeValidator.js # Validation UI Component
│   │   ├── DocumentScanner.js # Form Scanner UI Component
│   │   └── App.css         # Premium UI Styling
│   ├── public/
│   └── package.json
└── README.md

```