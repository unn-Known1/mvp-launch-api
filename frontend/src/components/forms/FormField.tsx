import type { ReactNode } from 'react';
import * as Label from '@radix-ui/react-label';

interface FormFieldProps {
  label: string;
  htmlFor: string;
  children: ReactNode;
  error?: string;
  required?: boolean;
}

export function FormField({ label, htmlFor, children, error, required }: FormFieldProps) {
  return (
    <div className="space-y-2">
      <Label.Root
        htmlFor={htmlFor}
        className="text-sm font-medium text-gray-700"
      >
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </Label.Root>
      {children}
      {error && (
        <p className="text-sm text-red-500">{error}</p>
      )}
    </div>
  );
}
