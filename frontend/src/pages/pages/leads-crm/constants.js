import { Users, Trash2, MessageCircle, DollarSign } from 'lucide-react';

export const STATUS_CONFIG = {
  nuevo:     { label: 'Nuevo',     color: 'bg-blue-500/20 text-blue-400 border-blue-500/30',           bgColumn: 'bg-blue-950/30',    dot: 'bg-blue-400',    icon: Users },
  spam:      { label: 'Spam',      color: 'bg-red-500/20 text-red-400 border-red-500/30',              bgColumn: 'bg-red-950/30',     dot: 'bg-red-400',     icon: Trash2 },
  consultas: { label: 'Consultas', color: 'bg-amber-500/20 text-amber-400 border-amber-500/30',        bgColumn: 'bg-amber-950/30',   dot: 'bg-amber-400',   icon: MessageCircle },
  valido:    { label: 'Válido',    color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',  bgColumn: 'bg-emerald-950/30', dot: 'bg-emerald-400', icon: DollarSign },
};

export const LINE_TYPE_CONFIG = {
  publi:     { label: 'Publicidad', color: 'bg-blue-500/20 text-blue-400' },
  principal: { label: 'Principal',  color: 'bg-emerald-500/20 text-emerald-400' },
  spam:      { label: 'Spam',       color: 'bg-red-500/20 text-red-400' },
};

export const STATUS_ORDER = ['nuevo', 'spam', 'consultas', 'valido'];

export const BADGE_COLORS = {
  blue:    { bg: 'bg-blue-500/15',    border: 'border-blue-500/40',    text: 'text-blue-300',    icon: 'text-blue-400',    dot: 'bg-blue-400' },
  emerald: { bg: 'bg-emerald-500/15', border: 'border-emerald-500/40', text: 'text-emerald-300', icon: 'text-emerald-400', dot: 'bg-emerald-400' },
  amber:   { bg: 'bg-amber-500/15',   border: 'border-amber-500/40',   text: 'text-amber-300',   icon: 'text-amber-400',   dot: 'bg-amber-400' },
};

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
