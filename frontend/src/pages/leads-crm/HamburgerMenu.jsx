import React, { useState, useEffect, useRef } from 'react';
import {
  Menu, X, BarChart3, Sun, Moon, RefreshCw, Radio, LogOut,
  Download, Bell, BellOff, Volume2, VolumeX,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

/**
 * Floating hamburger menu for the cajero desktop view.
 *
 * Replaces the old top bar so the chat takes the full vertical space
 * (cajeros often work on small netbooks). The button itself is a tiny
 * 32x32 pin in the top-left corner; clicking it opens a side panel
 * with all the actions.
 */
export const HamburgerMenu = ({
  currentUser,
  darkMode,
  funnel,
  onFunnelOpen,
  soundEnabled,
  onSoundToggle,
  notifyEnabled,
  onNotifyToggle,
  pwaPrompt,
  pwaInstalled,
  onInstall,
  onBroadcast,
  onRefresh,
  onContactsExport,
  unreadCount = 0,
}) => {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    document.addEventListener('touchstart', handler);
    return () => {
      document.removeEventListener('mousedown', handler);
      document.removeEventListener('touchstart', handler);
    };
  }, [open]);

  const close = () => setOpen(false);

  const action = (fn) => () => { try { fn?.(); } finally { close(); } };

  const handleLogout = () => {
    try { localStorage.removeItem('access_token'); } catch { /* silent */ }
    navigate('/login');
  };

  // Toggle theme via window event (avoids prop-drilling). The ThemeContext
  // already exposes a global toggle in some places — fallback to dispatch.
  const handleThemeToggle = () => {
    try {
      // Try the registered global toggle first.
      if (typeof window.__toggleTheme === 'function') {
        window.__toggleTheme();
      } else {
        // Last-resort: just flip class on <html>
        document.documentElement.classList.toggle('dark');
      }
    } catch { /* silent */ }
  };

  const itemBase = 'flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm transition-colors';
  const itemNormal = darkMode
    ? 'text-slate-200 hover:bg-slate-800 active:bg-slate-700'
    : 'text-gray-700 hover:bg-gray-100 active:bg-gray-200';
  const itemDanger = darkMode
    ? 'text-rose-300 hover:bg-rose-500/15'
    : 'text-rose-600 hover:bg-rose-50';

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        data-testid="hamburger-btn"
        title="Menú"
        className={`fixed top-[100px] left-2 z-40 w-9 h-9 rounded-full flex items-center justify-center shadow-md transition-all ${
          darkMode ? 'bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200' : 'bg-white hover:bg-gray-50 border border-gray-200 text-gray-700'
        }`}
      >
        <Menu className="w-4 h-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center animate-pulse">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
          <div
            ref={ref}
            data-testid="hamburger-panel"
            className={`absolute top-0 left-0 h-full w-[280px] shadow-2xl flex flex-col ${
              darkMode ? 'bg-slate-950 border-r border-slate-800' : 'bg-white border-r border-gray-200'
            }`}
          >
            <div className={`px-4 py-3 flex items-center justify-between border-b ${darkMode ? 'border-slate-800' : 'border-gray-200'}`}>
              <div className="min-w-0 flex-1">
                <p className={`text-xs ${darkMode ? 'text-slate-500' : 'text-gray-500'}`}>Hola,</p>
                <p className={`text-sm font-medium truncate ${darkMode ? 'text-white' : 'text-gray-900'}`} title={currentUser?.email}>
                  {currentUser?.email}
                </p>
              </div>
              <button
                onClick={close}
                className={`p-1.5 rounded-lg ${darkMode ? 'hover:bg-slate-800 text-slate-400' : 'hover:bg-gray-100 text-gray-600'}`}
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
              {funnel && (
                <button onClick={action(onFunnelOpen)} className={`${itemBase} ${itemNormal}`} data-testid="hm-funnel">
                  <BarChart3 className="w-4 h-4 shrink-0" />
                  <span>Embudo de conversión</span>
                </button>
              )}

              <button onClick={action(handleThemeToggle)} className={`${itemBase} ${itemNormal}`} data-testid="hm-theme">
                {darkMode ? <Sun className="w-4 h-4 shrink-0" /> : <Moon className="w-4 h-4 shrink-0" />}
                <span>{darkMode ? 'Tema claro' : 'Tema oscuro'}</span>
              </button>

              <button onClick={action(onNotifyToggle)} className={`${itemBase} ${itemNormal}`} data-testid="hm-notify">
                {notifyEnabled ? <Bell className="w-4 h-4 shrink-0 text-blue-400" /> : <BellOff className="w-4 h-4 shrink-0" />}
                <span>{notifyEnabled ? 'Notificaciones activas' : 'Activar notificaciones'}</span>
              </button>

              <button onClick={action(onSoundToggle)} className={`${itemBase} ${itemNormal}`} data-testid="hm-sound">
                {soundEnabled ? <Volume2 className="w-4 h-4 shrink-0 text-emerald-400" /> : <VolumeX className="w-4 h-4 shrink-0" />}
                <span>{soundEnabled ? 'Sonido activo' : 'Activar sonido'}</span>
              </button>

              <button onClick={action(onRefresh)} className={`${itemBase} ${itemNormal}`} data-testid="hm-refresh">
                <RefreshCw className="w-4 h-4 shrink-0" />
                <span>Actualizar leads</span>
              </button>

              {(currentUser?.role === 'admin' || (currentUser?.line_ids && currentUser.line_ids.length > 0)) && (
                <button onClick={action(onBroadcast)} className={`${itemBase} ${itemNormal}`} data-testid="hm-broadcast">
                  <Radio className="w-4 h-4 shrink-0 text-purple-400" />
                  <span>Envío masivo</span>
                </button>
              )}

              <button onClick={action(onContactsExport)} className={`${itemBase} ${itemNormal}`} data-testid="hm-contacts">
                <Download className="w-4 h-4 shrink-0 text-cyan-400" />
                <span>Descargar contactos (CSV)</span>
              </button>

              {pwaPrompt && !pwaInstalled && (
                <button onClick={action(onInstall)} className={`${itemBase} ${itemNormal}`} data-testid="hm-install">
                  <Download className="w-4 h-4 shrink-0 text-emerald-400" />
                  <span>Instalar app</span>
                </button>
              )}

              <div className={`my-2 border-t ${darkMode ? 'border-slate-800' : 'border-gray-200'}`} />

              <button onClick={handleLogout} className={`${itemBase} ${itemDanger}`} data-testid="hm-logout">
                <LogOut className="w-4 h-4 shrink-0" />
                <span>Cerrar sesión</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
