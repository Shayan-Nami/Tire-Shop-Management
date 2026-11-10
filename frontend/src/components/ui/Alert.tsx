import React from 'react';
import { CircleAlert, CircleCheck, Info, RotateCw, TriangleAlert, X } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';

export type AlertTone = 'info' | 'success' | 'warning' | 'danger';

const ICONS = { info: Info, success: CircleCheck, warning: TriangleAlert, danger: CircleAlert } as const;

export interface InlineAlertProps {
  tone?: AlertTone;
  title?: React.ReactNode;
  children?: React.ReactNode;
  /** Optional buttons rendered under the message. */
  actions?: React.ReactNode;
  onDismiss?: () => void;
  /** Defaults to `alert` for danger/warning and `status` otherwise. */
  role?: 'alert' | 'status';
  className?: string;
}

export const InlineAlert: React.FC<InlineAlertProps> = ({ tone = 'info', title, children, actions, onDismiss, role, className = '' }) => {
  const { t } = useLanguage();
  const Icon = ICONS[tone];
  return (
    <div role={role ?? (tone === 'danger' || tone === 'warning' ? 'alert' : 'status')} className={`alert alert-${tone} ${className}`}>
      <Icon className="w-4 h-4" aria-hidden="true" />
      <div className="alert-body">
        {title ? <p className="alert-title">{title}</p> : null}
        {children ? <div>{children}</div> : null}
        {actions ? <div className="alert-actions">{actions}</div> : null}
      </div>
      {onDismiss ? (
        <button type="button" className="icon-btn icon-btn-sm -my-1" aria-label={t('بستن')} onClick={onDismiss}>
          <X className="w-4 h-4" aria-hidden="true" />
        </button>
      ) : null}
    </div>
  );
};

export interface ErrorStateProps {
  message: React.ReactNode;
  title?: React.ReactNode;
  /** Renders a retry button when provided. */
  onRetry?: () => void;
  retryLabel?: string;
  /** Single-line alert instead of a centred panel; use inside cards and forms. */
  compact?: boolean;
  className?: string;
}

export const ErrorState: React.FC<ErrorStateProps> = ({ message, title, onRetry, retryLabel, compact = false, className = '' }) => {
  const { t } = useLanguage();
  const retry = onRetry ? (
    <button type="button" className="btn-secondary btn-sm" onClick={onRetry}>
      <RotateCw className="w-3.5 h-3.5" aria-hidden="true" />
      <span>{retryLabel ?? t('تلاش دوباره')}</span>
    </button>
  ) : null;

  if (compact) {
    return <InlineAlert tone="danger" title={title} actions={retry} className={className}>{message}</InlineAlert>;
  }
  return (
    <div role="alert" className={`surface-panel error-state ${className}`}>
      <span className="empty-state-icon" aria-hidden="true"><CircleAlert className="w-5 h-5" /></span>
      <p className="empty-state-title">{title ?? t('دریافت اطلاعات ناموفق بود')}</p>
      <p className="empty-state-text">{message}</p>
      {retry ? <div className="empty-state-action">{retry}</div> : null}
    </div>
  );
};
