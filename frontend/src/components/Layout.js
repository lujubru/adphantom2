import React, { useState, useEffect } from 'react';
import { Navigate, Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Target, LogOut, BarChart, Globe, Users, UserCog, Sun, Moon, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';

const ALL_NAV_ITEMS = [
  { path: '/dashboard', label: 'Panel', icon: LayoutDashboard, roles: ['admin'] },
  { path: '/leads-crm', label: 'CRM', icon: Users, roles: ['admin', 'cajero'] },
  { path: '/campaigns', label: 'Campañas', icon: Target, roles: ['admin'] },
  { path: '/wa-landings', label: 'Landings', icon: Globe, roles: ['admin'] },
  { path: '/wa-landing-forensics', label: 'WAForensics', icon: Globe, roles: ['admin'] },
  { path: '/analytics', label: 'Analytics', icon: BarChart, roles: ['admin'] },
  { path: '/ai-generator', label: 'AI Tools', icon: Sparkles, roles: ['admin'] },
  { path: '/user-management', label: 'Usuarios', icon: UserCog, roles: ['admin'] },
];

// Rutas que el cajero NO puede visitar
const ADMIN_ONLY_PATHS = [
  '/dashboard', '/campaigns', '/custom-filters', '/reports',
  '/analytics', '/ai-intelligence', '/ai-generator',
  '/click-forensics', '/whatsapp-crm', '/wa-landings', '/wa-landing-forensics',
  '/user-management',
];

const Layout = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const token = localStorage.getItem('token');
  const role = localStorage.getItem('role') || 'admin';
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('theme');
    return saved ? saved === 'dark' : true;
  });

  useEffect(() => {
    localStorage.setItem('theme', darkMode ? 'dark' : 'light');
    if (darkMode) {
      document.documentElement.classList.add('dark');
      document.documentElement.classList.remove('light');
    } else {
      document.documentElement.classList.remove('dark');
      document.documentElement.classList.add('light');
    }
  }, [darkMode]);

  if (!token) return <Navigate to="/login" />;

  // Bloquear rutas admin para cajeros
  if (role === 'cajero' && ADMIN_ONLY_PATHS.includes(location.pathname)) {
    return <Navigate to="/leads-crm" replace />;
  }

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('role');
    navigate('/login');
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
                <img src="/logo.png" alt="AdPhantom" className="h-10 w-10 rounded-lg object-contain" />
                <span className={`font-bold text-lg ${darkMode ? 'text-white' : 'text-gray-900'}`}>AdPhantom</span>
              </div>
              <div className="hidden md:flex space-x-1">
                {navItems.map((item) => {
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
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Button
                onClick={() => setDarkMode(!darkMode)}
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
        <Outlet context={{ darkMode }} />
      </main>
    </div>
  );
};

export default Layout;
