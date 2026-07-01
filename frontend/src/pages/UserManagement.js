import React, { useState, useEffect } from 'react';
import { UserPlus, Edit2, Trash2, X, Check, Plus, Phone, Landmark, Megaphone, Zap, GitMerge, RefreshCw, ArrowRight } from 'lucide-react';
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
  const [editingUserQuota, setEditingUserQuota] = useState(null);  // {used, quota, base, extra, period, remaining}
  const [topupAmount, setTopupAmount] = useState('');
  const [topupSaving, setTopupSaving] = useState(false);
  // Migración de chats entre líneas
  const [showMigrateModal, setShowMigrateModal] = useState(false);
  const [migrateSourceId, setMigrateSourceId] = useState('');
  const [migrateTargetId, setMigrateTargetId] = useState('');
  const [migrating, setMigrating] = useState(false);
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
    auto_welcome_enabled: true,
    derivation_message: 'Genial! Para realizar la carga te pido que envíes comprobante y usuario al siguiente número:',
    derivation_numbers: [],
    cbu_list: [],
    broadcast_monthly_quota: 0,
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

  const handleTopup = async () => {
    if (!editingUser?.id) return;
    const n = parseInt(topupAmount, 10);
    if (!n || n <= 0) { toast.error('Ingresá un número válido > 0'); return; }
    setTopupSaving(true);
    try {
      const { data } = await api.post(`/broadcasts/quota/${editingUser.id}/topup`, { extra: n });
      setEditingUserQuota(data?.state || null);
      setTopupAmount('');
      toast.success(`+${n} créditos añadidos a este período`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error en la recarga');
    } finally { setTopupSaving(false); }
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

  const handleEdit = async (user) => {
    setEditingUser(user);
    setEditingUserQuota(null);
    setTopupAmount('');
    if (user.role === 'cajero' && user.id) {
      // Pre-cargar el estado de cupo actual del cajero (para mostrar el "usados / cupo")
      try {
        const { data } = await api.get(`/broadcasts/quota/${user.id}`);
        setEditingUserQuota(data);
      } catch { /* admin viendo otro admin → ignorable */ }
    }
    setFormData({
      email: user.email,
      password: '',
      role: user.role,
      line_ids: user.line_ids || [],
      welcome_message: user.welcome_message || '',
      user_message: user.user_message || '',
      auto_welcome_enabled: user.auto_welcome_enabled !== false,
      derivation_message: user.derivation_message || 'Genial! Para realizar la carga te pido que envíes comprobante y usuario al siguiente número:',
      derivation_numbers: Array.isArray(user.derivation_numbers) ? user.derivation_numbers : [],
      cbu_list: Array.isArray(user.cbu_list) ? user.cbu_list : [],
      broadcast_monthly_quota: Number(user.broadcast_monthly_quota || 0),
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
      auto_welcome_enabled: true,
      derivation_message: 'Genial! Para realizar la carga te pido que envíes comprobante y usuario al siguiente número:',
      derivation_numbers: [],
      cbu_list: [],
      broadcast_monthly_quota: 0,
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

  const runMigration = async () => {
    if (!migrateSourceId || !migrateTargetId) {
      toast.error('Elegí origen y destino');
      return;
    }
    if (migrateSourceId === migrateTargetId) {
      toast.error('Origen y destino deben ser distintos');
      return;
    }
    const src = lines.find(l => l.id === migrateSourceId)?.name || 'origen';
    const tgt = lines.find(l => l.id === migrateTargetId)?.name || 'destino';
    if (!window.confirm(
      `¿Migrar TODOS los chats de "${src}" a "${tgt}"?\n\n` +
      `- Los leads/mensajes de "${src}" se moverán a "${tgt}".\n` +
      `- Si un mismo número existe en ambos lados, los mensajes se FUSIONAN en un solo chat (se conserva el lead más reciente).\n` +
      `- "${src}" quedará vacía pero seguirá activa.\n\n` +
      `Esta operación es IRREVERSIBLE.`
    )) return;
    setMigrating(true);
    try {
      const { data } = await api.post('/crm/lines/migrate', {
        source_line_id: migrateSourceId,
        target_line_id: migrateTargetId,
      });
      const s = data.stats || {};
      toast.success(
        `Migración OK · ${s.leads_moved || 0} movidos, ${s.leads_merged || 0} fusionados, ${s.messages_reassigned || 0} mensajes reasignados`
      );
      setShowMigrateModal(false);
      setMigrateSourceId('');
      setMigrateTargetId('');
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Error migrando');
    } finally {
      setMigrating(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className={`text-2xl font-bold ${textPrimary}`}>Gestión de Usuarios</h1>
          <p className={textSecondary}>Crear y administrar usuarios del sistema</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={() => { setMigrateSourceId(''); setMigrateTargetId(''); setShowMigrateModal(true); }}
            data-testid="migrate-lines-btn"
            variant="outline"
            className="border-amber-500/40 text-amber-300 bg-amber-500/10 hover:bg-amber-500/20"
          >
            <GitMerge className="w-4 h-4 mr-2" />
            Migrar chats
          </Button>
          <Button
            onClick={() => { resetForm(); setEditingUser(null); setShowModal(true); }}
            data-testid="create-user-btn"
            className="bg-teal-600 hover:bg-teal-700 text-white"
          >
            <UserPlus className="w-4 h-4 mr-2" />
            Nuevo Usuario
          </Button>
        </div>
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
                  <label className={`flex items-center gap-2 mb-3 cursor-pointer select-none ${textSecondary}`}>
                    <input
                      type="checkbox"
                      checked={formData.auto_welcome_enabled !== false}
                      onChange={e => setFormData(prev => ({ ...prev, auto_welcome_enabled: e.target.checked }))}
                      className="w-4 h-4 rounded border-slate-600 text-teal-500 focus:ring-teal-500 focus:ring-offset-0 bg-slate-800"
                      data-testid="user-auto-welcome-checkbox"
                    />
                    <span className="text-sm font-medium">
                      Bienvenida automática
                      <span className="text-xs font-normal text-slate-500 ml-2">
                        (si está desactivada, el cajero envía manualmente con el botón 👋 en el chat)
                      </span>
                    </span>
                  </label>
                  <label className={`block text-sm font-medium mb-2 ${textSecondary}`}>
                    Mensaje de Bienvenida <span className="text-xs text-teal-400">(se rota siempre — automática o manual)</span>
                  </label>
                  <textarea
                    value={formData.welcome_message}
                    onChange={e => setFormData(prev => ({ ...prev, welcome_message: e.target.value }))}
                    className={`w-full px-4 py-2 rounded-lg border ${inputBg} h-40 font-mono text-sm`}
                    data-testid="user-welcome-message"
                  />
                  <p className={`text-[11px] ${textSecondary} mt-1 leading-relaxed`}>
                    💡 <span className="font-medium">Múltiples variantes:</span> separalas con una línea que contenga solo <code className="px-1 bg-slate-800 text-teal-400 rounded">---</code> para que el sistema elija una al azar.
                    Si escribís una sola, se aplican micro-variaciones automáticas (saludo y emojis) para evitar patrones de automatización.
                  </p>
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

              {/* Derivation config (only for cajero) */}
              {formData.role === 'cajero' && (
                <div>
                  <label className={`block text-sm font-medium mb-2 ${textSecondary}`}>
                    Mensaje de Derivación <span className="text-xs text-amber-400">(se envía + el número elegido)</span>
                  </label>
                  <textarea
                    value={formData.derivation_message}
                    onChange={e => setFormData(prev => ({ ...prev, derivation_message: e.target.value }))}
                    className={`w-full px-4 py-2 rounded-lg border ${inputBg} h-20 font-mono text-sm`}
                    data-testid="user-derivation-message"
                    placeholder="Genial! Para realizar la carga te pido que envíes comprobante y usuario al siguiente número:"
                  />

                  <div className="mt-3 flex items-center justify-between">
                    <label className={`block text-sm font-medium ${textSecondary}`}>
                      Números de Derivación <span className="text-xs text-slate-500 font-normal">({formData.derivation_numbers.length})</span>
                    </label>
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => setFormData(prev => ({ ...prev, derivation_numbers: [...prev.derivation_numbers, ''] }))}
                      className="bg-amber-600 hover:bg-amber-500 text-white text-xs h-7 px-2"
                      data-testid="derivation-add-number-btn"
                    >
                      <Plus className="w-3.5 h-3.5 mr-1" /> Agregar número
                    </Button>
                  </div>

                  <div className="mt-2 max-h-72 overflow-y-auto pr-1 space-y-2 border border-slate-700/50 rounded-lg p-2 bg-slate-900/40" data-testid="derivation-numbers-list">
                    {formData.derivation_numbers.length === 0 ? (
                      <p className="text-xs text-slate-500 text-center py-3">
                        Sin números todavía. Tocá "Agregar número" para empezar.
                      </p>
                    ) : formData.derivation_numbers.map((num, idx) => (
                      <div key={idx} className="flex items-center gap-2" data-testid={`derivation-number-row-${idx}`}>
                        <span className="text-xs text-slate-500 font-mono w-6 shrink-0 text-right">{idx + 1}.</span>
                        <Phone className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                        <input
                          type="tel"
                          value={num}
                          onChange={e => {
                            const v = e.target.value;
                            setFormData(prev => ({
                              ...prev,
                              derivation_numbers: prev.derivation_numbers.map((n, i) => i === idx ? v : n)
                            }));
                          }}
                          placeholder="ej: 5491155554444"
                          className={`flex-1 px-3 py-1.5 rounded-md border ${inputBg} text-sm`}
                          data-testid={`derivation-number-input-${idx}`}
                        />
                        <button
                          type="button"
                          onClick={() => setFormData(prev => ({
                            ...prev,
                            derivation_numbers: prev.derivation_numbers.filter((_, i) => i !== idx)
                          }))}
                          className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded shrink-0"
                          data-testid={`derivation-number-remove-${idx}`}
                          title="Eliminar número"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                  <p className={`text-[11px] ${textSecondary} mt-1.5 leading-snug`}>
                    💡 Cargá los números sin el <code className="px-1 bg-slate-800 text-amber-300 rounded">+</code>, en formato internacional. El cajero va a poder elegir cualquiera desde un desplegable en el chat.
                  </p>
                </div>
              )}

              {/* CBU list (only for cajero) */}
              {formData.role === 'cajero' && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className={`block text-sm font-medium ${textSecondary}`}>
                      CBUs <span className="text-xs text-purple-400 font-normal">(envía CBU y nombre en mensajes separados)</span>
                      <span className="text-xs text-slate-500 font-normal ml-2">({formData.cbu_list.length})</span>
                    </label>
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => setFormData(prev => ({ ...prev, cbu_list: [...prev.cbu_list, { cbu: '', name: '' }] }))}
                      className="bg-purple-600 hover:bg-purple-500 text-white text-xs h-7 px-2"
                      data-testid="cbu-add-btn"
                    >
                      <Plus className="w-3.5 h-3.5 mr-1" /> Agregar CBU
                    </Button>
                  </div>

                  <div className="max-h-80 overflow-y-auto pr-1 space-y-2 border border-slate-700/50 rounded-lg p-2 bg-slate-900/40" data-testid="cbu-list">
                    {formData.cbu_list.length === 0 ? (
                      <p className="text-xs text-slate-500 text-center py-3">
                        Sin CBUs todavía. Tocá "Agregar CBU" para empezar.
                      </p>
                    ) : formData.cbu_list.map((item, idx) => (
                      <div key={idx} className="flex items-start gap-2" data-testid={`cbu-row-${idx}`}>
                        <span className="text-xs text-slate-500 font-mono w-6 shrink-0 text-right pt-2">{idx + 1}.</span>
                        <Landmark className="w-3.5 h-3.5 text-purple-400 shrink-0 mt-2.5" />
                        <div className="flex-1 grid grid-cols-1 sm:grid-cols-5 gap-2">
                          <input
                            type="text"
                            value={item.cbu || ''}
                            onChange={e => {
                              const v = e.target.value;
                              setFormData(prev => ({
                                ...prev,
                                cbu_list: prev.cbu_list.map((it, i) => i === idx ? { ...it, cbu: v } : it)
                              }));
                            }}
                            placeholder="CBU / Alias / Nº de cuenta"
                            className={`sm:col-span-3 px-3 py-1.5 rounded-md border ${inputBg} text-sm font-mono`}
                            data-testid={`cbu-input-${idx}`}
                          />
                          <input
                            type="text"
                            value={item.name || ''}
                            onChange={e => {
                              const v = e.target.value;
                              setFormData(prev => ({
                                ...prev,
                                cbu_list: prev.cbu_list.map((it, i) => i === idx ? { ...it, name: v } : it)
                              }));
                            }}
                            placeholder="A nombre de..."
                            className={`sm:col-span-2 px-3 py-1.5 rounded-md border ${inputBg} text-sm`}
                            data-testid={`cbu-name-${idx}`}
                          />
                        </div>
                        <button
                          type="button"
                          onClick={() => setFormData(prev => ({
                            ...prev,
                            cbu_list: prev.cbu_list.filter((_, i) => i !== idx)
                          }))}
                          className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded shrink-0 mt-1"
                          data-testid={`cbu-remove-${idx}`}
                          title="Eliminar CBU"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                  <p className={`text-[11px] ${textSecondary} mt-1.5 leading-snug`}>
                    💡 El cajero elige el CBU desde un desplegable (muestra el nombre). Se envían <strong>dos mensajes</strong>: primero el CBU, después el nombre — para que el cliente pueda copiar sin romper el formato.
                  </p>
                </div>
              )}

              {/* Broadcast monthly quota (only for cajero) */}
              {formData.role === 'cajero' && (
                <div className="rounded-lg border border-purple-700/40 bg-purple-900/10 p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <Megaphone className="w-4 h-4 text-purple-400" />
                    <label className={`text-sm font-semibold ${textSecondary}`}>
                      Cupo mensual de mensajes masivos (Broadcasts)
                    </label>
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min={0}
                      step={50}
                      value={formData.broadcast_monthly_quota}
                      onChange={e => setFormData(prev => ({ ...prev, broadcast_monthly_quota: Math.max(0, parseInt(e.target.value || '0', 10) || 0) }))}
                      placeholder="500"
                      className={`w-32 px-3 py-2 rounded-md border ${inputBg} text-sm font-mono`}
                      data-testid="user-broadcast-quota-input"
                    />
                    <span className={`text-xs ${textSecondary}`}>mensajes / mes</span>
                  </div>

                  {editingUser && editingUserQuota && (
                    <div className="mt-3 space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className={textSecondary}>
                          Período <span className="font-mono text-slate-200">{editingUserQuota.period}</span>
                        </span>
                        <span className={textSecondary}>
                          {editingUserQuota.used} / {editingUserQuota.quota} usados
                          {editingUserQuota.extra > 0 && (
                            <span className="ml-1 text-amber-400">(+{editingUserQuota.extra} extras)</span>
                          )}
                        </span>
                      </div>
                      <div className="h-2 rounded-full bg-slate-700/60 overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all"
                          style={{ width: `${editingUserQuota.quota > 0 ? Math.min(100, (editingUserQuota.used / editingUserQuota.quota) * 100) : 0}%` }}
                          data-testid="user-quota-bar"
                        />
                      </div>

                      {/* Admin top-up */}
                      <div className="mt-2 flex items-center gap-2">
                        <Zap className="w-3.5 h-3.5 text-amber-400" />
                        <input
                          type="number"
                          min={1}
                          step={50}
                          placeholder="ej. 100"
                          value={topupAmount}
                          onChange={e => setTopupAmount(e.target.value)}
                          className={`w-24 px-2 py-1 rounded-md border ${inputBg} text-xs font-mono`}
                          data-testid="user-topup-input"
                        />
                        <Button
                          type="button"
                          size="sm"
                          onClick={handleTopup}
                          disabled={topupSaving || !topupAmount}
                          className="bg-amber-600 hover:bg-amber-500 text-white text-xs h-7"
                          data-testid="user-topup-btn"
                        >
                          {topupSaving ? '...' : '+ Recargar este mes'}
                        </Button>
                      </div>
                      <p className="text-[10px] text-slate-500 leading-snug">
                        Las recargas extras solo valen para <strong>{editingUserQuota.period}</strong> y se reinician cuando arranca el siguiente mes (ART).
                      </p>
                    </div>
                  )}

                  <p className={`text-[11px] ${textSecondary} mt-2 leading-snug`}>
                    💡 0 = el cajero no puede crear campañas. Plan típico: 500/1000/2000 según el monto que pague el cliente. El cupo se renueva el día 1 de cada mes (ART).
                  </p>
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

      {/* MODAL: Migrar chats entre líneas */}
      {showMigrateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          onClick={() => !migrating && setShowMigrateModal(false)}
          data-testid="migrate-modal-backdrop">
          <div className={`w-full max-w-md rounded-xl border ${cardBg} shadow-2xl p-5`}
            onClick={e => e.stopPropagation()}
            data-testid="migrate-modal">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-amber-500/15 flex items-center justify-center">
                  <GitMerge className="w-4 h-4 text-amber-400" />
                </div>
                <div>
                  <p className={`text-sm font-semibold ${textPrimary}`}>Migrar chats entre líneas</p>
                  <p className={`text-xs ${textSecondary}`}>Mover leads + mensajes de una línea a otra</p>
                </div>
              </div>
              <Button variant="ghost" size="icon" onClick={() => !migrating && setShowMigrateModal(false)}
                data-testid="migrate-close-btn">
                <X className="w-4 h-4" />
              </Button>
            </div>

            <div className="rounded bg-blue-500/10 border border-blue-500/30 p-2.5 mb-4">
              <p className={`text-[11px] ${textSecondary}`}>
                💡 Si un mismo número existe en ambas líneas, los chats se <strong>fusionan</strong> en el más reciente. La línea origen queda vacía pero <strong>seguirá activa</strong>.
              </p>
            </div>

            <div className="space-y-3">
              <div>
                <label className={`text-xs font-medium ${textSecondary} block mb-1`}>Línea ORIGEN (de dónde salen los chats)</label>
                <select value={migrateSourceId}
                  onChange={e => setMigrateSourceId(e.target.value)}
                  className={`w-full h-9 px-2 rounded border ${inputBg} text-sm`}
                  disabled={migrating}
                  data-testid="migrate-source-select">
                  <option value="">— Elegir línea —</option>
                  {lines.map(l => (
                    <option key={l.id} value={l.id}>{l.name} · {l.whatsapp_number}</option>
                  ))}
                </select>
              </div>

              <div className="flex justify-center">
                <ArrowRight className="w-4 h-4 text-slate-500" />
              </div>

              <div>
                <label className={`text-xs font-medium ${textSecondary} block mb-1`}>Línea DESTINO (a dónde van todos)</label>
                <select value={migrateTargetId}
                  onChange={e => setMigrateTargetId(e.target.value)}
                  className={`w-full h-9 px-2 rounded border ${inputBg} text-sm`}
                  disabled={migrating}
                  data-testid="migrate-target-select">
                  <option value="">— Elegir línea —</option>
                  {lines
                    .filter(l => l.id !== migrateSourceId)
                    .map(l => (
                      <option key={l.id} value={l.id}>{l.name} · {l.whatsapp_number}</option>
                    ))}
                </select>
              </div>
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setShowMigrateModal(false)}
                disabled={migrating}
                data-testid="migrate-cancel-btn">
                Cancelar
              </Button>
              <Button onClick={runMigration}
                disabled={migrating || !migrateSourceId || !migrateTargetId}
                className="bg-amber-600 hover:bg-amber-500 text-white"
                data-testid="migrate-confirm-btn">
                {migrating ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" /> : <GitMerge className="w-4 h-4 mr-1" />}
                Migrar chats
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagement;
