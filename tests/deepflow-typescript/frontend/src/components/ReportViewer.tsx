/**
 * Report viewer component - HOP 20: Frontend XSS source.
 *
 * User input from this component flows through to template rendering
 * on the backend, creating an XSS vulnerability chain.
 */

import React, { useState } from 'react';
import { apiClient } from '../api/client';

export function ReportViewer() {
  const [title, setTitle] = useState('');
  const [htmlContent, setHtmlContent] = useState('');
  const [loading, setLoading] = useState(false);

  /**
   * Handle report generation.
   *
   * HOP 20: User input becomes XSS taint source.
   * Flows: useState -> fetch -> Express -> template -> XSS sink
   *
   * VULNERABILITY: XSS (frontend to backend template injection)
   */
  const handleGenerate = async () => {
    setLoading(true);
    try {
      // HOP 19: API client sends tainted title to backend
      const data = await apiClient.generateReport(title); // title is TAINTED
      setHtmlContent(data.html || '');
    } catch (error) {
      console.error('Generation failed:', error);
    }
    setLoading(false);
  };

  return (
    <div className="report-viewer">
      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)} // TAINT SOURCE
        placeholder="Report title..."
      />
      <button onClick={handleGenerate} disabled={loading}>
        {loading ? 'Generating...' : 'Generate Report'}
      </button>

      {/* VULNERABLE: Rendering backend-generated HTML without sanitization */}
      <div
        className="report-content"
        dangerouslySetInnerHTML={{ __html: htmlContent }}
      />
    </div>
  );
}
