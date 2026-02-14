import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [file, setFile] = useState(null);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState(null);

  const onFileChange = (e) => {
    const selected = e.target.files[0];
    setFile(selected);
    setPreview(URL.createObjectURL(selected));
    setText(""); 
  };

  const onUpload = async () => {
    if (!file) return;
    setLoading(true);
    
    const formData = new FormData();
    formData.append("image", file);

    try {
      const res = await axios.post("http://127.0.0.1:8000/api/scan/", formData);
      
      // --- OPTIMIZATION START ---
      // Fix common OCR glitches before displaying text
      let cleanText = res.data.text;
      
      // 1. Remove weird "pipe" characters often found in dictionary scans
      if (cleanText) {
        cleanText = cleanText.replace(/\|/g, "");
        
        // 2. Fix multiple spaces turning into huge gaps
        cleanText = cleanText.replace(/ +/g, " ");
      }
      // --- OPTIMIZATION END ---

      setText(cleanText);
    } catch (err) {
      console.error(err);
      alert("Scanning failed. Make sure Django is running.");
    }
    setLoading(false);
  };

  return (
    <div className="App">
      {/* Sidebar Section */}
      <div className="sidebar">
        <h2>VisionOCR</h2>
        <p style={{ opacity: 0.7 }}>Local AI Scanner</p>
        <div style={{ marginTop: '30px' }}>
          <small>Status:</small>
          <br />
          <span style={{ color: '#00b894', fontWeight: 'bold' }}>● System Online</span>
        </div>
      </div>
      
      {/* Main Content Area */}
      <div className="content">
        <h1 style={{ marginBottom: '20px', color: '#333' }}>Dashboard</h1>

        {/* Upload Card */}
        <div className="upload-card">
          <input type="file" onChange={onFileChange} accept="image/*" id="file-upload" hidden />
          <label htmlFor="file-upload" className="upload-label">
            {file ? file.name : "📁 Choose Document"}
          </label>
          <button onClick={onUpload} className="scan-button" disabled={!file || loading}>
            {loading ? "Processing..." : "⚡ Extract Text"}
          </button>
        </div>

        {/* Results Grid */}
        <div className="grid">
          <div className="pane">
            <h3>Document Preview</h3>
            <div style={{ marginTop: '15px' }}>
              {preview ? (
                <img src={preview} alt="Preview" />
              ) : (
                <div style={{ padding: '40px', color: '#aaa' }}>No document selected</div>
              )}
            </div>
          </div>

          <div className="pane">
            <h3>Extracted Information</h3>
            <div className="text-output" style={{ marginTop: '15px' }}>
              {text ? <pre>{text}</pre> : <div style={{ padding: '40px', color: '#aaa' }}>Text will appear here...</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;