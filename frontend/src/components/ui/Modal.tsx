import React, { useEffect, useRef } from 'react';

interface ModalProps {
  children: React.ReactNode;
  onClose: () => void;
  label: string;
  busy?: boolean;
  className?: string;
}

export const Modal: React.FC<ModalProps> = ({ children, onClose, label, busy = false, className = '' }) => {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    const trigger = typeof document !== 'undefined' ? document.activeElement : null;
    if (dialog && typeof dialog.showModal === 'function' && !dialog.open) {
      dialog.showModal();
    }
    return () => {
      if (dialog?.open && typeof dialog.close === 'function') {
        dialog.close();
      }
      if (typeof HTMLElement !== 'undefined' && trigger instanceof HTMLElement && trigger.isConnected) {
        trigger.focus();
      }
    };
  }, []);

  return (
    <dialog
      ref={ref}
      aria-label={label}
      aria-busy={busy}
      className={`app-modal ${className}`}
      onClick={(event) => {
        if (event.target === ref.current && !busy) onClose();
      }}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      {children}
    </dialog>
  );
};
