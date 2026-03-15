// frontend/src/ChequeValidator.js
import React, { useState } from 'react';

function ChequeValidator() {
  const [files, setFiles] = useState({ cheque: null, pan: null, aadhaar: null });
  const [previews, setPreviews] = useState({ cheque: null, pan: null, aadhaar: null });
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleFileChange = (e, type) => {
    const file = e.target.files[0];
    if (file) {
      setFiles({ ...files, [type]: file });
      setPreviews({ ...previews, [type]: URL.createObjectURL(file) });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!files.cheque || !files.pan || !files.aadhaar) {
      setError("Please upload all three documents.");
      return;
    }

    setLoading(true);
    setError(null);
    setResults(null);

    const formData = new FormData();
    formData.append('cheque', files.cheque);
    formData.append('pan', files.pan);
    formData.append('aadhaar', files.aadhaar);

    try {
      const response = await fetch('http://127.0.0.1:8000/api/validate-cheque/', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      
      if (!response.ok || data.status !== "success") {
        throw new Error(data.error || `Server error: ${response.status}`);
      }

      setResults(data);
    } catch (err) {
      setError(err.message || "An error occurred during validation.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="main-layout">
      {error && (
        <div style={{ backgroundColor: '#fee2e2', color: '#991b1b', padding: '12px', borderRadius: '6px', textAlign: 'center', marginBottom: '20px' }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="content-grid">
        {/* LEFT SIDE: UPLOADS */}
        <div className="card">
          <h3>Document Upload</h3>
          <form onSubmit={handleSubmit}>
            
            <div className="file-drop-zone" onClick={() => document.getElementById('chq-upload').click()}>
              <input type="file" id="chq-upload" hidden accept="image/*" onChange={(e) => handleFileChange(e, 'cheque')} />
              <strong>1. Upload Cheque</strong>
              <p style={{ margin: '5px 0', fontSize: '12px', color: '#64748b' }}>{files.cheque ? files.cheque.name : 'Click to browse'}</p>
              {previews.cheque && <img src={previews.cheque} alt="Cheque Preview" className="preview-img" />}
            </div>

            <div className="file-drop-zone" onClick={() => document.getElementById('pan-upload').click()}>
              <input type="file" id="pan-upload" hidden accept="image/*" onChange={(e) => handleFileChange(e, 'pan')} />
              <strong>2. Upload PAN Card (Person A)</strong>
              <p style={{ margin: '5px 0', fontSize: '12px', color: '#64748b' }}>{files.pan ? files.pan.name : 'Click to browse'}</p>
              {previews.pan && <img src={previews.pan} alt="PAN Preview" className="preview-img" />}
            </div>

            <div className="file-drop-zone" onClick={() => document.getElementById('aad-upload').click()}>
              <input type="file" id="aad-upload" hidden accept="image/*" onChange={(e) => handleFileChange(e, 'aadhaar')} />
              <strong>3. Upload Aadhaar Card (Person B)</strong>
              <p style={{ margin: '5px 0', fontSize: '12px', color: '#64748b' }}>{files.aadhaar ? files.aadhaar.name : 'Click to browse'}</p>
              {previews.aadhaar && <img src={previews.aadhaar} alt="Aadhaar Preview" className="preview-img" />}
            </div>

            <button type="submit" disabled={loading} className="btn btn-primary" style={{ width: '100%', marginTop: '10px' }}>
              {loading ? "⏳ Validating Documents..." : "🚀 Validate Cheque"}
            </button>
          </form>
        </div>
        {/* RIGHT SIDE: RESULTS */}
        <div className="card">
          <h3>System Decision Engine (JSON)</h3>
          
          {!results && !loading && (
            <div className="empty-state">
              <p>Upload all three documents and run the validation to see the system analysis.</p>
            </div>
          )}

          {loading && (
            <div className="empty-state">
              <p>Extracting text and running business logic...</p>
            </div>
          )}

          {results && results.data && (
            <div style={{ 
              backgroundColor: '#1e293b', /* Dark background for code */
              border: '1px solid #e2e8f0', 
              borderRadius: '8px', 
              padding: '24px',
              overflowX: 'auto',
              marginTop: '15px'
            }}>
              <pre style={{ 
                margin: 0, 
                color: '#10b981', /* Matrix green text */
                fontFamily: 'monospace',
                fontSize: '14px',
                whiteSpace: 'pre-wrap' 
              }}>
                {JSON.stringify(results, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ChequeValidator;