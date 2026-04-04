import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';
import { ThemeProvider } from '@/contexts/ThemeContext';
import Layout from '@/components/Layout';
import Login from '@/components/Login/Login';
import Dashboard from '@/components/Dashboard/Dashboard';
import Campaigns from '@/components/Campaigns/Campaigns';
import CustomFilters from '@/components/CustomFilters/CustomFilters';
import Reports from '@/components/Reports/Reports';
import Analytics from '@/components/Analytics/Analytics';
import AIIntelligence from '@/components/AIIntelligence/AIIntelligence';
import AIGenerator from '@/components/AIGenerator/AIGenerator';
import ClickForensics from '@/pages/ClickForensics';
import WhatsAppCRM from '@/pages/WhatsAppCRM';
import WALandings from '@/pages/WALandings';
import WALandingForensics from '@/pages/WALandingForensics';
import LeadsCRM from '@/pages/LeadsCRM';
import UserManagement from '@/pages/UserManagement';
import '@/App.css';

function App() {
  return (
    <ThemeProvider>
      <div className="App">
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<Layout />}>
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="campaigns" element={<Campaigns />} />
              <Route path="custom-filters" element={<CustomFilters />} />
              <Route path="reports" element={<Reports />} />
              <Route path="analytics" element={<Analytics />} />
              <Route path="ai-intelligence" element={<AIIntelligence />} />
              <Route path="ai-generator" element={<AIGenerator />} />
              <Route path="click-forensics" element={<ClickForensics />} />
              <Route path="whatsapp-crm" element={<WhatsAppCRM />} />
              <Route path="wa-landings" element={<WALandings />} />
              <Route path="wa-landing-forensics" element={<WALandingForensics />} />
              <Route path="leads-crm" element={<LeadsCRM />} />
              <Route path="user-management" element={<UserManagement />} />
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster position="top-right" richColors />
      </div>
    </ThemeProvider>
  );
}

export default App;
