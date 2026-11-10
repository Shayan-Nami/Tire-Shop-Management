import React from 'react';

export interface SkeletonProps {
  className?: string;
  width?: number | string;
  height?: number | string;
  style?: React.CSSProperties;
}

export const Skeleton: React.FC<SkeletonProps> = ({ className = '', width, height, style }) => (
  <span className={`skeleton ${className}`} style={{ width, height, ...style }} aria-hidden="true" />
);

export const SkeletonText: React.FC<{ lines?: number; className?: string }> = ({ lines = 3, className = '' }) => (
  <div className={className} aria-hidden="true">
    {Array.from({ length: lines }, (_, index) => (
      <Skeleton key={index} className="skeleton-line" width={index === lines - 1 && lines > 1 ? '60%' : '100%'} />
    ))}
  </div>
);

export const Spinner: React.FC<{ large?: boolean; className?: string }> = ({ large = false, className = '' }) => (
  <span className={`spinner${large ? ' spinner-lg' : ''} ${className}`} aria-hidden="true" />
);
