import React from 'react';
import { Navigate, Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Target, LogOut, ShieldCheck, BarChart, Globe, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';

const ALL_NAV_ITEMS = [
  { path: '/dashboard', label: 'Panel', icon: LayoutDashboard, roles: ['admin'] },
  { path: '/leads-crm', label: 'CRM', icon: Users, roles: ['admin', 'cajero'] },
  { path: '/campaigns', label: 'Campañas', icon: Target, roles: ['admin'] },
  { path: '/wa-landings', label: 'Landings', icon: Globe, roles: ['admin'] },
  { path: '/wa-landing-forensics', label: 'WAForensics', icon: Globe, roles: ['admin'] },
  { path: '/analytics', label: 'Analytics', icon: BarChart, roles: ['admin'] },
];

// Rutas que el cajero NO puede visitar
const ADMIN_ONLY_PATHS = [
  '/dashboard', '/campaigns', '/custom-filters', '/reports',
  '/analytics', '/ai-intelligence', '/ai-generator',
  '/click-forensics', '/whatsapp-crm', '/wa-landings', '/wa-landing-forensics',
];

const Layout = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const token = localStorage.getItem('token');
  const role = localStorage.getItem('role') || 'admin';

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
    <div className="min-h-screen bg-slate-950">
      <nav data-testid="main-nav" className="bg-slate-900/50 backdrop-blur-xl border-b border-slate-800 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-8">
              <div className="flex items-center space-x-2">
                <div className="bg-gradient-to-br from-blue-500 to-cyan-500 p-2 rounded-lg">
                  <ShieldCheck className="w-5 h-5 text-white" />
                </div>
                <span className="text-white font-bold text-lg">Traffic Guardian</span>
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
                        isActive ? 'bg-slate-800 text-white' : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
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
              {role === 'cajero' && (
                <span className="text-xs text-slate-500 bg-slate-800 px-2 py-1 rounded-md">Cajero</span>
              )}
              <Button
                onClick={handleLogout}
                data-testid="logout-button"
                variant="ghost"
                className="text-slate-400 hover:text-white hover:bg-slate-800"
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
