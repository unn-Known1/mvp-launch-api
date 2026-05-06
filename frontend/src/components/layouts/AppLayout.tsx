import type { ReactNode } from 'react';

interface AppLayoutProps {
  children: ReactNode;
  sidebar?: ReactNode;
  header?: ReactNode;
}

export function AppLayout({ children, sidebar, header }: AppLayoutProps) {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {header && (
        <header className="bg-white border-b border-gray-200 px-6 py-4">
          {header}
        </header>
      )}
      <div className="flex flex-1">
        {sidebar && (
          <aside className="w-64 bg-white border-r border-gray-200 p-4">
            {sidebar}
          </aside>
        )}
        <main className="flex-1 p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
