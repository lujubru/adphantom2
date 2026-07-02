import React from 'react';

// Colorful gradient pairs (Google Contacts-inspired). Chosen for good contrast on dark bg.
const GRADIENTS = [
  ['#f43f5e', '#fb923c'], // rose → orange
  ['#f97316', '#eab308'], // orange → yellow
  ['#84cc16', '#22c55e'], // lime → green
  ['#22c55e', '#14b8a6'], // green → teal
  ['#14b8a6', '#0ea5e9'], // teal → sky
  ['#0ea5e9', '#6366f1'], // sky → indigo
  ['#6366f1', '#8b5cf6'], // indigo → violet
  ['#8b5cf6', '#d946ef'], // violet → fuchsia
  ['#d946ef', '#ec4899'], // fuchsia → pink
  ['#ec4899', '#f43f5e'], // pink → rose
  ['#0284c7', '#0891b2'], // blue → cyan
  ['#7c3aed', '#4f46e5'], // deep violet → indigo
];

function hashString(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (h << 5) - h + str.charCodeAt(i);
    h |= 0; // to 32-bit
  }
  return Math.abs(h);
}

function initialFrom(name, phone) {
  const src = (name || phone || '?').trim();
  if (!src) return '?';
  // Take first alpha char, fallback to first digit
  const alpha = src.match(/[a-zA-Z]/);
  if (alpha) return alpha[0].toUpperCase();
  return src[0];
}

/**
 * Circular avatar with deterministic gradient based on lead.id (or phone).
 * Props: lead, size ('sm' 48px | 'md' 56px | 'xs' 32px), showStatus (bool)
 */
export const LeadAvatar = ({ lead, size = 'sm', ring = false, statusClass = '' }) => {
  const id = lead?.id || lead?.phone || 'x';
  const [a, b] = GRADIENTS[hashString(String(id)) % GRADIENTS.length];
  const letter = initialFrom(lead?.name, lead?.phone);
  const sizeCls = {
    xs: 'w-8 h-8 text-xs',
    sm: 'w-12 h-12 text-lg',
    md: 'w-14 h-14 text-xl',
  }[size] || 'w-12 h-12 text-lg';

  return (
    <div className="relative shrink-0" data-testid={`lead-avatar-${lead?.id || ''}`}>
      <div
        className={`${sizeCls} rounded-full flex items-center justify-center text-white font-semibold shadow-md ${ring ? 'ring-2 ring-red-500/50' : ''}`}
        style={{ backgroundImage: `linear-gradient(135deg, ${a}, ${b})` }}
      >
        {letter}
      </div>
      {statusClass && (
        <span className={`absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-slate-950 ${statusClass}`} />
      )}
    </div>
  );
};
