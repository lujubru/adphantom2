import React from 'react';
import { STATUS_CONFIG, BADGE_COLORS } from './constants';
import { formatRelative } from './utils';
import { TagChipList } from './LeadTags';
import { LeadAvatar } from './LeadAvatar';

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
      <LeadAvatar lead={lead} size="sm" ring={hasUnread} statusClass={cfg.dot} />
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
        {Array.isArray(lead.tag_details) && lead.tag_details.length > 0 && (
          <div className="mt-1">
            <TagChipList tags={lead.tag_details} max={3} size="xs" />
          </div>
        )}
      </div>
    </button>
  );
};
