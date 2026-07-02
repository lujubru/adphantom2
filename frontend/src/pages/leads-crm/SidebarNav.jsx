import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BarChart3, RefreshCw, Radio, LogOut, Download, Bell, BellOff,
  Volume2, VolumeX, Tag as TagIcon, Home, Sun, Moon, DownloadCloud,
} from 'lucide-react';

/**
 * Kommo-style vertical sidebar for the cajero CRM.
 * Fixed 56px wide column with icon buttons and hover tooltips.
 * Renders only on desktop (md+).
 */
const IconButton = ({ icon: Icon, label, onClick, active = false, badge, testId, danger = false, accent = false, disabled = false }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    data-testid={testId}
    className={`group relative w-11 h-11 flex items-center justify-center rounded-xl transition-all
      ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}
      ${active
        ? 'bg-emerald-500/20 text-emerald-300 shadow-inner'
        : danger
          ? 'text-slate-400 hover:text-red-300 hover:bg-red-500/10'
          : accent
            ? 'text-emerald-300 hover:bg-emerald-500/10'
            : 'text-slate-400 hover:text-white hover:bg-slate-800'}
    `}
    aria-label={label}
    title={label}
  >
    <Icon className="w-5 h-5" strokeWidth={1.8} />
    {typeof badge === 'number' && badge > 0 && (
      <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center shadow-md">
        {badge > 99 ? '99+' : badge}
      </span>
    )}
    {/* Tooltip on hover */}
    <span className="pointer-events-none absolute left-full ml-2 top-1/2 -translate-y-1/2 px-2 py-1 rounded-md bg-slate-800 text-slate-100 text-[11px] font-medium whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity shadow-lg z-50 border border-slate-700">
      {label}
    </span>
  </button>
);

const Divider = () => <div className="w-6 h-px bg-slate-800" />;

export const SidebarNav = ({
  currentUser,
  darkMode,
  onThemeToggle,
  onFunnelOpen,
  soundEnabled,
  onSoundToggle,
  notifyEnabled,
  onNotifyToggle,
  pwaPrompt,
  pwaInstalled,
  onInstall,
  onBroadcast,
  onTagsOpen,
  onRefresh,
  onContactsExport,
  unreadCount = 0,
  onBackToLines,
  showBackToLines = false,
}) => {
  const navigate = useNavigate();
  const handleLogout = () => {
    try { localStorage.removeItem('access_token'); } catch { /* silent */ }
    navigate('/login');
  };

  const canBroadcast = currentUser?.role === 'admin' || (currentUser?.line_ids && currentUser.line_ids.length > 0);

  return (
    <aside
      className="hidden md:flex shrink-0 w-14 flex-col items-center py-3 gap-1 border-r border-slate-800 bg-slate-950/80 backdrop-blur"
      data-testid="cajero-sidebar-nav"
    >
      {showBackToLines && (
        <>
          <IconButton icon={Home} label="Volver a líneas" onClick={onBackToLines} testId="sidebar-back-to-lines" />
          <Divider />
        </>
      )}

      <IconButton
        icon={RefreshCw}
        label="Actualizar leads"
        onClick={onRefresh}
        testId="sidebar-refresh"
        badge={unreadCount}
      />

      <IconButton
        icon={BarChart3}
        label="Embudo de conversión"
        onClick={onFunnelOpen}
        testId="sidebar-funnel"
      />

      {canBroadcast && (
        <IconButton
          icon={Radio}
          label="Envío masivo (broadcast)"
          onClick={onBroadcast}
          testId="sidebar-broadcast"
          accent
        />
      )}

      {canBroadcast && (
        <IconButton
          icon={TagIcon}
          label="Gestionar etiquetas"
          onClick={onTagsOpen}
          testId="sidebar-tags"
          accent
        />
      )}

      <Divider />

      <IconButton
        icon={soundEnabled ? Volume2 : VolumeX}
        label={soundEnabled ? 'Silenciar sonido' : 'Activar sonido de notificación'}
        onClick={onSoundToggle}
        active={soundEnabled}
        testId="sidebar-sound"
      />

      <IconButton
        icon={notifyEnabled ? Bell : BellOff}
        label={notifyEnabled ? 'Desactivar notificaciones' : 'Activar notificaciones'}
        onClick={onNotifyToggle}
        active={notifyEnabled}
        testId="sidebar-notify"
      />

      {onContactsExport && currentUser?.role === 'admin' && (
        <IconButton
          icon={Download}
          label="Exportar contactos"
          onClick={onContactsExport}
          testId="sidebar-export"
        />
      )}

      {pwaPrompt && !pwaInstalled && (
        <IconButton
          icon={DownloadCloud}
          label="Instalar app"
          onClick={onInstall}
          testId="sidebar-install"
          accent
        />
      )}

      <div className="flex-1" />

      {onThemeToggle && (
        <IconButton
          icon={darkMode ? Sun : Moon}
          label={darkMode ? 'Modo claro' : 'Modo oscuro'}
          onClick={onThemeToggle}
          testId="sidebar-theme"
        />
      )}

      <IconButton
        icon={LogOut}
        label="Cerrar sesión"
        onClick={handleLogout}
        testId="sidebar-logout"
        danger
      />
    </aside>
  );
};
