import React, { useState, useCallback } from 'react';
import api from '@/utils/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Zap, Link2, Image, Target, DollarSign, Send, Check, Loader2, AlertCircle, ArrowLeft, ArrowRight, Sparkles, Copy } from 'lucide-react';
import { toast } from 'sonner';

const OBJECTIVES = [
  { value: 'OUTCOME_TRAFFIC', label: 'Trafico', desc: 'Enviar personas a un destino' },
  { value: 'OUTCOME_ENGAGEMENT', label: 'Interaccion', desc: 'Mas interacciones con tu contenido' },
  { value: 'OUTCOME_LEADS', label: 'Clientes potenciales', desc: 'Captar datos de personas interesadas' },
  { value: 'OUTCOME_SALES', label: 'Ventas', desc: 'Personas que compren tu producto' },
  { value: 'OUTCOME_AWARENESS', label: 'Reconocimiento', desc: 'Aumentar visibilidad de marca' },
];

const CTAS = [
  { value: 'LEARN_MORE', label: 'Mas informacion' },
  { value: 'SHOP_NOW', label: 'Comprar ahora' },
  { value: 'SIGN_UP', label: 'Registrarse' },
  { value: 'CONTACT_US', label: 'Contactar' },
  { value: 'GET_OFFER', label: 'Obtener oferta' },
  { value: 'SEND_WHATSAPP_MESSAGE', label: 'WhatsApp' },
];

const AdManage = () => {
  const [step, setStep] = useState(0); // 0=connect, 1=objective, 2=creative, 3=audience, 4=budget, 5=publish
  const [connecting, setConnecting] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [genImage, setGenImage] = useState(false);
  const [publishLog, setPublishLog] = useState([]);
  const [accountInfo, setAccountInfo] = useState(null);

  const [meta, setMeta] = useState({ token: '', account_id: '' });
  const [campaign, setCampaign] = useState({
    name: '', objective: 'OUTCOME_TRAFFIC', status: 'PAUSED',
    link: '', headline: '', copy: '', description: '', cta: 'LEARN_MORE',
    pageName: '', pageId: '',
    imageBase64: '', imageUrl: '',
  });
  const [audience, setAudience] = useState({
    ageMin: 18, ageMax: 55, genders: [], countries: 'AR',
    interests: '', cities: '',
  });
  const [budget, setBudget] = useState({
    type: 'DAILY', amount: 5, bidStrategy: 'LOWEST_COST_WITHOUT_CAP',
    startDate: '', endDate: '', pixelId: '',
  });

  const connectMeta = async () => {
    if (!meta.token || !meta.account_id) return toast.error('Completa token y account ID');
    setConnecting(true);
    try {
      const resp = await api.post('/meta/connect', { access_token: meta.token, account_id: meta.account_id });
      setAccountInfo(resp.data);
      toast.success(`Conectado: ${resp.data.name} (${resp.data.currency})`);
      setStep(1);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al conectar con Meta');
    } finally { setConnecting(false); }
  };

  const generateCopy = async () => {
    if (!campaign.name) return toast.error('Ingresa el nombre del producto');
    setGenerating(true);
    try {
      const resp = await api.post('/ai/generate', {
        prompt: `Genera copy para un anuncio de Meta Ads en español.
Producto: ${campaign.name}
Objetivo: ${campaign.objective}
Genera: 1 headline (max 40 chars), 1 copy principal (max 125 chars), 1 descripcion (max 30 chars).
Responde SOLO en formato JSON: {"headline":"...","copy":"...","description":"..."}`,
        page_type: 'ad_copy'
      });
      try {
        const content = resp.data.content || resp.data.html || '';
        const jsonMatch = content.match(/\{[\s\S]*?\}/);
        if (jsonMatch) {
          const parsed = JSON.parse(jsonMatch[0]);
          setCampaign(prev => ({
            ...prev,
            headline: parsed.headline || prev.headline,
            copy: parsed.copy || prev.copy,
            description: parsed.description || prev.description,
          }));
          toast.success('Copy generado con IA');
        }
      } catch { toast.error('Error parseando respuesta IA'); }
    } catch (e) {
      toast.error('Error generando copy');
    } finally { setGenerating(false); }
  };

  const generateImage = async () => {
    const prompt = `Professional ad image for: ${campaign.name}. Clean, modern, commercial style. No text overlays, no logos.`;
    setGenImage(true);
    try {
      const resp = await api.post('/images/generate', { prompt, style: 'vivid', size: '1024x1024' }, { timeout: 120000 });
      setCampaign(prev => ({ ...prev, imageBase64: resp.data.image_base64 }));
      toast.success('Imagen generada');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error generando imagen');
    } finally { setGenImage(false); }
  };

  const addLog = useCallback((msg, success = null) => {
    setPublishLog(prev => [...prev, { msg, success, time: new Date().toLocaleTimeString() }]);
  }, []);

  const publishAd = async () => {
    setPublishing(true);
    setPublishLog([]);
    const account = meta.account_id;
    const token = meta.token;

    try {
      // 1. Create campaign
      addLog('Creando campana...');
      const campResp = await api.post('/meta/publish', {
        access_token: token, account_id: account, endpoint: 'campaigns',
        payload: {
          name: `${campaign.name} - Traffic Guardian`,
          objective: campaign.objective,
          status: campaign.status,
          special_ad_categories: [],
        }
      });
      addLog(`Campana creada: ${campResp.data.id}`, true);

      // 2. Upload image if we have one
      let imageHash = '';
      if (campaign.imageBase64) {
        addLog('Subiendo imagen a Meta...');
        try {
          const imgResp = await api.post('/meta/upload-image', {
            access_token: token, account_id: account, image_base64: campaign.imageBase64
          });
          const images = imgResp.data.images;
          if (images) {
            const firstKey = Object.keys(images)[0];
            imageHash = images[firstKey]?.hash || '';
          }
          addLog(`Imagen subida: ${imageHash}`, true);
        } catch (e) {
          addLog('Error subiendo imagen - continuando sin imagen', false);
        }
      }

      // 3. Create ad set
      addLog('Creando Ad Set...');
      const currency = accountInfo?.currency || 'USD';
      const multiplier = currency === 'ARS' ? 100 : 100;
      const dailyBudget = Math.round(budget.amount * multiplier);

      const targeting = { age_min: audience.ageMin, age_max: audience.ageMax };
      if (audience.genders.length > 0) targeting.genders = audience.genders;
      if (audience.countries) {
        targeting.geo_locations = { countries: audience.countries.split(',').map(c => c.trim().toUpperCase()) };
      }
      if (audience.interests) {
        const interestList = audience.interests.split(',').map(i => ({ name: i.trim() }));
        targeting.flexible_spec = [{ interests: interestList }];
      }

      const adsetPayload = {
        name: `${campaign.name} - AdSet`,
        campaign_id: campResp.data.id,
        status: campaign.status,
        billing_event: 'IMPRESSIONS',
        optimization_goal: 'LINK_CLICKS',
        bid_strategy: budget.bidStrategy,
        daily_budget: String(dailyBudget),
        targeting: JSON.stringify(targeting),
      };
      if (budget.startDate) adsetPayload.start_time = budget.startDate;
      if (budget.endDate) adsetPayload.end_time = budget.endDate;

      const adsetResp = await api.post('/meta/publish', {
        access_token: token, account_id: account, endpoint: 'adsets', payload: adsetPayload
      });
      addLog(`Ad Set creado: ${adsetResp.data.id}`, true);

      // 4. Create creative
      addLog('Creando creativo...');
      const linkData = {
        message: campaign.copy,
        link: campaign.link,
        name: campaign.headline,
        description: campaign.description,
        call_to_action: { type: campaign.cta, value: { link: campaign.link } }
      };
      if (imageHash) linkData.image_hash = imageHash;
      if (campaign.imageUrl) linkData.picture = campaign.imageUrl;

      const objectStorySpec = { page_id: campaign.pageId, link_data: linkData };
      const creativeResp = await api.post('/meta/publish', {
        access_token: token, account_id: account, endpoint: 'adcreatives',
        payload: { name: `${campaign.name} - Creative`, object_story_spec: JSON.stringify(objectStorySpec) }
      });
      addLog(`Creativo creado: ${creativeResp.data.id}`, true);

      // 5. Create ad
      addLog('Creando anuncio final...');
      const adResp = await api.post('/meta/publish', {
        access_token: token, account_id: account, endpoint: 'ads',
        payload: {
          name: `${campaign.name} - Ad`,
          adset_id: adsetResp.data.id,
          creative: JSON.stringify({ creative_id: creativeResp.data.id }),
          status: campaign.status,
        }
      });
      addLog(`Anuncio creado: ${adResp.data.id}`, true);
      addLog('Publicacion completa!', true);
      toast.success('Anuncio publicado exitosamente');

    } catch (e) {
      const detail = e.response?.data?.detail;
      const errorMsg = typeof detail === 'object' ? detail.message : (detail || 'Error en publicacion');
      addLog(`Error: ${errorMsg}`, false);
      toast.error(errorMsg);
    } finally { setPublishing(false); }
  };

  const steps = [
    { icon: Link2, label: 'Conectar' },
    { icon: Target, label: 'Objetivo' },
    { icon: Image, label: 'Creativo' },
    { icon: Zap, label: 'Audiencia' },
    { icon: DollarSign, label: 'Presupuesto' },
    { icon: Send, label: 'Publicar' },
  ];

  return (
    <div data-testid="admanage-container" className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">AdManage</h1>
          <p className="text-slate-400">Crea y publica anuncios de Meta Ads</p>
        </div>

        {/* Step indicator */}
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          {steps.map((s, i) => (
            <div key={i} className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${i === step ? 'bg-blue-600 text-white' : i < step ? 'bg-green-600/20 text-green-400 border border-green-500/30' : 'bg-slate-800 text-slate-500'}`}>
              {i < step ? <Check className="w-4 h-4" /> : <s.icon className="w-4 h-4" />}
              {s.label}
            </div>
          ))}
        </div>

        {/* Step 0: Connect */}
        {step === 0 && (
          <Card className="bg-slate-900/50 border-slate-800 p-6 space-y-4">
            <h2 className="text-xl font-semibold text-white">Conectar con Meta Ads</h2>
            <p className="text-slate-400 text-sm">Ingresa tu token de acceso y el ID de tu cuenta publicitaria de <a href="https://developers.facebook.com" target="_blank" rel="noreferrer" className="text-blue-400 underline">developers.facebook.com</a></p>
            <div>
              <Label className="text-slate-300">Access Token</Label>
              <Input type="password" value={meta.token} onChange={e => setMeta({...meta, token: e.target.value})} className="bg-slate-800 border-slate-700 text-white font-mono" placeholder="EAABs..." data-testid="meta-token-input" />
            </div>
            <div>
              <Label className="text-slate-300">Account ID</Label>
              <Input value={meta.account_id} onChange={e => setMeta({...meta, account_id: e.target.value})} className="bg-slate-800 border-slate-700 text-white font-mono" placeholder="act_352435040" data-testid="meta-account-input" />
            </div>
            <Button onClick={connectMeta} disabled={connecting} className="w-full bg-blue-600 hover:bg-blue-700" data-testid="meta-connect-btn">
              {connecting ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Conectando...</> : <><Zap className="w-4 h-4 mr-2" /> Conectar</>}
            </Button>
            {accountInfo && (
              <div className="p-3 bg-green-900/20 border border-green-500/30 rounded-lg text-green-400 text-sm">
                Conectado: {accountInfo.name} | Moneda: {accountInfo.currency}
              </div>
            )}
          </Card>
        )}

        {/* Step 1: Objective */}
        {step === 1 && (
          <Card className="bg-slate-900/50 border-slate-800 p-6 space-y-4">
            <h2 className="text-xl font-semibold text-white">Objetivo de la Campana</h2>
            <div>
              <Label className="text-slate-300">Nombre del producto/servicio</Label>
              <Input value={campaign.name} onChange={e => setCampaign({...campaign, name: e.target.value})} className="bg-slate-800 border-slate-700 text-white" placeholder="Ej: Curso de marketing digital" data-testid="product-name-input" />
            </div>
            <div>
              <Label className="text-slate-300">URL de destino</Label>
              <Input value={campaign.link} onChange={e => setCampaign({...campaign, link: e.target.value})} className="bg-slate-800 border-slate-700 text-white" placeholder="https://www.ares-club.com?c=abc123" data-testid="ad-link-input" />
            </div>
            <div>
              <Label className="text-slate-300 mb-2 block">Objetivo</Label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {OBJECTIVES.map(obj => (
                  <div key={obj.value} onClick={() => setCampaign({...campaign, objective: obj.value})}
                    className={`p-3 rounded-lg cursor-pointer border transition-all ${campaign.objective === obj.value ? 'border-blue-500 bg-blue-500/10 text-white' : 'border-slate-700 bg-slate-800 text-slate-400 hover:border-slate-600'}`} data-testid={`obj-${obj.value}`}>
                    <p className="font-medium text-sm">{obj.label}</p>
                    <p className="text-xs opacity-70">{obj.desc}</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-slate-300">Page ID (Facebook)</Label>
                <Input value={campaign.pageId} onChange={e => setCampaign({...campaign, pageId: e.target.value})} className="bg-slate-800 border-slate-700 text-white" placeholder="123456789" data-testid="page-id-input" />
              </div>
              <div>
                <Label className="text-slate-300">Estado inicial</Label>
                <select value={campaign.status} onChange={e => setCampaign({...campaign, status: e.target.value})} className="w-full bg-slate-800 border border-slate-700 text-white rounded-md h-10 px-3" data-testid="campaign-status-select">
                  <option value="PAUSED">Pausado (draft)</option>
                  <option value="ACTIVE">Activo</option>
                </select>
              </div>
            </div>
          </Card>
        )}

        {/* Step 2: Creative */}
        {step === 2 && (
          <Card className="bg-slate-900/50 border-slate-800 p-6 space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-semibold text-white">Creativo</h2>
              <Button variant="outline" size="sm" onClick={generateCopy} disabled={generating} className="border-purple-500/30 text-purple-400 hover:bg-purple-500/10" data-testid="generate-copy-btn">
                {generating ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Sparkles className="w-4 h-4 mr-1" />}
                Generar con IA
              </Button>
            </div>
            <div>
              <Label className="text-slate-300">Headline</Label>
              <Input value={campaign.headline} onChange={e => setCampaign({...campaign, headline: e.target.value})} className="bg-slate-800 border-slate-700 text-white" placeholder="Headline del anuncio" data-testid="headline-input" />
            </div>
            <div>
              <Label className="text-slate-300">Copy principal</Label>
              <textarea value={campaign.copy} onChange={e => setCampaign({...campaign, copy: e.target.value})} className="w-full bg-slate-800 border border-slate-700 text-white rounded-md p-3 h-24 resize-y" placeholder="Texto del anuncio..." data-testid="copy-input" />
            </div>
            <div>
              <Label className="text-slate-300">Descripcion</Label>
              <Input value={campaign.description} onChange={e => setCampaign({...campaign, description: e.target.value})} className="bg-slate-800 border-slate-700 text-white" placeholder="Descripcion debajo del headline" data-testid="description-input" />
            </div>
            <div>
              <Label className="text-slate-300 mb-2 block">Call To Action</Label>
              <div className="flex flex-wrap gap-2">
                {CTAS.map(c => (
                  <button key={c.value} onClick={() => setCampaign({...campaign, cta: c.value})}
                    className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${campaign.cta === c.value ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:bg-slate-700'}`} data-testid={`cta-${c.value}`}>
                    {c.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="border border-slate-700 rounded-lg p-4 space-y-3">
              <div className="flex justify-between items-center">
                <Label className="text-slate-300">Imagen del anuncio</Label>
                <Button variant="outline" size="sm" onClick={generateImage} disabled={genImage} className="border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10" data-testid="generate-image-btn">
                  {genImage ? <><Loader2 className="w-4 h-4 mr-1 animate-spin" /> Generando...</> : <><Image className="w-4 h-4 mr-1" /> Generar Imagen IA</>}
                </Button>
              </div>
              {campaign.imageBase64 && (
                <div className="rounded-lg overflow-hidden border border-slate-700">
                  <img src={`data:image/png;base64,${campaign.imageBase64}`} alt="Ad" className="w-full max-h-64 object-contain bg-slate-950" data-testid="generated-ad-image" />
                </div>
              )}
              <div>
                <Label className="text-slate-300 text-xs">O pega una URL de imagen</Label>
                <Input value={campaign.imageUrl} onChange={e => setCampaign({...campaign, imageUrl: e.target.value})} className="bg-slate-800 border-slate-700 text-white text-sm" placeholder="https://..." data-testid="image-url-input" />
              </div>
            </div>
          </Card>
        )}

        {/* Step 3: Audience */}
        {step === 3 && (
          <Card className="bg-slate-900/50 border-slate-800 p-6 space-y-4">
            <h2 className="text-xl font-semibold text-white">Audiencia</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-slate-300">Edad minima</Label>
                <Input type="number" value={audience.ageMin} onChange={e => setAudience({...audience, ageMin: parseInt(e.target.value)})} className="bg-slate-800 border-slate-700 text-white" data-testid="age-min-input" />
              </div>
              <div>
                <Label className="text-slate-300">Edad maxima</Label>
                <Input type="number" value={audience.ageMax} onChange={e => setAudience({...audience, ageMax: parseInt(e.target.value)})} className="bg-slate-800 border-slate-700 text-white" data-testid="age-max-input" />
              </div>
            </div>
            <div>
              <Label className="text-slate-300">Paises (separados por coma)</Label>
              <Input value={audience.countries} onChange={e => setAudience({...audience, countries: e.target.value})} className="bg-slate-800 border-slate-700 text-white" placeholder="AR, MX, CO" data-testid="countries-input" />
            </div>
            <div>
              <Label className="text-slate-300">Ciudades (opcional)</Label>
              <Input value={audience.cities} onChange={e => setAudience({...audience, cities: e.target.value})} className="bg-slate-800 border-slate-700 text-white" placeholder="Buenos Aires, Cordoba" data-testid="cities-input" />
            </div>
            <div>
              <Label className="text-slate-300">Intereses (separados por coma)</Label>
              <textarea value={audience.interests} onChange={e => setAudience({...audience, interests: e.target.value})} className="w-full bg-slate-800 border border-slate-700 text-white rounded-md p-3 h-20 resize-y" placeholder="marketing digital, emprendimiento, negocios..." data-testid="interests-input" />
            </div>
          </Card>
        )}

        {/* Step 4: Budget */}
        {step === 4 && (
          <Card className="bg-slate-900/50 border-slate-800 p-6 space-y-4">
            <h2 className="text-xl font-semibold text-white">Presupuesto</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-slate-300">Tipo</Label>
                <select value={budget.type} onChange={e => setBudget({...budget, type: e.target.value})} className="w-full bg-slate-800 border border-slate-700 text-white rounded-md h-10 px-3" data-testid="budget-type-select">
                  <option value="DAILY">Diario</option>
                  <option value="LIFETIME">Total</option>
                </select>
              </div>
              <div>
                <Label className="text-slate-300">Monto ({accountInfo?.currency || 'USD'})</Label>
                <Input type="number" value={budget.amount} onChange={e => setBudget({...budget, amount: parseFloat(e.target.value)})} className="bg-slate-800 border-slate-700 text-white" data-testid="budget-amount-input" />
              </div>
            </div>
            <div>
              <Label className="text-slate-300">Estrategia de oferta</Label>
              <select value={budget.bidStrategy} onChange={e => setBudget({...budget, bidStrategy: e.target.value})} className="w-full bg-slate-800 border border-slate-700 text-white rounded-md h-10 px-3" data-testid="bid-strategy-select">
                <option value="LOWEST_COST_WITHOUT_CAP">Menor costo (automatico)</option>
                <option value="LOWEST_COST_WITH_BID_CAP">Menor costo con tope</option>
                <option value="COST_CAP">Costo por resultado</option>
              </select>
            </div>
            <div>
              <Label className="text-slate-300">Pixel ID (opcional)</Label>
              <Input value={budget.pixelId} onChange={e => setBudget({...budget, pixelId: e.target.value})} className="bg-slate-800 border-slate-700 text-white" placeholder="123456789" data-testid="pixel-id-input" />
            </div>
          </Card>
        )}

        {/* Step 5: Publish */}
        {step === 5 && (
          <Card className="bg-slate-900/50 border-slate-800 p-6 space-y-4">
            <h2 className="text-xl font-semibold text-white">Resumen y Publicar</h2>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="space-y-2">
                <div className="p-3 bg-slate-800 rounded-lg">
                  <p className="text-slate-500 text-xs">Campana</p>
                  <p className="text-white font-medium">{campaign.name}</p>
                </div>
                <div className="p-3 bg-slate-800 rounded-lg">
                  <p className="text-slate-500 text-xs">Objetivo</p>
                  <p className="text-white">{OBJECTIVES.find(o => o.value === campaign.objective)?.label}</p>
                </div>
                <div className="p-3 bg-slate-800 rounded-lg">
                  <p className="text-slate-500 text-xs">Presupuesto</p>
                  <p className="text-white">{budget.amount} {accountInfo?.currency || 'USD'} / {budget.type === 'DAILY' ? 'dia' : 'total'}</p>
                </div>
              </div>
              <div className="space-y-2">
                <div className="p-3 bg-slate-800 rounded-lg">
                  <p className="text-slate-500 text-xs">URL destino</p>
                  <p className="text-cyan-400 text-xs truncate">{campaign.link}</p>
                </div>
                <div className="p-3 bg-slate-800 rounded-lg">
                  <p className="text-slate-500 text-xs">Audiencia</p>
                  <p className="text-white">{audience.countries} | {audience.ageMin}-{audience.ageMax}</p>
                </div>
                <div className="p-3 bg-slate-800 rounded-lg">
                  <p className="text-slate-500 text-xs">CTA</p>
                  <p className="text-white">{CTAS.find(c => c.value === campaign.cta)?.label}</p>
                </div>
              </div>
            </div>

            {campaign.imageBase64 && (
              <div className="rounded-lg overflow-hidden border border-slate-700 max-h-40">
                <img src={`data:image/png;base64,${campaign.imageBase64}`} alt="Preview" className="w-full max-h-40 object-contain bg-slate-950" />
              </div>
            )}

            <div className="flex gap-3">
              <Button onClick={() => { setCampaign({...campaign, status: 'PAUSED'}); publishAd(); }} disabled={publishing} className="flex-1 bg-slate-700 hover:bg-slate-600" data-testid="publish-draft-btn">
                {publishing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null} Guardar como borrador
              </Button>
              <Button onClick={() => { setCampaign({...campaign, status: 'ACTIVE'}); publishAd(); }} disabled={publishing} className="flex-1 bg-green-600 hover:bg-green-700" data-testid="publish-active-btn">
                {publishing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Send className="w-4 h-4 mr-2" />} Publicar activo
              </Button>
            </div>

            {publishLog.length > 0 && (
              <div className="bg-slate-950 border border-slate-700 rounded-lg p-4 space-y-2 max-h-60 overflow-y-auto" data-testid="publish-log">
                {publishLog.map((log, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm">
                    {log.success === true ? <Check className="w-4 h-4 text-green-400 flex-shrink-0" /> :
                     log.success === false ? <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" /> :
                     <Loader2 className="w-4 h-4 text-blue-400 animate-spin flex-shrink-0" />}
                    <span className={log.success === false ? 'text-red-400' : log.success === true ? 'text-green-400' : 'text-slate-400'}>{log.msg}</span>
                    <span className="text-slate-600 text-xs ml-auto">{log.time}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        )}

        {/* Navigation */}
        {step > 0 && (
          <div className="flex justify-between">
            <Button variant="outline" onClick={() => setStep(step - 1)} className="border-slate-700 text-slate-300 hover:bg-slate-800" data-testid="prev-step-btn">
              <ArrowLeft className="w-4 h-4 mr-2" /> Anterior
            </Button>
            {step < 5 && (
              <Button onClick={() => setStep(step + 1)} className="bg-blue-600 hover:bg-blue-700" data-testid="next-step-btn">
                Siguiente <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default AdManage;
