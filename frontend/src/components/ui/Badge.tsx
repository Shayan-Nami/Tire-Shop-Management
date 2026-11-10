import React from 'react';

export type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'accent';

export interface BadgeProps {
  tone?: BadgeTone;
  /** Leading status dot. */
  dot?: boolean;
  className?: string;
  children: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({ tone = 'neutral', dot = false, className = '', children }) => (
  <span className={`badge badge-${tone}${dot ? ' badge-dot' : ''}${className ? ` ${className}` : ''}`}>{children}</span>
);

const STATUS_TONES: Record<string, BadgeTone> = {
  PAID: 'success', CONFIRMED: 'success', ACTIVE: 'success', COMPLETED: 'success', IN_STOCK: 'success',
  PARTIAL: 'warning', PENDING: 'warning', LOW_STOCK: 'warning',
  UNPAID: 'danger', CANCELLED: 'danger', OVERDUE: 'danger', OUT_OF_STOCK: 'danger',
  DRAFT: 'neutral', INACTIVE: 'neutral',
};

export interface StatusBadgeProps {
  /** Backend status code, e.g. PAID / UNPAID / PARTIAL / CONFIRMED / CANCELLED / DRAFT. */
  status: string;
  /** Visible text (e.g. `status_display` or a translated label); falls back to the raw code. */
  label?: React.ReactNode;
  /** Overrides the tone inferred from `status`. */
  tone?: BadgeTone;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, label, tone, className }) => (
  <Badge tone={tone ?? STATUS_TONES[status.toUpperCase()] ?? 'neutral'} dot className={className}>{label ?? status}</Badge>
);
