// frontend/src/PanFormScanner.js
import React, { useState } from 'react';
import axios from 'axios';
import { downloadPDF } from './ExportPDF';

const API_BASE_URL = 'http://127.0.0.1:8000';

const PRIMARY_FIELD_OPTIONS = [
  { key: 'full_name', label: 'Full Name', description: 'Applicant name' },
  { key: 'dob', label: 'DOB', description: 'Date of birth' },
  { key: 'gender', label: 'Gender', description: 'Selected gender box' },
  { key: 'father_name', label: "Father's Name", description: 'Parent name block' },
  { key: 'location', label: 'Location', description: 'State and pincode' },
  { key: 'address_details', label: 'Address', description: 'Structured address lines' },
];

const METADATA_FIELD_OPTIONS = [
  { key: 'confidence_metrics', label: 'Confidence', description: 'Field review scores' },
  { key: 'raw_extracted_text', label: 'Raw OCR', description: 'Uncleaned OCR text' },
];

const DEFAULT_SELECTED_FIELDS = [
  ...PRIMARY_FIELD_OPTIONS.map((field) => field.key),
  ...METADATA_FIELD_OPTIONS.map((field) => field.key),
];

function buildEditorPayload(profile, status = 'success') {
  return JSON.stringify({ status, data: profile }, null, 2);
}

function extractProfileFromJson(value) {
  const parsed = JSON.parse(value);
  const data = parsed?.data ?? parsed?.profile ?? parsed;

  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new Error('JSON must contain an object in "data".');
  }

  return data;
}

function PanFormScanner() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [detectionImage, setDetectionImage] = useState(null);
  const [selectedFields, setSelectedFields] = useState(DEFAULT_SELECTED_FIELDS);
  const [jsonDraft, setJsonDraft] = useState('');
  const [jsonError, setJsonError] = useState('');
  const [lastSyncedJson, setLastSyncedJson] = useState('');
  const [requestError, setRequestError] = useState('');

  const selectedPrimaryCount = PRIMARY_FIELD_OPTIONS.filter((field) =>
    selectedFields.includes(field.key)
  ).length;

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (!file) {
      return;
    }

    if (preview) {
      URL.revokeObjectURL(preview);
    }

    setSelectedFile(file);
    setPreview(URL.createObjectURL(file));
    setDetectionImage(null);
    setProfile(null);
    setJsonDraft('');
    setJsonError('');
    setLastSyncedJson('');
    setRequestError('');
  };

  const handleFieldToggle = (fieldKey) => {
    setSelectedFields((currentFields) =>
      currentFields.includes(fieldKey)
        ? currentFields.filter((field) => field !== fieldKey)
        : [...currentFields, fieldKey]
    );
  };

  const handleJsonChange = (event) => {
    const nextValue = event.target.value;
    setJsonDraft(nextValue);

    try {
      setProfile(extractProfileFromJson(nextValue));
      setJsonError('');
    } catch (error) {
      setJsonError(error.message || 'JSON is invalid.');
    }
  };

  const handleResetJson = () => {
    if (!lastSyncedJson) {
      return;
    }

    setJsonDraft(lastSyncedJson);
    setProfile(extractProfileFromJson(lastSyncedJson));
    setJsonError('');
  };

  const handleDownload = () => {
    if (!profile || jsonError) {
      return;
    }

    downloadPDF(profile);
  };

  const handleScan = async () => {
    if (!selectedFile || selectedPrimaryCount === 0) {
      return;
    }

    setLoading(true);
    setRequestError('');

    const formData = new FormData();
    formData.append('image', selectedFile);
    formData.append('fields', JSON.stringify(selectedFields));

    try {
      const response = await axios.post(`${API_BASE_URL}/api/scan/`, formData);
      const extractedProfile = response.data.data || response.data.profile || null;
      const nextJson = buildEditorPayload(extractedProfile, response.data.status || 'success');

      setProfile(extractedProfile);
      setJsonDraft(nextJson);
      setLastSyncedJson(nextJson);
      setJsonError('');
      setDetectionImage(response.data.image_url ? API_BASE_URL + response.data.image_url : null);
    } catch (error) {
      setRequestError(error.response?.data?.error || 'Scan failed. Check the backend connection.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="main-layout">
      <div className="content-grid">
        <div className="card">
          <h3>Upload PAN Application</h3>

          <div
            className="file-drop-zone"
            onClick={() => document.getElementById('pan-form-upload').click()}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                document.getElementById('pan-form-upload').click();
              }
            }}
            role="button"
            tabIndex={0}
          >
            <input
              type="file"
              id="pan-form-upload"
              hidden
              accept="image/*"
              onChange={handleFileChange}
            />
            <strong>Select PAN Form Image</strong>
            <p className="upload-hint">
              {selectedFile ? selectedFile.name : 'Click to browse'}
            </p>
          </div>

          <div className="field-picker">
            <div className="field-picker-header">
              <h4>Choose What To Extract</h4>
              <p>Select at least one main field before running OCR.</p>
            </div>

            <div className="field-option-grid">
              {PRIMARY_FIELD_OPTIONS.map((field) => (
                <label className="field-option" key={field.key}>
                  <input
                    type="checkbox"
                    checked={selectedFields.includes(field.key)}
                    onChange={() => handleFieldToggle(field.key)}
                  />
                  <span>
                    <strong>{field.label}</strong>
                    <small>{field.description}</small>
                  </span>
                </label>
              ))}
            </div>

            <div className="field-picker-header compact">
              <h4>Extra Output Sections</h4>
              <p>Optional metadata for review and debugging.</p>
            </div>

            <div className="field-option-grid compact">
              {METADATA_FIELD_OPTIONS.map((field) => (
                <label className="field-option" key={field.key}>
                  <input
                    type="checkbox"
                    checked={selectedFields.includes(field.key)}
                    onChange={() => handleFieldToggle(field.key)}
                  />
                  <span>
                    <strong>{field.label}</strong>
                    <small>{field.description}</small>
                  </span>
                </label>
              ))}
            </div>
          </div>

          {selectedPrimaryCount === 0 && (
            <div className="form-warning">
              Select at least one extraction field to enable scanning.
            </div>
          )}

          {requestError && <div className="form-error">{requestError}</div>}

          <button
            onClick={handleScan}
            disabled={!selectedFile || loading || selectedPrimaryCount === 0}
            className="btn btn-primary"
            style={{ width: '100%' }}
          >
            {loading ? 'Extracting data...' : 'Extract Data'}
          </button>

          <div className="image-frame" style={{ marginTop: '20px' }}>
            {detectionImage ? (
              <img src={detectionImage} alt="Aligned form" className="doc-image" />
            ) : preview ? (
              <img src={preview} alt="Preview" className="doc-image" />
            ) : (
              <div className="placeholder-text">No image selected</div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="editor-header">
            <h3 style={{ margin: 0 }}>Editable JSON Output</h3>

            {profile && (
              <div className="editor-actions">
                <button type="button" onClick={handleResetJson} className="btn btn-outline btn-small">
                  Reset JSON
                </button>
                <button
                  type="button"
                  onClick={handleDownload}
                  className="btn btn-primary btn-small"
                  disabled={Boolean(jsonError)}
                >
                  Download PDF
                </button>
              </div>
            )}
          </div>

          {profile ? (
            <div className="json-editor-shell">
              <textarea
                className="json-editor"
                value={jsonDraft}
                onChange={handleJsonChange}
                spellCheck={false}
              />
              <div className="editor-note">
                {jsonError
                  ? `JSON error: ${jsonError}`
                  : 'The latest valid JSON in this editor is used for export.'}
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <p>Upload a form, choose the fields, and run OCR to edit the JSON here.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default PanFormScanner;
