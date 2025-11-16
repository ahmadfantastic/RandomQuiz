import React, { useState } from 'react';
import Sidebar from './Sidebar';
import { cn } from '@/lib/utils';

const AppShell = ({ title, description, children, actions }) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen bg-muted/20">
      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />
      <div className="flex flex-1 flex-col ml-0 lg:ml-64">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b bg-background px-4 py-4 lg:px-10">
          <div className="flex items-center">
            <button
              className="mr-4 inline-flex h-10 w-10 items-center justify-center rounded-md border lg:hidden"
              onClick={() => setIsSidebarOpen(true)}
              aria-label="Open navigation"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-5 w-5">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h10" />
              </svg>
            </button>
            <div>
              <h1 className="text-xl font-semibold lg:text-2xl">{title}</h1>
              {description && <p className="text-sm text-muted-foreground">{description}</p>}
            </div>
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
        <main className={cn('flex-1 overflow-auto px-4 py-6 lg:px-10', actions ? 'space-y-8' : '')}>{children}</main>
      </div>
    </div>
  );
};

export default AppShell;
