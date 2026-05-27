import React, { useEffect, useState } from 'react';
import { FinanzasModal } from './leads-crm/FinanzasModal';
import api from '@/utils/api';

export default function Finanzas() {
  const [currentUser, setCurrentUser] = useState(null);

  useEffect(() => {
    api.get('/auth/me').then(({ data }) => setCurrentUser(data)).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 py-6 px-4">
      <div className="max-w-5xl mx-auto">
        <FinanzasModal currentUser={currentUser} onClose={() => {}} inline />
      </div>
    </div>
  );
}
