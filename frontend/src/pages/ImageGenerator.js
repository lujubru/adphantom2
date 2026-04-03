import React, { useState } from 'react';
import api from '@/utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card } from '@/components/ui/card';
import { Image, Loader2, Download, Copy, Sparkles } from 'lucide-react';
import { toast } from 'sonner';

const PRESETS = [
  { label: 'Anuncio de producto', prompt: 'Professional product advertisement photo, clean white background, commercial style' },
  { label: 'Landing hero', prompt: 'Modern website hero image, abstract gradient, professional business style' },
  { label: 'Redes sociales', prompt: 'Eye-catching social media post image, vibrant colors, modern design' },
  { label: 'WhatsApp banner', prompt: 'WhatsApp business promotional banner, professional and friendly' },
];

const ImageGenerator = () => {
  const [prompt, setPrompt] = useState('');
  const [generating, setGenerating] = useState(false);
  const [images, setImages] = useState([]);

  const generate = async () => {
    if (!prompt.trim()) return toast.error('Ingresa una descripcion');
    setGenerating(true);
    try {
      const resp = await api.post('/images/generate', { prompt, style: 'vivid', size: '1024x1024' }, { timeout: 120000 });
      setImages(prev => [{ base64: resp.data.image_base64, prompt, time: new Date().toLocaleTimeString() }, ...prev]);
      toast.success('Imagen generada');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error generando imagen');
    } finally { setGenerating(false); }
  };

  const downloadImage = (base64, index) => {
    const link = document.createElement('a');
    link.href = `data:image/png;base64,${base64}`;
    link.download = `image-${index}.png`;
    link.click();
  };

  const copyBase64 = (base64) => {
    navigator.clipboard.writeText(base64);
    toast.success('Base64 copiado');
  };

  return (
    <div data-testid="image-generator-container" className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Generador de Imagenes IA</h1>
          <p className="text-slate-400">Genera imagenes con OpenAI para tus anuncios y landing pages</p>
        </div>

        <Card className="bg-slate-900/50 border-slate-800 p-6 space-y-4">
          <div>
            <Label className="text-slate-300">Descripcion de la imagen</Label>
            <textarea value={prompt} onChange={e => setPrompt(e.target.value)} className="w-full bg-slate-800 border border-slate-700 text-white rounded-md p-3 h-24 resize-y mt-1" placeholder="Describe la imagen que quieres generar..." data-testid="image-prompt-input" />
          </div>

          <div className="flex flex-wrap gap-2">
            {PRESETS.map((p, i) => (
              <button key={i} onClick={() => setPrompt(p.prompt)} className="px-3 py-1.5 rounded-full text-xs bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white transition-all" data-testid={`preset-${i}`}>
                {p.label}
              </button>
            ))}
          </div>

          <Button onClick={generate} disabled={generating} className="w-full bg-gradient-to-r from-purple-500 to-cyan-500 hover:from-purple-600 hover:to-cyan-600 text-white" data-testid="generate-image-submit">
            {generating ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Generando...</> : <><Sparkles className="w-4 h-4 mr-2" /> Generar Imagen</>}
          </Button>
        </Card>

        {images.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {images.map((img, i) => (
              <Card key={i} className="bg-slate-900/50 border-slate-800 overflow-hidden" data-testid={`generated-image-${i}`}>
                <img src={`data:image/png;base64,${img.base64}`} alt={img.prompt} className="w-full aspect-square object-contain bg-slate-950" />
                <div className="p-4 space-y-2">
                  <p className="text-slate-400 text-xs truncate">{img.prompt}</p>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => downloadImage(img.base64, i)} className="border-slate-700 text-slate-300 hover:bg-slate-800 flex-1" data-testid={`download-image-${i}`}>
                      <Download className="w-3 h-3 mr-1" /> Descargar
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => copyBase64(img.base64)} className="border-slate-700 text-slate-300 hover:bg-slate-800" data-testid={`copy-image-${i}`}>
                      <Copy className="w-3 h-3" />
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}

        {images.length === 0 && !generating && (
          <div className="text-center py-12">
            <Image className="w-16 h-16 text-slate-700 mx-auto mb-4" />
            <p className="text-slate-500">Las imagenes generadas apareceran aqui</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ImageGenerator;
