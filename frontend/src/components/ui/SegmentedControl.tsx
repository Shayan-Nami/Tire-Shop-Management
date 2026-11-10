import React from 'react';

export type SegmentTone = 'success' | 'warning' | 'danger' | 'info';

export interface SegmentOption<T extends string | number | boolean> {
  value: T;
  label: React.ReactNode;
  icon?: React.ReactNode;
  /** Tints the active state (default is the amber accent). */
  tone?: SegmentTone;
  disabled?: boolean;
}

export interface SegmentedControlProps<T extends string | number | boolean> {
  value: T;
  onChange: (value: T) => void;
  options: ReadonlyArray<SegmentOption<T>>;
  /** Required: names the group for assistive tech. */
  ariaLabel: string;
  size?: 'md' | 'sm';
  /** Stretch to the container width with equal-width options. */
  block?: boolean;
  className?: string;
}

export function SegmentedControl<T extends string | number | boolean>({
  value, onChange, options, ariaLabel, size = 'md', block = false, className = '',
}: SegmentedControlProps<T>): React.ReactElement {
  return (
    <div role="group" aria-label={ariaLabel} className={`segmented${size === 'sm' ? ' segmented-sm' : ''}${block ? ' segmented-block' : ''} ${className}`}>
      {options.map((option) => (
        <button
          key={String(option.value)}
          type="button"
          className="segmented-option"
          aria-pressed={option.value === value}
          data-tone={option.tone}
          disabled={option.disabled}
          onClick={() => { if (option.value !== value) onChange(option.value); }}
        >
          {option.icon}
          <span>{option.label}</span>
        </button>
      ))}
    </div>
  );
}
