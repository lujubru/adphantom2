import React, { useState, useEffect } from 'react';
import api from '@/utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Plus, Edit, Trash2, Copy, BarChart3, MessageCircle, Eye, Code } from 'lucide-react';
import { toast } from 'sonner';
import { formatNumber } from '@/utils/helpers';

const Campaigns = () => {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingCampaign, setEditingCampaign] = useState(null);
  const [showLanding, setShowLanding] = useState(false);
  const [generatingLanding, setGeneratingLanding] = useState(false);
  const [previewHtml, setPreviewHtml] = useState('');
  const [showPreview, setShowPreview] = useState(false);
  const [showHtmlEditor, setShowHtmlEditor] = useState(false);
  const [formData, setFormData] = useState({
    name: '', target_url: '', safe_page_url: '', is_active: true,
    daily_click_limit: 10000, allowed_countries: '', allowed_devices: '',
    allowed_os: '', block_empty_referrer: false, blacklist_ips: '', whitelist_ips: '',
    landing_html: '', whatsapp_number: '', whatsapp_message: '', meta_verification: ''
  });
  const [waConfig, setWaConfig] = useState({
    title: 'Contactanos', subtitle: 'Haz click para escribirnos por WhatsApp',
    button_text: 'Escribir por WhatsApp', color: '#25D366'
  });

  useEffect(() => { fetchCampaigns(); }, []);

  const fetchCampaigns = async () => {
    try {
      const response = await api.get('/campaigns');
      setCampaigns(response.data);
    } catch (error) {
      toast.error('Error al cargar campanas');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payload = {
      ...formData,
      allowed_countries: formData.allowed_countries ? formData.allowed_countries.split(',').map(s => s.trim()).filter(Boolean) : [],
      allowed_devices: formData.allowed_devices ? formData.allowed_devices.split(',').map(s => s.trim()).filter(Boolean) : [],
      allowed_os: formData.allowed_os ? formData.allowed_os.split(',').map(s => s.trim()).filter(Boolean) : [],
      blacklist_ips: formData.blacklist_ips ? formData.blacklist_ips.split(',').map(s => s.trim()).filter(Boolean) : [],
      whitelist_ips: formData.whitelist_ips ? formData.whitelist_ips.split(',').map(s => s.trim()).filter(Boolean) : [],
    };
    try {
      if (editingCampaign) {
        await api.put(`/campaigns/${editingCampaign.id}`, payload);
        toast.success('Campana actualizada');
      } else {
        await api.post('/campaigns', payload);
        toast.success('Campana creada');
      }
      setDialogOpen(false);
      resetForm();
      fetchCampaigns();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error en la operacion');
    }
  };

  const handleEdit = (campaign) => {
    setEditingCampaign(campaign);
    setFormData({
      name: campaign.name, target_url: campaign.target_url,
      safe_page_url: campaign.safe_page_url || '',
      is_active: campaign.is_active, daily_click_limit: campaign.daily_click_limit,
      allowed_countries: campaign.allowed_countries?.join(', ') || '',
      allowed_devices: campaign.allowed_devices?.join(', ') || '',
      allowed_os: campaign.allowed_os?.join(', ') || '',
      block_empty_referrer: campaign.block_empty_referrer,
      blacklist_ips: campaign.blacklist_ips?.join(', ') || '',
      whitelist_ips: campaign.whitelist_ips?.join(', ') || '',
      landing_html: campaign.landing_html || '',
      whatsapp_number: campaign.whatsapp_number || '',
      whatsapp_message: campaign.whatsapp_message || '',
      meta_verification: campaign.meta_verification || '',
    });
    setShowLanding(!!campaign.landing_html);
    setDialogOpen(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Estas seguro de eliminar esta campana?')) return;
    try {
      await api.delete(`/campaigns/${id}`);
      toast.success('Campana eliminada');
      fetchCampaigns();
    } catch (error) {
      toast.error('Error al eliminar campana');
    }
  };

  const copyTrackingUrl = (shortCode, type = 'meta') => {
    const url = type === 'meta'
      ? `${process.env.REACT_APP_BACKEND_URL}?c=${shortCode}`
      : `${process.env.REACT_APP_BACKEND_URL}/go/${shortCode}`;
    navigator.clipboard.writeText(url);
    toast.success(type === 'meta' ? 'URL Meta copiada' : 'URL corta copiada');
  };

  const generateWALanding = async () => {
    if (!formData.whatsapp_number) {
      toast.error('Ingresa un numero de WhatsApp primero');
      return;
    }
    setGeneratingLanding(true);
    try {
      const response = await api.post('/campaigns/generate-wa-landing', {
        whatsapp_number: formData.whatsapp_number,
        whatsapp_message: formData.whatsapp_message,
        ...waConfig
      });
      setFormData({ ...formData, landing_html: response.data.html });
      toast.success('Landing page de WhatsApp generada');
    } catch (error) {
      toast.error('Error al generar landing page');
    } finally {
      setGeneratingLanding(false);
    }
  };

  const resetForm = () => {
    setFormData({
      name: '', target_url: '', safe_page_url: '', is_active: true,
      daily_click_limit: 10000, allowed_countries: '', allowed_devices: '',
      allowed_os: '', block_empty_referrer: false, blacklist_ips: '', whitelist_ips: '',
      landing_html: '', whatsapp_number: '', whatsapp_message: '', meta_verification: ''
    });
    setEditingCampaign(null);
    setShowLanding(false);
    setShowHtmlEditor(false);
  };

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen bg-slate-950"><div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div></div>;
  }

  return (
    <div data-testid="campaigns-container" className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Campanas</h1>
            <p className="text-slate-400">Gestiona tus campanas de trafico</p>
          </div>
          <Dialog open={dialogOpen} onOpenChange={(open) => { setDialogOpen(open); if (!open) resetForm(); }}>
            <DialogTrigger asChild>
              <Button data-testid="create-campaign-button" className="bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white">
                <Plus className="w-4 h-4 mr-2" />
                Nueva Campana
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-slate-900 border-slate-800 text-white max-w-2xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle className="text-xl">{editingCampaign ? 'Editar Campana' : 'Crear Campana'}</DialogTitle>
              </DialogHeader>
              <form onSubmit={handleSubmit} className="space-y-4 mt-4">
                <div>
                  <Label className="text-slate-300">Nombre de la Campana</Label>
                  <Input data-testid="campaign-name-input" value={formData.name} onChange={(e) => setFormData({...formData, name: e.target.value})} required className="bg-slate-800 border-slate-700 text-white" />
                </div>
                <div>
                  <Label className="text-slate-300">URL de Destino (si no usas landing page)</Label>
                  <Input data-testid="campaign-target-url-input" value={formData.target_url} onChange={(e) => setFormData({...formData, target_url: e.target.value})} required className="bg-slate-800 border-slate-700 text-white" placeholder="https://ejemplo.com/landing" />
                </div>
                <div>
                  <Label className="text-slate-300">URL de Pagina Segura (para trafico bloqueado)</Label>
                  <Input value={formData.safe_page_url} onChange={(e) => setFormData({...formData, safe_page_url: e.target.value})} className="bg-slate-800 border-slate-700 text-white" placeholder="https://ejemplo.com/segura" />
                </div>
                <div>
                  <Label className="text-slate-300">Limite de Clicks Diarios</Label>
                  <Input type="number" value={formData.daily_click_limit} onChange={(e) => setFormData({...formData, daily_click_limit: parseInt(e.target.value)})} className="bg-slate-800 border-slate-700 text-white" />
                </div>
                <div className="flex items-center space-x-2">
                  <Switch checked={formData.is_active} onCheckedChange={(checked) => setFormData({...formData, is_active: checked})} />
                  <Label className="text-slate-300">Campana Activa</Label>
                </div>

                {/* Meta Verification */}
                <div>
                  <Label className="text-slate-300">Meta Verification Code (opcional)</Label>
                  <Input value={formData.meta_verification} onChange={(e) => setFormData({...formData, meta_verification: e.target.value})} className="bg-slate-800 border-slate-700 text-white" placeholder="Codigo de verificacion de Meta" data-testid="meta-verification-input" />
                  <p className="text-xs text-slate-500 mt-1">Solo el valor content= de la meta etiqueta que te da Meta</p>
                </div>

                {/* Landing Page Section */}
                <div className="border border-green-500/30 rounded-lg p-4 bg-green-900/10">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <MessageCircle className="w-5 h-5 text-green-400" />
                      <Label className="text-green-400 font-semibold text-base">Landing Page WhatsApp</Label>
                    </div>
                    <Switch checked={showLanding} onCheckedChange={setShowLanding} data-testid="toggle-landing" />
                  </div>
                  <p className="text-xs text-slate-400 mb-3">Sirve una landing page con boton de WhatsApp directamente. Meta ve contenido real y aprueba el anuncio.</p>

                  {showLanding && (
                    <div className="space-y-3">
                      <div>
                        <Label className="text-slate-300">Numero de WhatsApp (con codigo de pais)</Label>
                        <Input value={formData.whatsapp_number} onChange={(e) => setFormData({...formData, whatsapp_number: e.target.value})} className="bg-slate-800 border-slate-700 text-white" placeholder="5491112345678" data-testid="whatsapp-number-input" />
                      </div>
                      <div>
                        <Label className="text-slate-300">Mensaje predefinido (opcional)</Label>
                        <Input value={formData.whatsapp_message} onChange={(e) => setFormData({...formData, whatsapp_message: e.target.value})} className="bg-slate-800 border-slate-700 text-white" placeholder="Hola, quiero mas informacion..." data-testid="whatsapp-message-input" />
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <Label className="text-slate-300 text-xs">Titulo</Label>
                          <Input value={waConfig.title} onChange={(e) => setWaConfig({...waConfig, title: e.target.value})} className="bg-slate-800 border-slate-700 text-white text-sm" />
                        </div>
                        <div>
                          <Label className="text-slate-300 text-xs">Texto del boton</Label>
                          <Input value={waConfig.button_text} onChange={(e) => setWaConfig({...waConfig, button_text: e.target.value})} className="bg-slate-800 border-slate-700 text-white text-sm" />
                        </div>
                      </div>
                      <div>
                        <Label className="text-slate-300 text-xs">Subtitulo</Label>
                        <Input value={waConfig.subtitle} onChange={(e) => setWaConfig({...waConfig, subtitle: e.target.value})} className="bg-slate-800 border-slate-700 text-white text-sm" />
                      </div>

                      <div className="flex gap-2">
                        <Button type="button" onClick={generateWALanding} disabled={generatingLanding} className="flex-1 bg-green-600 hover:bg-green-700 text-white" data-testid="generate-wa-landing-btn">
                          <MessageCircle className="w-4 h-4 mr-2" />
                          {generatingLanding ? 'Generando...' : 'Generar Landing WhatsApp'}
                        </Button>
                      </div>

                      {formData.landing_html && (
                        <div className="space-y-2">
                          <div className="flex gap-2">
                            <Button type="button" variant="outline" size="sm" onClick={() => { setPreviewHtml(formData.landing_html); setShowPreview(true); }} className="border-slate-700 text-slate-300 hover:bg-slate-800" data-testid="preview-landing-btn">
                              <Eye className="w-3 h-3 mr-1" /> Vista previa
                            </Button>
                            <Button type="button" variant="outline" size="sm" onClick={() => setShowHtmlEditor(!showHtmlEditor)} className="border-slate-700 text-slate-300 hover:bg-slate-800" data-testid="edit-html-btn">
                              <Code className="w-3 h-3 mr-1" /> {showHtmlEditor ? 'Ocultar HTML' : 'Editar HTML'}
                            </Button>
                          </div>
                          {showHtmlEditor && (
                            <textarea value={formData.landing_html} onChange={(e) => setFormData({...formData, landing_html: e.target.value})} className="w-full h-48 bg-slate-950 border border-slate-700 rounded-lg p-3 text-xs text-green-400 font-mono resize-y" data-testid="landing-html-editor" />
                          )}
                          <p className="text-xs text-green-400">Landing page configurada. Se servira directamente en la URL de tracking.</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Filters */}
                <details className="border border-slate-700 rounded-lg">
                  <summary className="p-3 text-slate-400 text-sm cursor-pointer hover:text-white">Filtros avanzados</summary>
                  <div className="p-3 space-y-3 border-t border-slate-700">
                    <div>
                      <Label className="text-slate-300">Paises Permitidos (separados por coma)</Label>
                      <Input value={formData.allowed_countries} onChange={(e) => setFormData({...formData, allowed_countries: e.target.value})} className="bg-slate-800 border-slate-700 text-white" placeholder="US, GB, CA" />
                    </div>
                    <div>
                      <Label className="text-slate-300">Dispositivos Permitidos</Label>
                      <Input value={formData.allowed_devices} onChange={(e) => setFormData({...formData, allowed_devices: e.target.value})} className="bg-slate-800 border-slate-700 text-white" placeholder="Desktop, Mobile" />
                    </div>
                    <div>
                      <Label className="text-slate-300">SO Permitidos</Label>
                      <Input value={formData.allowed_os} onChange={(e) => setFormData({...formData, allowed_os: e.target.value})} className="bg-slate-800 border-slate-700 text-white" placeholder="Windows, macOS, iOS" />
                    </div>
                    <div className="flex items-center space-x-2">
                      <Switch checked={formData.block_empty_referrer} onCheckedChange={(checked) => setFormData({...formData, block_empty_referrer: checked})} />
                      <Label className="text-slate-300">Bloquear Referrer Vacio</Label>
                    </div>
                    <div>
                      <Label className="text-slate-300">IPs en Lista Negra</Label>
                      <Input value={formData.blacklist_ips} onChange={(e) => setFormData({...formData, blacklist_ips: e.target.value})} className="bg-slate-800 border-slate-700 text-white" placeholder="1.2.3.4, 5.6.7.8" />
                    </div>
                    <div>
                      <Label className="text-slate-300">IPs en Lista Blanca</Label>
                      <Input value={formData.whitelist_ips} onChange={(e) => setFormData({...formData, whitelist_ips: e.target.value})} className="bg-slate-800 border-slate-700 text-white" placeholder="9.10.11.12" />
                    </div>
                  </div>
                </details>

                <Button data-testid="campaign-submit-button" type="submit" className="w-full bg-blue-600 hover:bg-blue-700">{editingCampaign ? 'Actualizar' : 'Crear'}</Button>
              </form>
            </DialogContent>
          </Dialog>
        </div>

        <div className="grid grid-cols-1 gap-4">
          {campaigns.map((campaign) => (
            <Card key={campaign.id} data-testid={`campaign-card-${campaign.id}`} className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="text-xl font-semibold text-white">{campaign.name}</h3>
                    {campaign.is_active ? (
                      <span className="px-2 py-1 bg-green-500/10 text-green-400 text-xs font-medium rounded-full border border-green-500/20">Activa</span>
                    ) : (
                      <span className="px-2 py-1 bg-red-500/10 text-red-400 text-xs font-medium rounded-full border border-red-500/20">Inactiva</span>
                    )}
                    {campaign.landing_html && (
                      <span className="px-2 py-1 bg-green-500/10 text-green-400 text-xs font-medium rounded-full border border-green-500/20 flex items-center gap-1">
                        <MessageCircle className="w-3 h-3" /> Landing WA
                      </span>
                    )}
                  </div>
                  <p className="text-slate-400 text-sm mb-2">{campaign.target_url}</p>
                  {campaign.short_code && (
                    <div className="flex flex-col gap-1 mb-4">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-green-400 font-semibold">Meta:</span>
                        <code className="text-xs text-green-300 bg-green-900/30 px-2 py-1 rounded font-mono border border-green-500/20" data-testid={`meta-url-${campaign.id}`}>{process.env.REACT_APP_BACKEND_URL}?c={campaign.short_code}</code>
                        <Button size="icon" variant="ghost" className="h-6 w-6 hover:bg-green-900/30 text-green-400 hover:text-green-300" onClick={() => copyTrackingUrl(campaign.short_code, 'meta')} data-testid={`copy-meta-url-${campaign.id}`}>
                          <Copy className="w-3 h-3" />
                        </Button>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-500">Directa:</span>
                        <code className="text-xs text-cyan-400 bg-slate-800 px-2 py-1 rounded font-mono" data-testid={`direct-url-${campaign.id}`}>{process.env.REACT_APP_BACKEND_URL}/go/{campaign.short_code}</code>
                        <Button size="icon" variant="ghost" className="h-6 w-6 hover:bg-slate-800 text-slate-400 hover:text-white" onClick={() => copyTrackingUrl(campaign.short_code, 'direct')} data-testid={`copy-direct-url-${campaign.id}`}>
                          <Copy className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>
                  )}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div><p className="text-slate-500 text-xs mb-1">Total Clicks</p><p className="text-white font-semibold">{formatNumber(campaign.total_clicks)}</p></div>
                    <div><p className="text-slate-500 text-xs mb-1">Hoy</p><p className="text-white font-semibold">{formatNumber(campaign.clicks_today)} / {formatNumber(campaign.daily_click_limit)}</p></div>
                    <div><p className="text-slate-500 text-xs mb-1">Paises</p><p className="text-white font-semibold">{campaign.allowed_countries?.length || 'Todos'}</p></div>
                    <div><p className="text-slate-500 text-xs mb-1">Dispositivos</p><p className="text-white font-semibold">{campaign.allowed_devices?.length || 'Todos'}</p></div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button size="icon" variant="ghost" onClick={() => handleEdit(campaign)} className="hover:bg-slate-800 text-slate-400 hover:text-white" data-testid={`edit-campaign-${campaign.id}`}>
                    <Edit className="w-4 h-4" />
                  </Button>
                  <Button size="icon" variant="ghost" onClick={() => handleDelete(campaign.id)} className="hover:bg-slate-800 text-red-400 hover:text-red-300" data-testid={`delete-campaign-${campaign.id}`}>
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>

        {campaigns.length === 0 && (
          <div className="text-center py-12">
            <BarChart3 className="w-16 h-16 text-slate-700 mx-auto mb-4" />
            <p className="text-slate-400">No hay campanas aun. Crea tu primera!</p>
          </div>
        )}
      </div>

      {/* Landing Page Preview Modal */}
      {showPreview && (
        <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4" onClick={() => setShowPreview(false)}>
          <div className="bg-white rounded-xl w-full max-w-lg h-[80vh] overflow-hidden relative" onClick={e => e.stopPropagation()}>
            <Button variant="ghost" size="sm" className="absolute top-2 right-2 z-10 bg-black/50 text-white hover:bg-black/70" onClick={() => setShowPreview(false)}>X</Button>
            <iframe srcDoc={previewHtml} className="w-full h-full border-0" title="Preview Landing" sandbox="allow-scripts allow-same-origin" />
          </div>
        </div>
      )}
    </div>
  );
};

export default Campaigns;
