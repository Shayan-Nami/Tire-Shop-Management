import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';

interface ErrorFallbackProps {
  onRetry: () => void;
}

const ErrorFallback: React.FC<ErrorFallbackProps> = ({ onRetry }) => {
  const { t } = useLanguage();

  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center min-h-[60vh] p-6 text-center space-y-4"
    >
      <div className="w-12 h-12 rounded-2xl bg-rose-500/10 text-rose-600 dark:text-rose-400 flex items-center justify-center">
        <AlertTriangle className="w-6 h-6" />
      </div>
      <div className="space-y-1 max-w-md">
        <h2 className="text-base font-bold text-slate-900 dark:text-white">
          {t("خطایی در بارگذاری صفحه رخ داد")}
        </h2>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {t("لطفاً دوباره تلاش کنید یا صفحه را تازه‌سازی نمایید.")}
        </p>
      </div>
      <button
        type="button"
        onClick={onRetry}
        className="action-primary inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold rounded-xl shadow-sm transition-colors"
      >
        <RefreshCw className="w-4 h-4" />
        <span>{t("تلاش مجدد")}</span>
      </button>
    </div>
  );
};

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error('ErrorBoundary caught an error:', error, info);
  }

  handleRetry = (): void => {
    this.setState({ hasError: false });
  };

  render(): React.ReactNode {
    if (this.state.hasError) {
      return <ErrorFallback onRetry={this.handleRetry} />;
    }
    return this.props.children;
  }
}
