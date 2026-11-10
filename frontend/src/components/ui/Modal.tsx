import React, { useEffect, useId, useRef } from 'react';
import { X } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';

export type ModalSize = 'sm' | 'md' | 'lg' | 'xl';

export interface ModalProps {
  children: React.ReactNode;
  onClose: () => void;
  /** Accessible name for bare modals (no `title`). */
  label?: string;
  /** When set, Modal renders its own card: header with close button, body and optional footer. */
  title?: React.ReactNode;
  description?: React.ReactNode;
  footer?: React.ReactNode;
  size?: ModalSize;
  /** Blocks Esc, backdrop and close-button dismissal while a request is in flight. */
  busy?: boolean;
  className?: string;
}

const BODY_CONTROLS = 'input:not([type="hidden"]):not(:disabled), select:not(:disabled), textarea:not(:disabled)';

export const Modal: React.FC<ModalProps> = ({
  children, onClose, label, title, description, footer, size = 'md', busy = false, className = '',
}) => {
  const { t } = useLanguage();
  const ref = useRef<HTMLDialogElement>(null);
  const pressedOnBackdrop = useRef(false);
  const titleId = useId();
  const descriptionId = useId();
  const structured = title !== undefined && title !== null && title !== '';

  useEffect(() => {
    const dialog = ref.current;
    const trigger = document.activeElement;
    if (dialog && !dialog.open) dialog.showModal();
    const preferred = dialog?.querySelector<HTMLElement>('[data-autofocus]') ?? dialog?.querySelector<HTMLElement>(`.modal-body ${BODY_CONTROLS.replaceAll(', ', ', .modal-body ')}`);
    preferred?.focus();
    return () => {
      dialog?.close();
      if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus();
    };
  }, []);

  return (
    <dialog
      ref={ref}
      aria-label={structured ? undefined : label}
      aria-labelledby={structured ? titleId : undefined}
      aria-describedby={structured && description ? descriptionId : undefined}
      aria-busy={busy}
      className={`app-modal ${className}`}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
      onMouseDown={(event) => { pressedOnBackdrop.current = event.target === event.currentTarget; }}
      onClick={(event) => {
        if (pressedOnBackdrop.current && event.target === event.currentTarget && !busy) onClose();
        pressedOnBackdrop.current = false;
      }}
    >
      {structured ? (
        <div className={`modal-card modal-structured modal-${size}`}>
          <div className="modal-header">
            <div className="min-w-0">
              <h2 id={titleId} className="modal-title">{title}</h2>
              {description ? <p id={descriptionId} className="modal-description">{description}</p> : null}
            </div>
            <button type="button" className="icon-btn icon-btn-sm modal-close" aria-label={t('بستن پنجره')} onClick={onClose} disabled={busy}>
              <X className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
          <div className="modal-body">{children}</div>
          {footer ? <div className="modal-footer">{footer}</div> : null}
        </div>
      ) : children}
    </dialog>
  );
};
