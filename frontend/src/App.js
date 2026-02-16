import React, { useState } from 'react';
import axios from 'axios';
import './App.css'; // Make sure this file exists!

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [ocrData, setOcrData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [detectionImage, setDetectionImage] = useState(null);

  // Define your Django Server URL here to fix broken images
  const API_BASE_URL = "http://127.0.0.1:8000";

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      setSelectedFile(file);
      setPreview(URL.createObjectURL(file));
      setOcrData(null);       // Reset old data
      setDetectionImage(null); // Reset old image
    }
  };

  const handleScan = async () => {
    if (!selectedFile) return;
    setLoading(true);

    const formData = new FormData();
    formData.append('image', selectedFile);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/scan/`, formData);
      console.log("Server Response:", response.data);

      setOcrData(response.data.data);
      
      // FIX: Prepend the Django Server URL so the image loads
      if (response.data.detection_image) {
        setDetectionImage(API_BASE_URL + response.data.detection_image);
      }
      
    } catch (error) {
      console.error("Error scanning:", error);
      alert("Scan failed! Is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* 1. Professional Header */}
      <header className="app-header">
        <h1>🖊️ VisionOCR: Handwriting Scanner</h1>
      </header>

      <div className="main-layout">
        
        {/* 2. Upload Card */}
        <div className="card upload-card">
          <h3>1. Upload Document</h3>
          <div className="upload-controls">
            <input 
              type="file" 
              id="fileInput"
              onChange={handleFileChange} 
              accept="image/*" 
              style={{ display: 'none' }} 
            />
            <label htmlFor="fileInput" className="btn btn-outline">
              {selectedFile ? selectedFile.name : "📁 Choose Image"}
            </label>
            
            <button 
              onClick={handleScan} 
              disabled={!selectedFile || loading}
              className="btn btn-primary"
            >
              {loading ? "⏳ Scanning..." : "🚀 Extract Text"}
            </button>
          </div>
        </div>

        <div className="content-grid">
          {/* 3. Image Viewer (Left) */}
          <div className="card image-card">
            <h3>Document View</h3>
            <div className="image-frame">
              {/* Logic: Show Detection Image if available, otherwise Original */}
              {detectionImage ? (
                <img src={detectionImage} alt="AI Analysis" className="doc-image" />
              ) : preview ? (
                <img src={preview} alt="Preview" className="doc-image" />
              ) : (
                <div className="placeholder-text">No image selected</div>
              )}
            </div>
            {detectionImage && <p className="caption">✅ Green boxes indicate detected text</p>}
          </div>

          {/* 4. Results Table (Right) */}
          <div className="card results-card">
            <h3>Extracted Data</h3>
            {ocrData ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Row ID</th>
                    <th>Detected Text</th>
                    <th>Accuracy</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(ocrData).map(([key, value]) => (
                    <tr key={key}>
                      <td className="row-id">{key}</td>
                      <td className="ocr-text">{value.text}</td>
                      <td>
                        <span className={`badge ${value.accuracy > 80 ? 'good' : 'avg'}`}>
                          {value.accuracy}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="empty-state">
                <p>Upload a form and click "Extract" to see results here.</p>
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}

export default App;