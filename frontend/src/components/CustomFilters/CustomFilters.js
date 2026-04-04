import React, { useState, useEffect } from 'react';
import api from '@/utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Filter, Plus, Edit, Trash2, ArrowUp, ArrowDown } from 'lucide-react';
import { toast } from 'sonner';

const CustomFilters = () => {
  const [filters, setFilters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingFilter, setEditingFilter] = useState(null);
  const [formData, setFormData] = useState({
    name: '', description: '', action: 'block', priority: 0, is_active: true, conditions: {}
  });

  useEffect(() => { fetchFilters(); }, []);

  const fetchFilters = async () => {
    try {
      const response = await api.get('/filters');
      setFilters(response.data);
    } catch (error) {
      toast.error('Error al cargar filtros');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingFilter) {
        await api.put(`/filters/${editingFilter.id}`, formData);
        toast.success('Filtro actualizado');
      } else {
        await api.post('/filters/', formData);
        toast.success('Filtro creado');
      }
      setDialogOpen(false);
      resetForm();
      fetchFilters();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error en la operación');
    }
  };

  const handleEdit = (filter) => {
    setEditingFilter(filter);
    setFormData({
      name: filter.name, description: filter.description || '',
      action: filter.action, priority: filter.priority,
      is_active: filter.is_active, conditions: filter.conditions
    });
    setDialogOpen(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('¿Eliminar este filtro?')) return;
    try {
      await api.delete(`/filters/${id}`);
      toast.success('Filtro eliminado');
      fetchFilters();
    } catch (error) {
      toast.error('Error al eliminar filtro');
    }
  };

  const resetForm = () => {
    setFormData({ name: '', description: '', action: 'block', priority: 0, is_active: true, conditions: {} });
    setEditingFilter(null);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-950">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div data-testid="filters-container" className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Filtros Personalizados</h1>
            <p className="text-slate-400">Crea reglas avanzadas de filtrado de tráfico</p>
          </div>
          <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) resetForm(); }}>
            <DialogTrigger asChild>
              <Button data-testid="create-filter-button" className="bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white">
                <Plus className="w-4 h-4 mr-2" />
                Nuevo Filtro
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-slate-900 border-slate-800 text-white max-w-2xl">
              <DialogHeader>
                <DialogTitle className="text-xl">{editingFilter ? 'Editar Filtro' : 'Crear Filtro'}</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4 mt-4">
                <div>
                  <Label className="text-slate-300">Nombre del Filtro</Label>
                  <Input data-testid="filter-name-input" value={formData.name} onChange={(e) => setFormData({...formData, name: e.target.value})} required className="bg-slate-800 border-slate-700 text-white" placeholder="Ej: Bloquear VPNs" />
                </div>
                <div>
                  <Label className="text-slate-300">Descripción</Label>
                  <Textarea value={formData.description} onChange={(e) => setFormData({...formData, description: e.target.value})} className="bg-slate-800 border-slate-700 text-white" placeholder="Describe qué hace este filtro" rows={3} />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label className="text-slate-300">Acción</Label>
                    <select value={formData.action} onChange={(e) => setFormData({...formData, action: e.target.value})} className="w-full bg-slate-800 border border-slate-700 text-white rounded-md px-3 py-2">
                      <option value="block">Bloquear</option>
                      <option value="allow">Permitir</option>
                    </select>
                  </div>
                  <div>
                    <Label className="text-slate-300">Prioridad</Label>
                    <Input type="number" value={formData.priority} onChange={(e) => setFormData({...formData, priority: parseInt(e.target.value)})} className="bg-slate-800 border-slate-700 text-white" min="0" max="100" />
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <Switch checked={formData.is_active} onCheckedChange={(checked) => setFormData({...formData, is_active: checked})} />
                  <Label className="text-slate-300">Filtro Activo</Label>
                </div>
                <Button data-testid="filter-submit-button" type="submit" className="w-full bg-blue-600 hover:bg-blue-700">
                  {editingFilter ? 'Actualizar' : 'Crear'} Filtro
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        {filters.length === 0 ? (
          <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-12 text-center">
            <Filter className="w-16 h-16 text-slate-700 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-white mb-2">No hay filtros personalizados</h3>
            <p className="text-slate-400 mb-6">Crea tu primer filtro para tener control avanzado sobre tu tráfico</p>
            <Button onClick={() => setDialogOpen(true)} className="bg-blue-600 hover:bg-blue-700">
              <Plus className="w-4 h-4 mr-2" />Crear Primer Filtro
            </Button>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {filters.map((filter) => (
              <Card key={filter.id} data-testid={`filter-card-${filter.id}`} className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-xl font-semibold text-white">{filter.name}</h3>
                      {filter.is_active ? (
                        <span className="px-2 py-1 bg-green-500/10 text-green-400 text-xs font-medium rounded-full border border-green-500/20">Activo</span>
                      ) : (
                        <span className="px-2 py-1 bg-gray-500/10 text-gray-400 text-xs font-medium rounded-full border border-gray-500/20">Inactivo</span>
                      )}
                      <span className={`px-2 py-1 text-xs font-medium rounded-full border ${filter.action === 'block' ? 'bg-red-500/10 text-red-400 border-red-500/20' : 'bg-blue-500/10 text-blue-400 border-blue-500/20'}`}>
                        {filter.action === 'block' ? 'Bloquear' : 'Permitir'}
                      </span>
                    </div>
                    {filter.description && <p className="text-slate-400 text-sm mb-4">{filter.description}</p>}
                    <div className="grid grid-cols-3 gap-4 mt-4">
                      <div>
                        <p className="text-slate-500 text-xs mb-1">Prioridad</p>
                        <p className="text-white font-semibold flex items-center">
                          {filter.priority > 50 && <ArrowUp className="w-4 h-4 text-green-400 mr-1" />}
                          {filter.priority <= 50 && filter.priority > 0 && <ArrowDown className="w-4 h-4 text-yellow-400 mr-1" />}
                          {filter.priority}
                        </p>
                      </div>
                      <div>
                        <p className="text-slate-500 text-xs mb-1">Veces Activado</p>
                        <p className="text-white font-semibold">{filter.times_triggered || 0}</p>
                      </div>
                      <div>
                        <p className="text-slate-500 text-xs mb-1">Creado</p>
                        <p className="text-white font-semibold text-sm">{new Date(filter.created_at).toLocaleDateString('es-ES')}</p>
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2 ml-4">
                    <Button size="icon" variant="ghost" onClick={() => handleEdit(filter)} className="hover:bg-slate-800 text-slate-400 hover:text-white">
                      <Edit className="w-4 h-4" />
                    </Button>
                    <Button size="icon" variant="ghost" onClick={() => handleDelete(filter.id)} className="hover:bg-slate-800 text-red-400 hover:text-red-300">
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}

        <Card className="bg-slate-900/30 border-slate-800 p-6">
          <h4 className="text-white font-semibold mb-3">Guía de Filtros Personalizados</h4>
          <div className="space-y-2 text-sm text-slate-400">
            <p><strong className="text-white">Prioridad:</strong> Los filtros con mayor prioridad (100) se ejecutan primero</p>
            <p><strong className="text-white">Acción Bloquear:</strong> El tráfico que coincida será bloqueado y redirigido a safe page</p>
            <p><strong className="text-white">Acción Permitir:</strong> El tráfico que coincida será permitido siempre</p>
            <p><strong className="text-white">Casos de uso:</strong> Bloquear VPNs, permitir solo ciertos países, bloquear IPs específicas</p>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default CustomFilters;
