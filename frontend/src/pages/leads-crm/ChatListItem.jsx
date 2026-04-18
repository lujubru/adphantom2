import React from 'react';
import { STATUS_CONFIG, BADGE_COLORS } from './constants';
import { formatRelative } from './utils';

export const ChatListItem = ({ lead, onClick }) => {
  const cfg = STATUS_CONFIG[lead.status] || STATUS_CONFIG.nuevo;
  const hasUnread = lead.unread_count > 0 || lead.has_unread_messages;
  const adBadge = lead.ad_badge;
  const adColor = adBadge ? (BADGE_COLORS[adBadge.color] || BADGE_COLORS.blue) : null;
  const lastTime = lead.last_interaction || lead.created_at;
  const relTime = formatRelative(lastTime);

  return (
    <button
      type="button"
      onClick={() => onClick(lead)}
      data-testid={`chat-list-item-${lead.id}`}
      className="w-full flex items-center gap-3 px-3 py-3 active:bg-slate-800/70 hover:bg-slate-800/40 transition-colors text-left border-b border-slate-800/60"
    >
      <div className="relative shrink-0">
        <div className={`w-12 h-12 rounded-full flex items-center justify-center text-white font-semibold ${cfg.dot} bg-opacity-80`}>
          {(lead.name || '?').slice(0, 1).toUpperCase()}
        </div>
        <span className={`absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-slate-950 ${cfg.dot}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className="text-white text-sm font-medium truncate">{lead.name || lead.phone}</span>
          <span className={`text-[10px] shrink-0 ${hasUnread ? 'text-emerald-400 font-semibold' : 'text-slate-500'}`}>{relTime}</span>
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-xs text-slate-400 truncate flex-1">
            {lead.phone}{lead.line_name ? ` · ${lead.line_name}` : ''}
          </span>
          {adBadge && (
            <span className={`inline-flex items-center gap-0.5 px-1 py-0.5 rounded border ${adColor.border} ${adColor.bg} text-[9px] font-semibold ${adColor.text} max-w-[80px] truncate`}>
              📢 {adBadge.label}
            </span>
          )}
          {hasUnread && (
            <span className="inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-emerald-500 text-white text-[10px] font-bold shrink-0">
              {lead.unread_count || 1}
            </span>
          )}
        </div>
      </div>
    </button>
  );
};
