import React, { useState, useEffect, useRef } from 'react';
import { Navigate, Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Target, LogOut, BarChart, Globe, Users, UserCog, Sun, Moon, Sparkles, Activity, TrendingUp, Megaphone, Wallet, Settings, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useTheme } from '@/contexts/ThemeContext';

const ALL_NAV_ITEMS = [
  { path: '/dashboard', label: 'Panel', icon: LayoutDashboard, roles: ['admin'] },
  { path: '/leads-crm', label: 'CRM', icon: Users, roles: ['admin', 'cajero'] },
  { path: '/broadcasts', label: 'Broadcasts', icon: Megaphone, roles: ['admin', 'cajero'] },
  { path: '/finanzas', label: 'Finanzas', icon: Wallet, roles: ['admin', 'cajero'] },
  { path: '/mi-configuracion', label: 'Mi config', icon: Settings, roles: ['admin', 'cajero'] },
  { path: '/campaigns', label: 'Campañas', icon: Target, roles: ['admin'] },
  { path: '/wa-landings', label: 'Landings', icon: Globe, roles: ['admin'] },
  { path: '/wa-landing-forensics', label: 'WAForensics', icon: Globe, roles: ['admin'] },
  { path: '/analytics', label: 'Analytics', icon: BarChart, roles: ['admin'] },
  { path: '/ai-generator', label: 'AI Tools', icon: Sparkles, roles: ['admin'] },
  { path: '/user-management', label: 'Usuarios', icon: UserCog, roles: ['admin'] },
  { path: '/meta-diagnostics', label: 'Meta CAPI', icon: Activity, roles: ['admin'] },
  { path: '/meta-insights', label: 'Meta Insights', icon: TrendingUp, roles: ['admin'] },
];

// Rutas que el cajero NO puede visitar
const ADMIN_ONLY_PATHS = [
  '/dashboard', '/campaigns', '/custom-filters', '/reports',
  '/analytics', '/ai-intelligence', '/ai-generator',
  '/click-forensics', '/whatsapp-crm', '/wa-landings', '/wa-landing-forensics',
  '/user-management',
  '/meta-diagnostics',
  '/meta-insights',
];

// Rutas explícitamente permitidas para cajero (whitelist gana siempre).
// Esto evita cualquier confusión cuando agregamos features nuevas:
// si está en esta lista, el cajero siempre puede entrar, incluso si por
// error alguien la sumara a ADMIN_ONLY_PATHS más adelante.
const CAJERO_ALLOWED_PATHS = [
  '/leads-crm',
  '/broadcasts',
  '/finanzas',
  '/mi-configuracion',
];

const Layout = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const token = localStorage.getItem('token');
  const role = localStorage.getItem('role') || 'admin';
  const { darkMode, toggleTheme } = useTheme();

  const [activeDropdown, setActiveDropdown] = useState(null); // 'marketing' | 'metrics' | 'config' | null
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (activeDropdown && dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setActiveDropdown(null);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [activeDropdown]);

  if (!token) return <Navigate to="/login" />;

  // Bloquear rutas admin para cajeros — pero la whitelist gana siempre.
  if (
    role === 'cajero'
    && ADMIN_ONLY_PATHS.includes(location.pathname)
    && !CAJERO_ALLOWED_PATHS.includes(location.pathname)
  ) {
    return <Navigate to="/leads-crm" replace />;
  }

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    navigate('/login');
  };

  const handleDropdownToggle = (key) => {
    setActiveDropdown(prev => prev === key ? null : key);
  };

  const navItems = ALL_NAV_ITEMS.filter(item => item.roles.includes(role));

  return (
    <div className={`min-h-screen transition-colors duration-300 ${darkMode ? 'bg-slate-950' : 'bg-gray-100'}`}>
      <nav data-testid="main-nav" className={`backdrop-blur-xl border-b sticky top-0 z-50 transition-colors duration-300 ${
        darkMode ? 'bg-slate-900/50 border-slate-800' : 'bg-white/80 border-gray-200'
      }`}>
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-8">
              <div className="flex items-center space-x-2">
                <img src="/logo.png" alt="aplicacion" className="h-10 w-10 rounded-lg object-contain" />
                <span className={`font-bold text-lg ${darkMode ? 'text-white' : 'text-gray-900'}`}>aplicacion</span>
              </div>
              <div className="hidden md:flex space-x-1 items-center" ref={dropdownRef}>
                {role === 'cajero' ? (
                  navItems.map((item) => {
                    const Icon = item.icon;
                    const isActive = location.pathname === item.path;
                    return (
                      <Link
                        key={item.path}
                        to={item.path}
                        data-testid={`nav-${item.path.slice(1)}`}
                        className={`flex items-center space-x-2 px-3 py-2 rounded-lg transition-colors ${
                          isActive 
                            ? (darkMode ? 'bg-slate-800 text-white' : 'bg-teal-100 text-teal-800') 
                            : (darkMode ? 'text-slate-400 hover:text-white hover:bg-slate-800/50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100')
                        }`}
                      >
                        <Icon className="w-4 h-4" />
                        <span className="text-sm font-medium">{item.label}</span>
                      </Link>
                    );
                  })
                ) : (
                  <>
                    {[
                      { path: '/dashboard', label: 'Panel', icon: LayoutDashboard },
                      { path: '/leads-crm', label: 'CRM', icon: Users },
                      { path: '/broadcasts', label: 'Broadcasts', icon: Megaphone },
                      { path: '/finanzas', label: 'Finanzas', icon: Wallet },
                    ].map((item) => {
                      const Icon = item.icon;
                      const isActive = location.pathname === item.path;
                      return (
                        <Link
                          key={item.path}
                          to={item.path}
                          data-testid={`nav-${item.path.slice(1)}`}
                          className={`flex items-center space-x-2 px-3 py-2 rounded-lg transition-colors ${
                            isActive 
                              ? (darkMode ? 'bg-slate-800 text-white' : 'bg-teal-100 text-teal-800') 
                              : (darkMode ? 'text-slate-400 hover:text-white hover:bg-slate-800/50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100')
                          }`}
                        >
                          <Icon className="w-4 h-4" />
                          <span className="text-sm font-medium">{item.label}</span>
                        </Link>
                      );
                    })}

                    {[
                      {
                        label: 'Marketing',
                        key: 'marketing',
                        icon: Target,
                        items: [
                          { path: '/campaigns', label: 'Campañas', icon: Target },
                          { path: '/wa-landings', label: 'Landings', icon: Globe },
                          { path: '/wa-landing-forensics', label: 'WAForensics', icon: Globe },
                        ]
                      },
                      {
                        label: 'Métricas',
                        key: 'metrics',
                        icon: BarChart,
                        items: [
                          { path: '/analytics', label: 'Analytics', icon: BarChart },
                          { path: '/meta-diagnostics', label: 'Meta CAPI', icon: Activity },
                          { path: '/meta-insights', label: 'Meta Insights', icon: TrendingUp },
                        ]
                      },
                      {
                        label: 'Configuración',
                        key: 'config',
                        icon: Settings,
                        items: [
                          { path: '/user-management', label: 'Usuarios', icon: UserCog },
                          { path: '/ai-generator', label: 'AI Tools', icon: Sparkles },
                          { path: '/mi-configuracion', label: 'Mi config', icon: Settings },
                        ]
                      }
                    ].map((group) => {
                      const GroupIcon = group.icon;
                      const isDropdownOpen = activeDropdown === group.key;
                      const isAnyChildActive = group.items.some(item => location.pathname === item.path);
                      
                      return (
                        <div key={group.key} className="relative">
                          <button
                            onClick={() => handleDropdownToggle(group.key)}
                            className={`flex items-center space-x-1.5 px-3 py-2 rounded-lg transition-colors ${
                              isAnyChildActive
                                ? (darkMode ? 'bg-slate-800 text-white' : 'bg-teal-100 text-teal-800') 
                                : (darkMode ? 'text-slate-400 hover:text-white hover:bg-slate-800/50' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100')
                            }`}
                          >
                            <GroupIcon className="w-4 h-4" />
                            <span className="text-sm font-medium">{group.label}</span>
                            <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${isDropdownOpen ? 'rotate-180' : ''}`} />
                          </button>

                          {isDropdownOpen && (
                            <div className={`absolute left-0 mt-1.5 w-48 rounded-lg border shadow-xl z-50 py-1 transition-all duration-200 ${
                              darkMode ? 'bg-slate-900 border-slate-800 text-white' : 'bg-white border-gray-205 text-gray-800'
                            }`}>
                              {group.items.map((item) => {
                                const ItemIcon = item.icon;
                                const isItemActive = location.pathname === item.path;
                                return (
                                  <Link
                                    key={item.path}
                                    to={item.path}
                                    onClick={() => setActiveDropdown(null)}
                                    className={`flex items-center space-x-2 px-3 py-2 text-sm transition-colors ${
                                      isItemActive
                                        ? (darkMode ? 'bg-slate-850 text-white' : 'bg-teal-50 text-teal-900 font-semibold')
                                        : (darkMode ? 'hover:bg-slate-800/50 text-slate-300 hover:text-white' : 'hover:bg-gray-100 text-gray-700 hover:text-gray-900')
                                    }`}
                                  >
                                    <ItemIcon className="w-4 h-4 shrink-0" />
                                    <span>{item.label}</span>
                                  </Link>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </>
                )}
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Button
                onClick={toggleTheme}
                data-testid="theme-toggle"
                variant="ghost"
                size="icon"
                className={darkMode ? 'text-slate-400 hover:text-white hover:bg-slate-800' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'}
              >
                {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              </Button>
              {role === 'cajero' && (
                <span className={`text-xs px-2 py-1 rounded-md ${darkMode ? 'text-slate-500 bg-slate-800' : 'text-gray-500 bg-gray-200'}`}>Cajero</span>
              )}
              <Button
                onClick={handleLogout}
                data-testid="logout-button"
                variant="ghost"
                className={darkMode ? 'text-slate-400 hover:text-white hover:bg-slate-800' : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'}
              >
                <LogOut className="w-4 h-4 mr-2" />
                Salir
              </Button>
            </div>
          </div>
        </div>
      </nav>
      <main>
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
