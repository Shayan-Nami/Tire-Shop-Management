import React from 'react';
import { Inbox } from 'lucide-react';

export interface EmptyStateProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  /** Defaults to an inbox glyph; pass `null` to omit. */
  icon?: React.ReactNode;
  /** Usually a button or link. */
  action?: React.ReactNode;
  /** Grow to fill a flex-column panel body so the empty message is vertically centred. */
  fill?: boolean;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ title, description, icon, action, fill = false, className = '' }) => (
  <div className={`empty-state${fill ? ' empty-state-fill' : ''} ${className}`}>
    {icon === null ? null : <span className="empty-state-icon" aria-hidden="true">{icon ?? <Inbox className="w-5 h-5" />}</span>}
    <p className="empty-state-title">{title}</p>
    {description ? <p className="empty-state-text">{description}</p> : null}
    {action ? <div className="empty-state-action">{action}</div> : null}
  </div>
);
