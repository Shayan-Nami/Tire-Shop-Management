import React, { useId } from 'react';
import { useLanguage } from '../../context/LanguageContext';

export interface FieldControlProps {
  id: string;
  'aria-describedby'?: string;
  'aria-invalid'?: true;
  'aria-required'?: true;
}

export interface FieldProps {
  label: React.ReactNode;
  hint?: React.ReactNode;
  /** Validation message; also marks the control `aria-invalid`. */
  error?: React.ReactNode;
  required?: boolean;
  /** Shows an "(optional)" tag instead of the required asterisk. */
  optional?: boolean;
  className?: string;
  /** A single control element (gets id/aria props injected) or a render function for wrapped controls. */
  children: React.ReactElement<Record<string, unknown>> | ((control: FieldControlProps) => React.ReactNode);
}

export const Field: React.FC<FieldProps> = ({ label, hint, error, required, optional, className = '', children }) => {
  const { t } = useLanguage();
  const uid = useId();
  const hintId = `${uid}-hint`;
  const errorId = `${uid}-error`;
  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(' ') || undefined;

  const control: FieldControlProps = {
    id: React.isValidElement(children) && typeof children.props.id === 'string' ? children.props.id : uid,
    'aria-describedby': describedBy,
    'aria-invalid': error ? true : undefined,
    'aria-required': required ? true : undefined,
  };

  return (
    <div className={`field ${className}`}>
      <label className="field-label" htmlFor={control.id}>
        {label}
        {required ? <span className="field-required" aria-hidden="true">*</span> : null}
        {optional && !required ? <span className="field-optional">({t('اختیاری')})</span> : null}
      </label>
      {typeof children === 'function' ? children(control) : React.cloneElement(children, control as unknown as Record<string, unknown>)}
      {hint ? <p id={hintId} className="field-hint">{hint}</p> : null}
      {error ? <p id={errorId} className="field-error" aria-live="polite">{error}</p> : null}
    </div>
  );
};
