// frontend/src/App.js
import React, { useState } from 'react';
import ChequeValidator from './ChequeValidator';
import DocumentScanner from './DocumentScanner';
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
      </nav>

      <main style={{ padding: '20px', backgroundColor: '#f8fafc', minHeight: '85vh' }}>
        {/* Render the correct tool based on the clicked tab */}
        {activeTab === 'cheque' ? <ChequeValidator /> : <DocumentScanner />}
      </main>
    </div>
  );
}

export default App;