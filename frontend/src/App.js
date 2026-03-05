import React, { useState } from 'react';
import axios from 'axios';
import './App.css'; 

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [ocrData, setOcrData] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [detectionImage, setDetectionImage] = useState(null);

  const API_BASE_URL = "http://127.0.0.1:8000";

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      setSelectedFile(file);
      setPreview(URL.createObjectURL(file));
      setOcrData(null);       
      setDetectionImage(null); 
      setProfile(null); 
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
      setProfile(response.data.profile || null);
      
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
      <header className="app-header">
        <h1>🖊️ VisionOCR: Handwriting Scanner</h1>
      </header>

      <div className="main-layout">
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
          <div className="card image-card">
            <h3>Document View</h3>
            <div className="image-frame">
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

          <div className="card results-card">
            <h3>Extracted Data</h3>
            
            {/* The Profile ID Card */}
            {profile && (
              <div style={{ 
                  backgroundColor: '#f8fafc', 
                  border: '1px solid #e2e8f0', 
                  borderRadius: '8px', 
                  padding: '24px', 
                  marginBottom: '24px',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
              }}>
                <h3 style={{ marginTop: 0, color: '#1e293b', borderBottom: '2px solid #e2e8f0', paddingBottom: '12px' }}>
                  PAN Card Application Details
                </h3>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginTop: '16px' }}>
                  <div>
                    <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Full Name</p>
                    <p style={{ margin: 0, fontSize: '16px', fontWeight: 'bold', color: '#0f172a' }}>
                      {profile.name || "N/A"}
                    </p>
                  </div>

                  <div>
                    <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Date of Birth</p>
                    <p style={{ margin: 0, fontSize: '16px', fontWeight: 'bold', color: '#0f172a' }}>
                      {profile.date_of_birth || "N/A"}
                    </p>
                  </div>

                  <div>
                    <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Gender</p>
                    <p style={{ margin: 0, fontSize: '16px', fontWeight: 'bold', color: '#0f172a' }}>
                      {profile.gender || "N/A"}
                    </p>
                  </div>

                  <div>
                    <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Father's Name</p>
                    <p style={{ margin: 0, fontSize: '16px', fontWeight: 'bold', color: '#0f172a' }}>
                      {profile.father_name || "N/A"}
                    </p>
                  </div>
                </div>

                <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px dashed #cbd5e1' }}>
                  <p style={{ margin: '0 0 12px 0', fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Full Residence Address</p>
                  <p style={{ margin: '0 0 16px 0', fontSize: '15px', color: '#334155' }}>
                    {profile.address?.full_address || "N/A"}
                  </p>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', backgroundColor: '#e2e8f0', padding: '12px', borderRadius: '6px' }}>
                    <div>
                      <p style={{ margin: '0 0 2px 0', fontSize: '11px', color: '#475569', textTransform: 'uppercase' }}>Area / Locality</p>
                      <p style={{ margin: 0, fontSize: '14px', fontWeight: '600', color: '#0f172a' }}>{profile.address?.area || "N/A"}</p>
                    </div>
                    <div>
                      <p style={{ margin: '0 0 2px 0', fontSize: '11px', color: '#475569', textTransform: 'uppercase' }}>Town / City</p>
                      <p style={{ margin: 0, fontSize: '14px', fontWeight: '600', color: '#0f172a' }}>{profile.address?.city || "N/A"}</p>
                    </div>
                    <div>
                      <p style={{ margin: '0 0 2px 0', fontSize: '11px', color: '#475569', textTransform: 'uppercase' }}>State</p>
                      <p style={{ margin: 0, fontSize: '14px', fontWeight: '600', color: '#0f172a' }}>{profile.address?.state || "N/A"}</p>
                    </div>
                    <div>
                      <p style={{ margin: '0 0 2px 0', fontSize: '11px', color: '#475569', textTransform: 'uppercase' }}>Pin Code</p>
                      <p style={{ margin: 0, fontSize: '14px', fontWeight: '600', color: '#0f172a' }}>{profile.address?.pin_code || "N/A"}</p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* The Raw Data Table */}
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
              !profile && (
                <div className="empty-state">
                  <p>Upload a form and click "Extract" to see results here.</p>
                </div>
              )
            )}
          </div>
        </div>

      </div>
    </div>
  );
}

export default App;