// frontend/src/DocumentScanner.js
import React, { useState } from 'react';
import axios from 'axios';

function DocumentScanner() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [detectionImage, setDetectionImage] = useState(null);

  const API_BASE_URL = "http://127.0.0.1:8000";

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      setSelectedFile(file);
      setPreview(URL.createObjectURL(file));
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
      setProfile(response.data.profile || null);
      if (response.data.image_url) {
        setDetectionImage(API_BASE_URL + response.data.image_url);
      }
    } catch (error) {
      alert("Scan failed! Check backend connection.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="main-layout">
      <div className="content-grid">
        {/* LEFT SIDE: UPLOAD & PREVIEW */}
        <div className="card">
          <h3>Upload PAN Application</h3>
          <div className="file-drop-zone" onClick={() => document.getElementById('pan-form-upload').click()}>
            <input type="file" id="pan-form-upload" hidden accept="image/*" onChange={handleFileChange} />
            <strong>Select Handwritten Form</strong>
            <p style={{ margin: '5px 0', fontSize: '12px', color: '#64748b' }}>{selectedFile ? selectedFile.name : 'Click to browse'}</p>
          </div>
          
          <button onClick={handleScan} disabled={!selectedFile || loading} className="btn btn-primary" style={{ width: '100%' }}>
            {loading ? "⏳ Extracting Text..." : "🚀 Extract Data"}
          </button>

          <div className="image-frame" style={{ marginTop: '20px' }}>
            {detectionImage ? (
              <img src={detectionImage} alt="AI Analysis" className="doc-image" />
            ) : preview ? (
              <img src={preview} alt="Preview" className="doc-image" />
            ) : (
              <div className="placeholder-text">No image selected</div>
            )}
          </div>
        </div>

        {/* RIGHT SIDE: EXTRACTED DATA */}
        <div className="card">
          <h3>Extracted Profile Data</h3>
          {profile ? (
            <div style={{ backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '24px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                <div>
                  <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Full Name</p>
                  <p style={{ margin: 0, fontSize: '16px', fontWeight: 'bold' }}>{profile.name || "N/A"}</p>
                </div>
                <div>
                  <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Date of Birth</p>
                  <p style={{ margin: 0, fontSize: '16px', fontWeight: 'bold' }}>{profile.date_of_birth || "N/A"}</p>
                </div>
                <div>
                  <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Gender</p>
                  <p style={{ margin: 0, fontSize: '16px', fontWeight: 'bold' }}>{profile.gender || "N/A"}</p>
                </div>
                <div>
                  <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Father's Name</p>
                  <p style={{ margin: 0, fontSize: '16px', fontWeight: 'bold' }}>{profile.father_name || "N/A"}</p>
                </div>
                {/* --- NEW STATE FIELD --- */}
                <div>
                  <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>State / UT</p>
                  <p style={{ margin: 0, fontSize: '16px', fontWeight: 'bold', color: '#00b894' }}>{profile.state || "N/A"}</p>
                </div>

                {/* --- NEW PIN FIELD --- */}
                <div>
                  <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Pincode</p>
                  <p style={{ margin: 0, fontSize: '16px', fontWeight: 'bold', color: '#00b894' }}>{profile.pin || "N/A"}</p>
                </div>
              </div>
              
              <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px dashed #cbd5e1' }}>
                <p style={{ margin: '0 0 8px 0', fontSize: '12px', color: '#64748b', textTransform: 'uppercase' }}>Full Address</p>
                <p style={{ margin: 0, fontSize: '15px' }}>{profile.address?.full_address || "N/A"}</p>
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <p>Upload a form and extract data to see the digitized profile here.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default DocumentScanner;