/**
 * Main React application.
 *
 * HOP 19-20: Frontend components that initiate taint chains.
 */

import React from 'react';
import { UserSearch } from './components/UserSearch';
import { ReportViewer } from './components/ReportViewer';

function App() {
  return (
    <div className="app">
      <h1>DeepFlow Frontend</h1>
      <p>
        <strong>WARNING:</strong> Contains intentional vulnerabilities for testing.
      </p>

      <section>
        <h2>User Search (SQL Injection Chain)</h2>
        <UserSearch />
      </section>

      <section>
        <h2>Report Viewer (XSS Chain)</h2>
        <ReportViewer />
      </section>
    </div>
  );
}

export default App;
