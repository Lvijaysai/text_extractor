//frontend/src/App.js
import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [file, setFile] = useState(null);
  const [text, setText] = useState("");
  const [extractedData, setExtractedData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState(null);

  const onFileChange = (e) => {
    const selected = e.target.files[0];
    if (!selected) return;
    setFile(selected);
    setPreview(URL.createObjectURL(selected));
    // Reset output
    setText("");
    setExtractedData(null);
  };

  const onUpload = async () => {
    if (!file) return;
    setLoading(true);
    
    const formData = new FormData();
    formData.append("image", file);

    try {
      // Ensure this URL matches your Django terminal output
      const res = await axios.post("http://127.0.0.1:8000/api/scan/", formData);
      
      setText(res.data.text);
      setExtractedData(res.data.data);
    } catch (err) {
      console.error(err);
      alert("Scanning failed. Check Django console for errors.");
    }
    setLoading(false);
  };

  return (
    <div className="App">
      {/* Header */}
      <header className="app-header">
        <h1>VisionOCR</h1>
      </header>
      
      <div className="container">
        {/* Upload Section */}
        <div className="upload-section">
          <input type="file" onChange={onFileChange} accept="image/*" id="file" hidden />
          <label htmlFor="file" className="btn-upload">
             {file ? file.name : "📁 Select Image"}
          </label>
          <button onClick={onUpload} className="btn-scan" disabled={!file || loading}>
            {loading ? "Processing..." : "Extract Data"}
          </button>
        </div>

        <div className="results-grid">
          {/* Left: Image Preview */}
          <div className="card">
            <h3>Original Document</h3>
            <div className="image-box">
              {preview ? (
                <img src={preview} alt="Preview" />
              ) : (
                <p className="placeholder">No image selected</p>
              )}
            </div>
          </div>

          {/* Right: Extracted Data */}
          <div className="card">
            <h3>Extracted Information</h3>
            
            {extractedData && extractedData.fields ? (
              <div className="data-box">
                <table className="info-table">
                  <thead>
                    <tr>
                      <th>Field</th>
                      <th>Extracted Value</th>
                      <th>Model Accuracy</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(extractedData.fields).map(([key, val]) => (
                      <tr key={key}>
                        <td className="label">{key}</td>
                        <td className="value">{val.text}</td>
                        <td className="accuracy">
                          <span className={`badge ${val.accuracy > 80 ? 'high' : 'low'}`}>
                            {val.accuracy}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* Dates Found section (if available) */}
                {extractedData.dates && extractedData.dates.length > 0 && (
                  <div className="extra-info" style={{ marginTop: '20px' }}>
                    <strong>Dates Found:</strong> {extractedData.dates.join(", ")}
                  </div>
                )}
              </div>
            ) : (
              <p className="placeholder">No data extracted yet.</p>
            )}

            {/* Raw Text Fallback */}
            <details style={{ marginTop: '20px' }}>
              <summary style={{ cursor: 'pointer', fontWeight: 'bold', color: '#2c3e50' }}>
                View Raw Text
              </summary>
              <pre className="raw-text">{text}</pre>
            </details>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;