// frontend/src/App.js
import React, { useState } from 'react';
import ChequeValidator from './ChequeValidator';
import PanFormScanner from './PanFormScanner';
import TemplateCalibrator from './TemplateCalibrator'; // <-- 1. Import it
import './App.css'; 

function App() {
  const [activeTab, setActiveTab] = useState('cheque');

  return (
    <div className="App">
      <header className="App-header">
        <h1>🏦 VisionOCR Financial Suite</h1>
      </header>

      {/* Navigation Menu */}
      <nav className="tab-navigation">
        <button 
          className={`tab-btn ${activeTab === 'cheque' ? 'active' : ''}`}
          onClick={() => setActiveTab('cheque')}
        >
          Cheque Validation
        </button>
        <button 
          className={`tab-btn ${activeTab === 'pan' ? 'active' : ''}`}
          onClick={() => setActiveTab('pan')}
        >
          PAN Form Extraction
        </button>
        {/* 2. Add the Calibrator Button */}
        <button 
          className={`tab-btn ${activeTab === 'calibrator' ? 'active' : ''}`}
          onClick={() => setActiveTab('calibrator')}
        >
          ⚙️ ROI Calibrator
        </button>
      </nav>

      <main style={{ padding: '20px', backgroundColor: '#f8fafc', minHeight: '85vh' }}>
        {/* 3. Render the correct tool */}
        {activeTab === 'cheque' && <ChequeValidator />}
        {activeTab === 'pan' && <PanFormScanner />}
        {activeTab === 'calibrator' && <TemplateCalibrator />}
      </main>
    </div>
  );
}

export default App;