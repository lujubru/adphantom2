import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '@/utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

const handleSubmit = async (e) => {
  e.preventDefault();
  setLoading(true);
  try {
    const response = await api.post('/auth/login', { email, password });
    const token = response.data.access_token;
    localStorage.setItem('token', token);

    // Obtener rol
    const meResponse = await api.get('/auth/me');
    const role = meResponse.data.role || 'admin';
    localStorage.setItem('role', role);

    toast.success('Inicio de sesión exitoso');
    navigate(role === 'cajero' ? '/leads-crm' : '/dashboard');
  } catch (error) {
    toast.error(error.response?.data?.detail || 'Error al iniciar sesión');
  } finally {
    setLoading(false);
  }
};

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-slate-900/50 backdrop-blur-xl border border-slate-800 rounded-2xl p-8 shadow-2xl">
          <div className="flex flex-col items-center mb-8">
            <img src="/logo.png" alt="aplicacion" className="w-20 h-20 rounded-xl mb-4 object-contain" />
            <h1 className="text-2xl font-bold text-white mb-1">Black Guardian</h1>
            <p className="text-slate-400 text-sm">Portal de Administración</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="email" className="text-slate-300">Correo electrónico</Label>
              <Input
                id="email"
                type="email"
                data-testid="login-email-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="bg-slate-800/50 border-slate-700 text-white placeholder:text-slate-500 focus:border-blue-500"
                placeholder="tu@mailasignado.com"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-slate-300">Contraseña</Label>
              <Input
                id="password"
                type="password"
                data-testid="login-password-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="bg-slate-800/50 border-slate-700 text-white placeholder:text-slate-500 focus:border-blue-500"
                placeholder="********"
              />
            </div>

            <Button
              type="submit"
              data-testid="login-submit-button"
              disabled={loading}
              className="w-full bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white font-medium py-2.5"
            >
              {loading ? 'Iniciando sesión...' : 'Iniciar Sesión'}
            </Button>
          </form>


        </div>
      </div>
    </div>
  );
};

export default Login;
