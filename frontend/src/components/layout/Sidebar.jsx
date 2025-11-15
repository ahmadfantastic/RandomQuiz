import React from 'react';
import { NavLink } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

const navItems = [
  { label: 'Dashboard', to: '/dashboard' },
  { label: 'Problem Banks', to: '/problem-banks' },
  { label: 'Admin Instructors', to: '/admin/instructors' },
];

const Sidebar = ({ isOpen, onClose }) => {
  return (
    <aside
      className={cn(
        'fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r bg-card/95 p-6 shadow-xl backdrop-blur transition-transform lg:static lg:translate-x-0',
        isOpen ? 'translate-x-0' : '-translate-x-full'
      )}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-widest text-muted-foreground">Random Quiz</p>
          <p className="text-lg font-semibold">Instructor</p>
        </div>
        <button className="rounded-md border p-2 lg:hidden" onClick={onClose} aria-label="Close navigation">
          <span className="sr-only">Close sidebar</span>
          <div className="h-4 w-4">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" className="h-full w-full">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 6l8 8M6 14L14 6" />
            </svg>
          </div>
        </button>
      </div>
      <nav className="mt-10 flex flex-1 flex-col gap-2">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                'rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground hover:bg-muted',
                isActive && 'bg-muted text-foreground'
              )
            }
            onClick={onClose}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto">
        <Button variant="outline" className="w-full" onClick={() => window.location.assign('/')}>
          Log out
        </Button>
      </div>
    </aside>
  );
};

export default Sidebar;
