import React, { useState, useEffect } from 'react';
import api from '@/utils/api';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Card } from '@/components/ui/card';
import { Wand2, Eye, Trash2, Copy, Link, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const AIGenerator = () => {
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [generatedPage, setGeneratedPage] = useState(null);
  const [savedPages, setSavedPages] = useState([]);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [campaigns, setCampaigns] = useState([]);
  const [selectedCampaign, setSelectedCampaign] = useState('none');

  const backendUrl = process.env.REACT_APP_BACKEND_URL || '';

  useEffect(() => { 
    fetchPages(); 
    fetchCampaigns();
  }, []);

  const fetchCampaigns = async () => {
    try {
      const res = await api.get('/campaigns');
      setCampaigns(res.data);
    } catch (e) { /* silent */ }
  };

  const fetchPages = async () => {
    try {
      const res = await api.get('/ai/pages');
      setSavedPages(res.data);
    } catch (e) { /* silent */ }
  };

  const getPublicUrl = (pageId) => {
    return `${backendUrl}/api/p/${pageId}`;
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Link copiado al portapapeles');
  };

  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!prompt.trim()) { toast.error('Ingresa una descripción'); return; }
    setLoading(true);
    try {
      const payload = { 
        prompt,
        campaign_id: selectedCampaign !== 'none' ? selectedCampaign : null
      };
      const response = await api.post('/ai/generate', payload);
      setGeneratedPage(response.data);
      toast.success('Página generada exitosamente');
      setPrompt('');
      fetchPages();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al generar página');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (pageId) => {
    if (!window.confirm('¿Eliminar esta página?')) return;
    try {
      await api.delete(`/ai/pages/${pageId}`);
      toast.success('Página eliminada');
      fetchPages();
      if (generatedPage?.id === pageId) setGeneratedPage(null);
    } catch (e) {
      toast.error('Error al eliminar');
    }
  };

  return (
    <div data-testid="ai-generator-container" className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Generador de Páginas IA</h1>
          <p className="text-slate-400">Genera landing pages con inteligencia artificial</p>
        </div>

        <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
          <form onSubmit={handleGenerate} className="space-y-4">
            <div>
              <Label className="text-slate-300 mb-2 block">Describe la landing page que deseas</Label>
              <Textarea
                data-testid="ai-prompt-textarea"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Crea una landing page moderna para un producto SaaS que ayuda a las empresas a gestionar sus redes sociales. Incluye hero, características, precios y botones CTA. Usa colores azul y blanco."
                className="bg-slate-800/50 border-slate-700 text-white placeholder:text-slate-500 min-h-[150px]"
                rows={6}
              />
            </div>
            
            <div>
              <Label className="text-slate-300 mb-2 block">Asociar a Campaña (para reglas antibot)</Label>
              <Select value={selectedCampaign} onValueChange={setSelectedCampaign}>
                <SelectTrigger className="bg-slate-800/50 border-slate-700 text-white">
                  <SelectValue placeholder="Seleccionar campaña" />
                </SelectTrigger>
                <SelectContent className="bg-slate-800 border-slate-700">
                  <SelectItem value="none" className="text-slate-300">Sin campaña (solo detección básica de bots)</SelectItem>
                  {campaigns.map((camp) => (
                    <SelectItem key={camp.id} value={camp.id} className="text-slate-300">
                      {camp.name} {camp.is_active ? '✓' : '(inactiva)'}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-slate-500 text-xs mt-1">
                Al asociar una campaña, se aplicarán sus reglas de filtrado (países, dispositivos, IPs, etc.)
              </p>
            </div>
            
            <Button
              type="submit"
              data-testid="generate-ai-page-button"
              disabled={loading}
              className="w-full bg-gradient-to-r from-purple-500 to-pink-600 hover:from-purple-600 hover:to-pink-700 text-white font-medium py-3"
            >
              {loading ? (
                <><div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-white mr-2"></div>Generando...</>
              ) : (
                <><Wand2 className="w-4 h-4 mr-2" />Generar Página</>
              )}
            </Button>
          </form>
        </Card>

        {generatedPage && (
          <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-lg font-semibold text-white mb-1">Página Generada</h3>
                <p className="text-slate-400 text-sm">{generatedPage.title}</p>
              </div>
              <Button onClick={() => setPreviewOpen(true)} data-testid="preview-page-button" className="bg-blue-600 hover:bg-blue-700">
                <Eye className="w-4 h-4 mr-2" />Vista Previa
              </Button>
            </div>
            
            {/* Public URL with antibot tracking */}
            <div className="bg-green-900/30 border border-green-700/50 rounded-lg p-4 mb-4">
              <div className="flex items-center gap-2 mb-2">
                <Link className="w-4 h-4 text-green-400" />
                <span className="text-green-400 font-medium text-sm">Link Público con Tracking Antibot</span>
              </div>
              <div className="flex items-center gap-2">
                <input 
                  type="text" 
                  readOnly 
                  value={getPublicUrl(generatedPage.id)}
                  className="flex-1 bg-slate-800/50 border border-slate-700 rounded px-3 py-2 text-white text-sm"
                />
                <Button 
                  size="sm" 
                  onClick={() => copyToClipboard(getPublicUrl(generatedPage.id))}
                  className="bg-green-600 hover:bg-green-700"
                >
                  <Copy className="w-4 h-4" />
                </Button>
                <Button 
                  size="sm" 
                  onClick={() => window.open(getPublicUrl(generatedPage.id), '_blank')}
                  className="bg-slate-600 hover:bg-slate-700"
                >
                  <ExternalLink className="w-4 h-4" />
                </Button>
              </div>
              <p className="text-green-300/70 text-xs mt-2">
                ✓ Usa este link en tus campañas de Meta. Los bots verán una página 404, los usuarios reales verán tu landing.
              </p>
            </div>
            
            <div className="bg-slate-800/50 rounded-lg p-4 border border-slate-700">
              <pre className="text-slate-300 text-xs overflow-x-auto max-h-64"><code>{generatedPage.generated_html}</code></pre>
            </div>
          </Card>
        )}

        {savedPages.length > 0 && (
          <Card className="bg-slate-900/50 backdrop-blur-xl border-slate-800 p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Páginas Guardadas</h3>
            <div className="space-y-3">
              {savedPages.map((page) => (
                <div key={page.id} className="p-4 bg-slate-800/30 rounded-lg border border-slate-700/50">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex-1">
                      <p className="text-white text-sm font-medium">{page.title}</p>
                      <p className="text-slate-500 text-xs">
                        {new Date(page.created_at).toLocaleDateString('es-ES')}
                        {page.campaign_id && ' • Asociada a campaña'}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="ghost" onClick={() => { setGeneratedPage(page); setPreviewOpen(true); }} className="text-blue-400 hover:text-blue-300">
                        <Eye className="w-4 h-4" />
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => handleDelete(page.id)} className="text-red-400 hover:text-red-300">
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                  {/* Public URL */}
                  <div className="flex items-center gap-2 mt-2 pt-2 border-t border-slate-700/50">
                    <input 
                      type="text" 
                      readOnly 
                      value={getPublicUrl(page.id)}
                      className="flex-1 bg-slate-900/50 border border-slate-700 rounded px-2 py-1 text-slate-300 text-xs"
                    />
                    <Button 
                      size="sm" 
                      variant="ghost"
                      onClick={() => copyToClipboard(getPublicUrl(page.id))}
                      className="text-green-400 hover:text-green-300 h-7 w-7 p-0"
                    >
                      <Copy className="w-3 h-3" />
                    </Button>
                    <Button 
                      size="sm" 
                      variant="ghost"
                      onClick={() => window.open(getPublicUrl(page.id), '_blank')}
                      className="text-slate-400 hover:text-slate-300 h-7 w-7 p-0"
                    >
                      <ExternalLink className="w-3 h-3" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
          <DialogContent className="max-w-6xl max-h-[90vh] bg-white p-0 overflow-hidden">
            <div className="h-[85vh] overflow-auto">
              {generatedPage && (
                <iframe srcDoc={generatedPage.generated_html} title="Vista Previa" className="w-full h-full border-0" sandbox="allow-same-origin" />
              )}
            </div>
          </DialogContent>
        </Dialog>

        <div className="bg-slate-900/30 border border-slate-800 rounded-lg p-4">
          <h4 className="text-white font-medium mb-2">Consejos para mejores resultados:</h4>
          <ul className="text-slate-400 text-sm space-y-1 list-disc list-inside">
            <li>Sé específico sobre el propósito y público objetivo</li>
            <li>Menciona las secciones deseadas (hero, características, precios, testimonios)</li>
            <li>Especifica esquema de colores y preferencias de estilo</li>
            <li>Incluye contenido o mensajes específicos que desees</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default AIGenerator;
