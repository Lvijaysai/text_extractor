import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000';

const FIELDS = ["name", "dob", "gender", "father_name", "address", "state", "pin"];

function TemplateCalibrator() {
  const [imageSrc, setImageSrc] = useState(null);
  const [activeField, setActiveField] = useState("name");
  const [rois, setRois] = useState({});
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPos, setStartPos] = useState({ x: 0, y: 0 });
  const [currentBox, setCurrentBox] = useState(null);
  
  const imageRef = useRef(null);

  // Load existing ROIs from backend on mount
  useEffect(() => {
    axios.get(`${API_BASE_URL}/api/config/rois/`)
      .then(res => setRois(res.data.rois))
      .catch(err => console.error("Failed to load ROIs", err));
  }, []);

  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (imageSrc) URL.revokeObjectURL(imageSrc);
      setImageSrc(URL.createObjectURL(file));
    }
  };

  const getMouseCoords = (e) => {
    const rect = imageRef.current.getBoundingClientRect();
    // Calculate percentages relative to the image size
    const xPct = (e.clientX - rect.left) / rect.width;
    const yPct = (e.clientY - rect.top) / rect.height;
    return { x: Math.max(0, Math.min(1, xPct)), y: Math.max(0, Math.min(1, yPct)) };
  };

  const handleMouseDown = (e) => {
    if (!imageSrc) return;
    const coords = getMouseCoords(e);
    setIsDrawing(true);
    setStartPos(coords);
    setCurrentBox({ x1: coords.x, y1: coords.y, x2: coords.x, y2: coords.y });
  };

  const handleMouseMove = (e) => {
    if (!isDrawing) return;
    const coords = getMouseCoords(e);
    setCurrentBox({
      x1: Math.min(startPos.x, coords.x),
      y1: Math.min(startPos.y, coords.y),
      x2: Math.max(startPos.x, coords.x),
      y2: Math.max(startPos.y, coords.y)
    });
  };

  const handleMouseUp = () => {
    if (!isDrawing) return;
    setIsDrawing(false);
    if (currentBox) {
      // Save the final box array [x1, y1, x2, y2] to the active field
      setRois({
        ...rois,
        [activeField]: [currentBox.x1, currentBox.y1, currentBox.x2, currentBox.y2]
      });
      setCurrentBox(null);
    }
  };

  const saveConfiguration = async () => {
    try {
      await axios.post(`${API_BASE_URL}/api/config/rois/`, { rois });
      alert("✅ ROIs Saved Successfully to Backend!");
    } catch (err) {
      alert("❌ Failed to save ROIs.");
    }
  };

  // Helper to render bounding boxes overlay
  const renderBox = (boxArray, fieldName, isActive) => {
    if (!boxArray) return null;
    const [x1, y1, x2, y2] = boxArray;
    return (
      <div key={fieldName} style={{
        position: 'absolute',
        left: `${x1 * 100}%`, top: `${y1 * 100}%`,
        width: `${(x2 - x1) * 100}%`, height: `${(y2 - y1) * 100}%`,
        border: `2px solid ${isActive ? '#00b894' : '#3b82f6'}`,
        backgroundColor: isActive ? 'rgba(0, 184, 148, 0.2)' : 'rgba(59, 130, 246, 0.1)',
        pointerEvents: 'none'
      }}>
        <span style={{
          backgroundColor: isActive ? '#00b894' : '#3b82f6', color: 'white',
          fontSize: '10px', padding: '2px 4px', position: 'absolute', top: '-18px', left: '-2px'
        }}>
          {fieldName}
        </span>
      </div>
    );
  };

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '15px' }}>
        <h3>Template ROI Calibrator</h3>
        <button onClick={saveConfiguration} className="btn btn-primary">💾 Save Configuration</button>
      </div>

      <div style={{ display: 'flex', gap: '20px', marginBottom: '20px' }}>
        <input type="file" accept="image/*" onChange={handleImageUpload} />
        
        <select 
          value={activeField} 
          onChange={(e) => setActiveField(e.target.value)}
          style={{ padding: '8px', borderRadius: '4px', border: '1px solid #ccc' }}
        >
          {FIELDS.map(f => <option key={f} value={f}>Target: {f.toUpperCase()}</option>)}
        </select>
      </div>

      <div 
        style={{ position: 'relative', display: 'inline-block', border: '2px dashed #ccc', cursor: 'crosshair' }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        {imageSrc ? (
          <img 
            ref={imageRef} src={imageSrc} alt="Form Template" 
            style={{ maxWidth: '800px', display: 'block', userSelect: 'none' }} 
            draggable="false"
          />
        ) : (
          <div style={{ width: '800px', height: '1000px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#888' }}>
            Upload a blank PAN Form to calibrate ROIs
          </div>
        )}

        {/* Render all saved ROIs */}
        {Object.entries(rois).map(([field, coords]) => renderBox(coords, field, field === activeField))}
        
        {/* Render the box currently being drawn */}
        {isDrawing && currentBox && renderBox([currentBox.x1, currentBox.y1, currentBox.x2, currentBox.y2], activeField, true)}
      </div>
    </div>
  );
}

export default TemplateCalibrator;