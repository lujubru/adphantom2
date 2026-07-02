import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Tag as TagIcon, Plus, X, Check, Pencil, Trash2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/utils/api';

export const TAG_MAX_PER_LEAD = 5;

export const TAG_PALETTE = [
  '#ef4444', '#f59e0b', '#eab308', '#22c55e', '#14b8a6',
  '#3b82f6', '#8b5cf6', '#ec4899', '#64748b',
];

/** Small color pill for a tag. */
export const TagChip = ({ tag, onRemove, size = 'sm' }) => {
  if (!tag) return null;
  const px = size === 'xs' ? 'px-1.5 py-0 text-[10px]' : 'px-2 py-0.5 text-[11px]';
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full font-medium ${px} text-white`}
      style={{ backgroundColor: tag.color || '#64748b' }}
      data-testid={`tag-chip-${tag.id}`}
      title={tag.name}
    >
      <span className="truncate max-w-[100px]">{tag.name}</span>
      {onRemove && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onRemove(tag); }}
          className="opacity-70 hover:opacity-100"
          aria-label={`Quitar etiqueta ${tag.name}`}
          data-testid={`tag-remove-${tag.id}`}
        >
          <X className="w-2.5 h-2.5" />
        </button>
      )}
    </span>
  );
};

/** Compact row of tag chips for use inside chat list items and cards. */
export const TagChipList = ({ tags, max = 3, size = 'xs' }) => {
  if (!tags || tags.length === 0) return null;
  const visible = tags.slice(0, max);
  const rest = tags.length - visible.length;
  return (
    <div className="flex items-center gap-1 flex-wrap">
      {visible.map((t) => (
        <TagChip key={t.id} tag={t} size={size} />
      ))}
      {rest > 0 && (
        <span className="text-[10px] text-slate-400 font-medium">+{rest}</span>
      )}
    </div>
  );
};

/**
 * Inline bar to display and edit the tags of a lead.
 * Opens a small popover with checkboxes to add/remove tags.
 */
export const LeadTagsBar = ({ lead, onChange }) => {
  const [tags, setTags] = useState(Array.isArray(lead?.tag_details) ? lead.tag_details : []);
  const [tagIds, setTagIds] = useState(Array.isArray(lead?.tags) ? lead.tags : []);
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [availableTags, setAvailableTags] = useState([]);
  const [loadingList, setLoadingList] = useState(false);
  const [saving, setSaving] = useState(false);
  const popRef = useRef(null);

  useEffect(() => {
    setTags(Array.isArray(lead?.tag_details) ? lead.tag_details : []);
    setTagIds(Array.isArray(lead?.tags) ? lead.tags : []);
  }, [lead?.id, lead?.tag_details, lead?.tags]);

  useEffect(() => {
    if (!popoverOpen) return;
    const onDown = (e) => {
      if (popRef.current && !popRef.current.contains(e.target)) setPopoverOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [popoverOpen]);

  const loadAvailable = async () => {
    if (!lead?.line_id) return;
    setLoadingList(true);
    try {
      const { data } = await api.get('/crm/tags', { params: { line_id: lead.line_id } });
      setAvailableTags(data || []);
    } catch {
      toast.error('Error cargando etiquetas');
    } finally {
      setLoadingList(false);
    }
  };

  const openPopover = async () => {
    setPopoverOpen(true);
    await loadAvailable();
  };

  const persistTags = async (nextIds) => {
    setSaving(true);
    try {
      const { data } = await api.patch(`/crm/leads/${lead.id}/tags`, { tag_ids: nextIds });
      const nextTagDetails = (data?.lead?.tags || nextIds)
        .map((id) => (availableTags.find((t) => t.id === id) || tags.find((t) => t.id === id)))
        .filter(Boolean);
      setTagIds(data?.tags || nextIds);
      setTags(nextTagDetails);
      onChange?.({ tags: data?.tags || nextIds, tag_details: nextTagDetails });
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error guardando etiquetas');
    } finally {
      setSaving(false);
    }
  };

  const toggleTag = (tag) => {
    const has = tagIds.includes(tag.id);
    let next;
    if (has) {
      next = tagIds.filter((id) => id !== tag.id);
    } else {
      if (tagIds.length >= TAG_MAX_PER_LEAD) {
        toast.error(`Máximo ${TAG_MAX_PER_LEAD} etiquetas por chat`);
        return;
      }
      next = [...tagIds, tag.id];
    }
    persistTags(next);
  };

  const removeTag = (tag) => persistTags(tagIds.filter((id) => id !== tag.id));

  return (
    <div className="relative inline-flex items-center gap-1 flex-wrap" data-testid="lead-tags-bar">
      {tags.map((t) => (
        <TagChip key={t.id} tag={t} size="xs" onRemove={removeTag} />
      ))}
      <button
        type="button"
        onClick={openPopover}
        disabled={saving}
        className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full border border-dashed border-slate-600 text-slate-400 hover:text-emerald-400 hover:border-emerald-500 text-[10px] transition-colors disabled:opacity-50"
        data-testid="lead-tags-add-btn"
        title="Agregar / quitar etiquetas"
      >
        {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <TagIcon className="w-3 h-3" />}
        <span>{tags.length ? 'editar' : 'etiquetas'}</span>
      </button>
      {popoverOpen && (
        <div
          ref={popRef}
          className="absolute top-full left-0 mt-1 z-40 w-56 max-h-64 overflow-y-auto rounded-lg border border-slate-700 bg-slate-900 shadow-xl p-2"
          data-testid="lead-tags-popover"
        >
          <div className="text-[10px] text-slate-500 uppercase tracking-wide px-1 pb-1">
            {tagIds.length}/{TAG_MAX_PER_LEAD} · {lead.line_name || 'línea'}
          </div>
          {loadingList ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="w-4 h-4 text-slate-500 animate-spin" />
            </div>
          ) : availableTags.length === 0 ? (
            <div className="px-2 py-3 text-xs text-slate-500 text-center">
              No hay etiquetas en esta línea.<br />
              <span className="text-slate-600">Creá una desde el botón &quot;Etiquetas&quot;.</span>
            </div>
          ) : (
            <ul className="space-y-0.5">
              {availableTags.map((t) => {
                const active = tagIds.includes(t.id);
                return (
                  <li key={t.id}>
                    <button
                      type="button"
                      onClick={() => toggleTag(t)}
                      disabled={saving}
                      className={`w-full flex items-center justify-between gap-2 px-2 py-1.5 rounded text-xs transition-colors ${
                        active ? 'bg-slate-800' : 'hover:bg-slate-800/60'
                      }`}
                      data-testid={`lead-tags-option-${t.id}`}
                    >
                      <span className="flex items-center gap-2 min-w-0">
                        <span
                          className="inline-block w-3 h-3 rounded-full shrink-0"
                          style={{ backgroundColor: t.color }}
                        />
                        <span className="text-slate-200 truncate">{t.name}</span>
                      </span>
                      {active && <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

/**
 * Full CRUD manager for tags. Renders as a modal when `open` is true.
 * Lets user pick a line, list tags, create/edit/delete.
 */
export const TagsManagerModal = ({ open, onClose, lines, defaultLineId }) => {
  const [lineId, setLineId] = useState(defaultLineId || (lines?.[0]?.id ?? ''));
  const [tags, setTags] = useState([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newColor, setNewColor] = useState(TAG_PALETTE[3]);
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');
  const [editColor, setEditColor] = useState('');

  useEffect(() => {
    if (open) setLineId(defaultLineId || (lines?.[0]?.id ?? ''));
  }, [open, defaultLineId, lines]);

  const load = async () => {
    if (!lineId) return;
    setLoading(true);
    try {
      const { data } = await api.get('/crm/tags', { params: { line_id: lineId } });
      setTags(data || []);
    } catch {
      toast.error('Error cargando etiquetas');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) load();
  }, [open, lineId]);

  const create = async (e) => {
    e?.preventDefault();
    if (!newName.trim() || !lineId) return;
    setCreating(true);
    try {
      const { data } = await api.post('/crm/tags', {
        line_id: lineId,
        name: newName.trim(),
        color: newColor,
      });
      setTags((prev) => [...prev, data].sort((a, b) => a.name.localeCompare(b.name)));
      setNewName('');
      toast.success('Etiqueta creada');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error creando etiqueta');
    } finally {
      setCreating(false);
    }
  };

  const startEdit = (t) => {
    setEditingId(t.id);
    setEditName(t.name);
    setEditColor(t.color);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditName('');
    setEditColor('');
  };

  const saveEdit = async () => {
    if (!editingId || !editName.trim()) return;
    try {
      const { data } = await api.put(`/crm/tags/${editingId}`, { name: editName.trim(), color: editColor });
      setTags((prev) => prev.map((t) => (t.id === editingId ? data : t)).sort((a, b) => a.name.localeCompare(b.name)));
      cancelEdit();
      toast.success('Etiqueta actualizada');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error actualizando');
    }
  };

  const removeTag = async (t) => {
    if (!window.confirm(`¿Eliminar la etiqueta "${t.name}"? Se quitará de todos los chats que la tengan.`)) return;
    try {
      await api.delete(`/crm/tags/${t.id}`);
      setTags((prev) => prev.filter((x) => x.id !== t.id));
      toast.success('Etiqueta eliminada');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Error eliminando');
    }
  };

  const linesToShow = useMemo(() => Array.isArray(lines) ? lines : [], [lines]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[70] bg-black/60 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4"
      onClick={onClose}
      data-testid="tags-manager-modal"
    >
      <div
        className="w-full max-w-lg max-h-[90vh] overflow-y-auto bg-slate-900 rounded-xl border border-slate-700 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-700 sticky top-0 bg-slate-900 z-10">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2">
            <TagIcon className="w-4 h-4 text-emerald-400" /> Etiquetas
          </h2>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800"
            data-testid="tags-manager-close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div>
            <label className="text-[11px] text-slate-400 uppercase tracking-wide font-semibold">Línea</label>
            <select
              value={lineId}
              onChange={(e) => setLineId(e.target.value)}
              className="mt-1 w-full bg-slate-800 border border-slate-700 text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              data-testid="tags-manager-line-select"
            >
              {linesToShow.length === 0 ? (
                <option value="">— sin líneas —</option>
              ) : (
                linesToShow.map((l) => (
                  <option key={l.id} value={l.id}>{l.name}</option>
                ))
              )}
            </select>
            <p className="text-[10px] text-slate-500 mt-1">
              Las etiquetas son <strong>por línea</strong>. Cada cajero ve solo las de sus líneas.
            </p>
          </div>

          {/* Create form */}
          <form onSubmit={create} className="rounded-lg border border-slate-700 bg-slate-800/50 p-3 space-y-2" data-testid="tag-create-form">
            <div className="text-xs font-semibold text-slate-300">Nueva etiqueta</div>
            <div className="flex items-center gap-2">
              <input
                type="text"
                placeholder="Ej: VIP, Consulta, No responde…"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                maxLength={40}
                className="flex-1 bg-slate-900 border border-slate-700 text-white text-sm rounded px-2.5 py-1.5 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                data-testid="tag-create-name"
                disabled={!lineId || creating}
              />
              <button
                type="submit"
                disabled={!newName.trim() || !lineId || creating}
                className="inline-flex items-center gap-1 px-3 py-1.5 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-40 disabled:cursor-not-allowed text-slate-900 text-xs font-semibold rounded transition-colors"
                data-testid="tag-create-submit"
              >
                {creating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                Crear
              </button>
            </div>
            <div className="flex items-center gap-1.5 flex-wrap">
              {TAG_PALETTE.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setNewColor(c)}
                  className={`w-6 h-6 rounded-full border-2 transition-transform ${newColor === c ? 'border-white scale-110' : 'border-transparent hover:scale-105'}`}
                  style={{ backgroundColor: c }}
                  aria-label={`Color ${c}`}
                  data-testid={`tag-create-color-${c}`}
                />
              ))}
            </div>
          </form>

          {/* List */}
          <div className="rounded-lg border border-slate-700 divide-y divide-slate-800" data-testid="tag-list">
            {loading ? (
              <div className="flex items-center justify-center py-6">
                <Loader2 className="w-4 h-4 text-slate-500 animate-spin" />
              </div>
            ) : tags.length === 0 ? (
              <div className="py-6 text-center text-xs text-slate-500">Todavía no hay etiquetas en esta línea.</div>
            ) : (
              tags.map((t) => (
                <div key={t.id} className="flex items-center justify-between gap-2 px-3 py-2" data-testid={`tag-row-${t.id}`}>
                  {editingId === t.id ? (
                    <>
                      <div className="flex items-center gap-2 flex-1">
                        <span className="inline-block w-4 h-4 rounded-full shrink-0" style={{ backgroundColor: editColor }} />
                        <input
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          maxLength={40}
                          className="flex-1 bg-slate-900 border border-slate-700 text-white text-xs rounded px-2 py-1"
                          data-testid={`tag-edit-name-${t.id}`}
                        />
                        <div className="flex items-center gap-1">
                          {TAG_PALETTE.slice(0, 6).map((c) => (
                            <button
                              key={c}
                              type="button"
                              onClick={() => setEditColor(c)}
                              className={`w-4 h-4 rounded-full border ${editColor === c ? 'border-white' : 'border-transparent'}`}
                              style={{ backgroundColor: c }}
                            />
                          ))}
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <button onClick={saveEdit} className="p-1 text-emerald-400 hover:text-emerald-300 rounded hover:bg-emerald-500/10" data-testid={`tag-edit-save-${t.id}`}>
                          <Check className="w-4 h-4" />
                        </button>
                        <button onClick={cancelEdit} className="p-1 text-slate-400 hover:text-red-400 rounded hover:bg-red-500/10">
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        <TagChip tag={t} size="sm" />
                        <span className="text-[10px] text-slate-500">por {t.created_by || '—'}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => startEdit(t)}
                          className="p-1 text-slate-400 hover:text-blue-400 rounded hover:bg-blue-500/10"
                          data-testid={`tag-edit-btn-${t.id}`}
                          title="Editar"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => removeTag(t)}
                          className="p-1 text-slate-400 hover:text-red-400 rounded hover:bg-red-500/10"
                          data-testid={`tag-delete-btn-${t.id}`}
                          title="Eliminar"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
