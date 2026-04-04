import React, { useState, useEffect } from 'react';
import { UserPlus, Edit2, Trash2, X, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import api from '@/utils/api';
import { toast } from 'sonner';
import { useTheme } from '@/contexts/ThemeContext';

const UserManagement = () => {
  const { darkMode } = useTheme();
  const [users, setUsers] = useState([]);
  const [lines, setLines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    role: 'cajero',
    line_ids: [],
    welcome_message: `¡Buenas!👋 Trabajamos con las plataformas MÁS COMPLETAS del país!  
💟 ¡GANAMOS! 💟 💜 GANAMOSvip 💜 🥇 OROPURO 🥇  
ℹ MINIMOS: $2000 Acreditación // $5000 Retiro. 
🏦 Retiras tus ganancias UNA vez cada 24hs! 
⛔ No abonamos ni trabajamos con Ruletas 
🎁B0N0 ¡Beneficio de bienvenida activado! B0N0🎁  
✨¡Decime tu nombre para generar el usuario!✨`,
    user_message: `¡Te dejo tus datos de acceso!:
👤Usuario: [CLIPBOARD]
🔑Contraseña: hola123
🌐Link de acceso: https://ganamosnet.org
🌐Link de acceso: https://oropuro.net
🌐Link de acceso: https://1ganamos.vip
¡Te dejo el CBU para que puedas cargar! 
Le envio nuestros datos de cuenta 👇`,
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [usersRes, linesRes] = await Promise.all([
        api.get('/auth/users'),
        api.get('/crm/lines')
      ]);
      setUsers(usersRes.data);
      setLines(linesRes.data);
    } catch (err) {
      toast.error('Error cargando datos');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingUser) {
        await api.put(`/auth/users/${editingUser.id}`, formData);
        toast.success('Usuario actualizado');
      } else {
        await api.post('/auth/users', formData);
        toast.success('Usuario creado');
      }
      setShowModal(false);
      setEditingUser(null);
      resetForm();
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error guardando usuario');
    }
  };

  const handleDelete = async (userId) => {
    if (!window.confirm('¿Eliminar este usuario?')) return;
    try {
      await api.delete(`/auth/users/${userId}`);
      toast.success('Usuario eliminado');
      loadData();
    } catch (err) {
      toast.error('Error eliminando usuario');
    }
  };

  const handleEdit = (user) => {
    setEditingUser(user);
    setFormData({
      email: user.email,
      password: '',
      role: user.role,
      line_ids: user.line_ids || [],
      welcome_message: user.welcome_message || '',
      user_message: user.user_message || '',
    });
    setShowModal(true);
  };

  const resetForm = () => {
    setFormData({
      email: '',
      password: '',
      role: 'cajero',
      line_ids: [],
      welcome_message: `¡Buenas!👋 Trabajamos con las plataformas MÁS COMPLETAS del país!  
💟 ¡GANAMOS! 💟 💜 GANAMOSvip 💜 🥇 OROPURO 🥇  
ℹ MINIMOS: $2000 Acreditación // $5000 Retiro. 
🏦 Retiras tus ganancias UNA vez cada 24hs! 
⛔ No abonamos ni trabajamos con Ruletas 
🎁B0N0 ¡Beneficio de bienvenida activado! B0N0🎁  
✨¡Decime tu nombre para generar el usuario!✨`,
      user_message: `¡Te dejo tus datos de acceso!:
👤Usuario: [CLIPBOARD]
🔑Contraseña: hola123
🌐Link de acceso: https://ganamosnet.org
🌐Link de acceso: https://oropuro.net
🌐Link de acceso: https://1ganamos.vip
¡Te dejo el CBU para que puedas cargar! 
Le envio nuestros datos de cuenta 👇`,
    });
  };

  const toggleLine = (lineId) => {
    setFormData(prev => ({
      ...prev,
      line_ids: prev.line_ids.includes(lineId)
        ? prev.line_ids.filter(id => id !== lineId)
        : [...prev.line_ids, lineId]
    }));
  };

  const cardBg = darkMode ? 'bg-slate-900/50 border-slate-800' : 'bg-white border-gray-200';
  const textPrimary = darkMode ? 'text-white' : 'text-gray-900';
  const textSecondary = darkMode ? 'text-slate-400' : 'text-gray-600';
  const inputBg = darkMode ? 'bg-slate-800 border-slate-700 text-white' : 'bg-gray-50 border-gray-300 text-gray-900';

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-teal-500"></div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className={`text-2xl font-bold ${textPrimary}`}>Gestión de Usuarios</h1>
          <p className={textSecondary}>Crear y administrar usuarios del sistema</p>
        </div>
        <Button
          onClick={() => { resetForm(); setEditingUser(null); setShowModal(true); }}
          data-testid="create-user-btn"
          className="bg-teal-600 hover:bg-teal-700 text-white"
        >
          <UserPlus className="w-4 h-4 mr-2" />
          Nuevo Usuario
        </Button>
      </div>

      {/* Users Table */}
      <div className={`rounded-xl border ${cardBg} overflow-hidden`}>
        <table className="w-full">
          <thead className={darkMode ? 'bg-slate-800/50' : 'bg-gray-50'}>
            <tr>
              <th className={`px-6 py-4 text-left text-sm font-medium ${textSecondary}`}>Email</th>
              <th className={`px-6 py-4 text-left text-sm font-medium ${textSecondary}`}>Rol</th>
              <th className={`px-6 py-4 text-left text-sm font-medium ${textSecondary}`}>Líneas</th>
              <th className={`px-6 py-4 text-left text-sm font-medium ${textSecondary}`}>Estado</th>
              <th className={`px-6 py-4 text-right text-sm font-medium ${textSecondary}`}>Acciones</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {users.map(user => (
              <tr key={user.id} data-testid={`user-row-${user.id}`} className={darkMode ? 'hover:bg-slate-800/30' : 'hover:bg-gray-50'}>
                <td className={`px-6 py-4 ${textPrimary}`}>{user.email}</td>
                <td className="px-6 py-4">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    user.role === 'admin' 
                      ? 'bg-purple-500/20 text-purple-400' 
                      : 'bg-teal-500/20 text-teal-400'
                  }`}>
                    {user.role}
                  </span>
                </td>
                <td className={`px-6 py-4 ${textSecondary}`}>
                  {user.line_names?.join(', ') || '-'}
                </td>
                <td className="px-6 py-4">
                  <span className={`px-2 py-1 rounded-full text-xs ${
                    user.is_active !== false ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                  }`}>
                    {user.is_active !== false ? 'Activo' : 'Inactivo'}
                  </span>
                </td>
                <td className="px-6 py-4 text-right">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleEdit(user)}
                    data-testid={`edit-user-${user.id}`}
                    className={darkMode ? 'text-slate-400 hover:text-white' : 'text-gray-600 hover:text-gray-900'}
                  >
                    <Edit2 className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDelete(user.id)}
                    data-testid={`delete-user-${user.id}`}
                    className="text-red-400 hover:text-red-300"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {users.length === 0 && (
          <div className={`text-center py-12 ${textSecondary}`}>
            No hay usuarios registrados
          </div>
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className={`rounded-xl border ${cardBg} w-full max-w-2xl max-h-[90vh] overflow-y-auto`}>
            <div className={`flex justify-between items-center p-6 border-b ${darkMode ? 'border-slate-800' : 'border-gray-200'}`}>
              <h2 className={`text-xl font-bold ${textPrimary}`}>
                {editingUser ? 'Editar Usuario' : 'Nuevo Usuario'}
              </h2>
              <Button variant="ghost" size="icon" onClick={() => setShowModal(false)}>
                <X className="w-5 h-5" />
              </Button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-6">
              {/* Email */}
              <div>
                <label className={`block text-sm font-medium mb-2 ${textSecondary}`}>Email</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={e => setFormData(prev => ({ ...prev, email: e.target.value }))}
                  className={`w-full px-4 py-2 rounded-lg border ${inputBg}`}
                  data-testid="user-email-input"
                  required
                />
              </div>

              {/* Password */}
              <div>
                <label className={`block text-sm font-medium mb-2 ${textSecondary}`}>
                  Contraseña {editingUser && '(dejar vacío para no cambiar)'}
                </label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={e => setFormData(prev => ({ ...prev, password: e.target.value }))}
                  className={`w-full px-4 py-2 rounded-lg border ${inputBg}`}
                  data-testid="user-password-input"
                  {...(!editingUser && { required: true })}
                />
              </div>

              {/* Role */}
              <div>
                <label className={`block text-sm font-medium mb-2 ${textSecondary}`}>Rol</label>
                <select
                  value={formData.role}
                  onChange={e => setFormData(prev => ({ ...prev, role: e.target.value }))}
                  className={`w-full px-4 py-2 rounded-lg border ${inputBg}`}
                  data-testid="user-role-select"
                >
                  <option value="cajero">Cajero</option>
                  <option value="admin">Admin</option>
                </select>
              </div>

              {/* Lines Selection (only for cajero) */}
              {formData.role === 'cajero' && (
                <div>
                  <label className={`block text-sm font-medium mb-2 ${textSecondary}`}>Líneas asignadas</label>
                  <div className="grid grid-cols-2 gap-2">
                    {lines.map(line => (
                      <button
                        key={line.id}
                        type="button"
                        onClick={() => toggleLine(line.id)}
                        className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
                          formData.line_ids.includes(line.id)
                            ? 'bg-teal-500/20 border-teal-500 text-teal-400'
                            : (darkMode ? 'border-slate-700 text-slate-400 hover:border-slate-600' : 'border-gray-300 text-gray-600 hover:border-gray-400')
                        }`}
                        data-testid={`line-toggle-${line.id}`}
                      >
                        <span className="text-sm">{line.name}</span>
                        {formData.line_ids.includes(line.id) && <Check className="w-4 h-4" />}
                      </button>
                    ))}
                  </div>
                  {lines.length === 0 && (
                    <p className={`text-sm ${textSecondary}`}>No hay líneas creadas</p>
                  )}
                </div>
              )}

              {/* Welcome Message (only for cajero) */}
              {formData.role === 'cajero' && (
                <div>
                  <label className={`block text-sm font-medium mb-2 ${textSecondary}`}>
                    Mensaje de Bienvenida
                  </label>
                  <textarea
                    value={formData.welcome_message}
                    onChange={e => setFormData(prev => ({ ...prev, welcome_message: e.target.value }))}
                    className={`w-full px-4 py-2 rounded-lg border ${inputBg} h-40 font-mono text-sm`}
                    data-testid="user-welcome-message"
                  />
                </div>
              )}

              {/* User Message (only for cajero) */}
              {formData.role === 'cajero' && (
                <div>
                  <label className={`block text-sm font-medium mb-2 ${textSecondary}`}>
                    Mensaje de Usuario <span className="text-xs text-teal-400">(usa [CLIPBOARD] para el usuario copiado)</span>
                  </label>
                  <textarea
                    value={formData.user_message}
                    onChange={e => setFormData(prev => ({ ...prev, user_message: e.target.value }))}
                    className={`w-full px-4 py-2 rounded-lg border ${inputBg} h-40 font-mono text-sm`}
                    data-testid="user-user-message"
                  />
                </div>
              )}

              <div className="flex justify-end gap-3 pt-4">
                <Button type="button" variant="ghost" onClick={() => setShowModal(false)}>
                  Cancelar
                </Button>
                <Button type="submit" className="bg-teal-600 hover:bg-teal-700 text-white" data-testid="save-user-btn">
                  {editingUser ? 'Guardar Cambios' : 'Crear Usuario'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagement;
