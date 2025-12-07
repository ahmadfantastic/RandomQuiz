import React, { useState } from 'react';
import { Menu } from 'lucide-react';
import Sidebar from './Sidebar';
import { cn } from '@/lib/utils';

const AppShell = ({ title, description, children, actions, headerContent }) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen bg-muted/20 print:bg-white print:h-auto">
      <div className="print:hidden">
        <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />
      </div>
      <div className="flex flex-1 flex-col ml-0 lg:ml-64 print:ml-0">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b bg-background px-4 py-4 lg:px-10 print:hidden">
          <div className="flex items-center gap-4 flex-1">
            <div className="flex items-center">
              <button
                className="mr-4 inline-flex h-10 w-10 items-center justify-center rounded-md border lg:hidden"
                onClick={() => setIsSidebarOpen(true)}
                aria-label="Open navigation"
              >
                <Menu className="h-5 w-5" />
              </button>
              <div>
                <h1 className="text-xl font-semibold lg:text-2xl">{title}</h1>
                {description && <p className="text-sm text-muted-foreground">{description}</p>}
              </div>
            </div>
            {headerContent && <div className="flex-1 flex justify-center">{headerContent}</div>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
        <main className={cn('flex-1 overflow-auto px-4 py-6 lg:px-10 print:p-0 print:overflow-visible', actions ? 'space-y-8' : '')}>{children}</main>
      </div>
    </div>
  );
};

export default AppShell;
