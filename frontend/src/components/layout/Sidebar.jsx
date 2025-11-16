import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import QuizStatusIcon from '@/components/quiz/QuizStatusIcon';
import { getQuizStatus } from '@/lib/quizStatus';
import api from '@/lib/api';
import { clearAuthFlag, hasAuthFlag } from '@/lib/auth';
import Avatar from '@/components/ui/Avatar';

const navItems = [
  {
    label: 'Profile',
    to: '/profile',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-5 w-5">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 20c0-3 3.5-5 8-5s8 2 8 5" />
      </svg>
    ),
  },
  {
    label: 'Dashboard',
    to: '/dashboard',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-5 w-5">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 13h4v6H3zM11 9h4v10h-4zM19 5h4v14h-4z" />
      </svg>
    ),
  },
  {
    label: 'Problem Banks',
    to: '/problem-banks',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-5 w-5">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7h16M4 12h16M4 17h16" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 7v10" />
      </svg>
    ),
  },
  {
    label: 'Instructors',
    to: '/admin/instructors',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-5 w-5">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 5.5a3 3 0 0 0-3 3m6 0a3 3 0 0 0-3-3m0 0a3 3 0 0 1 3 3" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 20v-1a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v1" />
      </svg>
    ),
  },
];

const Sidebar = ({ isOpen, onClose }) => {
  const [isQuizMenuOpen, setIsQuizMenuOpen] = useState(true);
  const [profile, setProfile] = useState({
    username: 'Instructor',
    email: '',
    first_name: '',
    last_name: '',
    profile_picture_url: '',
  });
  const [quizzes, setQuizzes] = useState([]);
  const [isLoadingQuizzes, setIsLoadingQuizzes] = useState(true);
  const [quizError, setQuizError] = useState('');

  useEffect(() => {
    let isMounted = true;
    if (!hasAuthFlag()) {
      setIsLoadingQuizzes(false);
      setQuizError('Sign in to view your quizzes.');
      return () => {
        isMounted = false;
      };
    }
    setIsLoadingQuizzes(true);
    api
      .get('/api/quizzes/')
      .then((res) => {
        if (!isMounted) return;
        setQuizzes(res.data);
        setQuizError('');
      })
      .catch(() => {
        if (!isMounted) return;
        setQuizError('Unable to load quizzes.');
      })
      .finally(() => {
        if (isMounted) setIsLoadingQuizzes(false);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!hasAuthFlag()) return;
    let isMounted = true;
    api
      .get('/api/instructors/me/')
      .then((res) => {
        if (!isMounted) return;
        setProfile({
          username: res.data.username || 'Instructor',
          email: res.data.email || '',
          first_name: res.data.first_name || '',
          last_name: res.data.last_name || '',
          profile_picture_url: res.data.profile_picture_url || '',
        });
      })
      .catch(() => {});
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    const handler = (event) => {
      if (!event?.detail) return;
      setProfile({
        username: event.detail.username || 'Instructor',
        email: event.detail.email || '',
        first_name: event.detail.first_name || '',
        last_name: event.detail.last_name || '',
        profile_picture_url: event.detail.profile_picture_url || '',
      });
    };
    window.addEventListener('profileUpdated', handler);
    return () => window.removeEventListener('profileUpdated', handler);
  }, []);

  useEffect(() => {
    const handleStatusChange = (event) => {
      const updatedQuiz = event.detail;
      if (!updatedQuiz?.id) return;
      setQuizzes((prev) =>
        prev.map((quiz) => (quiz.id === updatedQuiz.id ? { ...quiz, ...updatedQuiz } : quiz))
      );
    };
    window.addEventListener('quizStatusChanged', handleStatusChange);
    return () => {
      window.removeEventListener('quizStatusChanged', handleStatusChange);
    };
  }, []);

  const renderQuizMenu = () => {
    if (!isQuizMenuOpen) return null;

    if (isLoadingQuizzes) {
      return <p className="text-xs text-muted-foreground">Loading quizzes…</p>;
    }

    if (quizError) {
      return <p className="text-xs text-destructive">{quizError}</p>;
    }

    const hasQuizzes = quizzes.length > 0;

    return (
      <div className="space-y-3">
        <div className="rounded-2xl border border-border/80 bg-card/70 p-3 shadow-sm">
          <div className="px-1">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Recent quizzes</p>
              <span className="text-xs text-muted-foreground">{quizzes.length} total</span>
            </div>
          </div>
          <div className="mt-3 space-y-2">
            {hasQuizzes ? (
              <div className="space-y-2">
                {quizzes.map((quiz) => {
                  const status = getQuizStatus(quiz);
                  return (
                    <NavLink
                      key={quiz.id}
                      to={`/quizzes/${quiz.id}`}
                      className={({ isActive }) =>
                        cn(
                          'block rounded-xl border border-transparent transition-colors hover:border-primary/70 hover:bg-primary/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
                          isActive
                            ? 'border-primary/80 bg-primary/5 text-foreground'
                            : 'bg-background text-muted-foreground'
                        )
                      }
                      onClick={onClose}
                    >
                      <span
                        className={`flex shrink-0 items-center gap-1 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${status.tone}`}
                      >
                        <QuizStatusIcon statusKey={status.key} className="h-3 w-3 text-current" />
                        {quiz.title}
                      </span>
                    </NavLink>
                  );
                })}
              </div>
            ) : (
              <div className="space-y-3 rounded-xl border border-dashed border-border/60 bg-muted/10 px-4 py-6 text-center text-sm font-semibold text-muted-foreground">
                <p>No quizzes yet.</p>
                <p className="text-xs font-normal text-muted-foreground/70">Start by creating a quiz so instructors can assign it.</p>
                <Button size="sm" variant="outline" to="/quizzes/new" onClick={onClose}>
                  Create quiz
                </Button>
              </div>
            )}
            <div className="mt-3">
                <Button
                  size="sm"
                  variant="ghost"
                  to="/quizzes"
                  className="text-[11px] uppercase tracking-wide text-muted-foreground w-full"
                  onClick={onClose}
                >
                  Show all
                </Button>
              </div>
            </div>
        </div>
        {hasQuizzes && (
          <Button size="sm" variant="outline" to="/quizzes/new" className="w-full" onClick={onClose}>
            + Create quiz
          </Button>
        )}
      </div>
    );
  };

  return (
    <aside
      className={cn(
        'fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r bg-card/95 p-6 shadow-xl backdrop-blur transition-transform',
        isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Avatar
            size={48}
            name={[profile.first_name, profile.last_name].filter(Boolean).join(' ') || profile.username}
            src={profile.profile_picture_url}
          />
          <div>
            <p className="text-xs uppercase tracking-widest text-muted-foreground">Random Quiz</p>
            <p className="text-lg font-semibold">
              {[profile.first_name, profile.last_name].filter(Boolean).join(' ') || profile.username}
            </p>
            {profile.email && <p className="text-xs text-muted-foreground">{profile.email}</p>}
          </div>
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
                'flex items-center rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground hover:bg-muted',
                isActive && 'bg-muted text-foreground'
              )
            }
            onClick={onClose}
          >
            <span className="mr-3 flex h-5 w-5 items-center justify-center text-sm text-muted-foreground">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}

        <div className="mt-4 space-y-2 rounded-2xl border border-border/80 bg-card/70 p-3 shadow-sm">
          <button
            type="button"
            className="flex w-full items-center justify-between text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground"
            onClick={() => setIsQuizMenuOpen((value) => !value)}
            aria-expanded={isQuizMenuOpen}
          >
            <span className="flex items-center gap-2">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-4 w-4">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 10h16M7 14h10" />
              </svg>
              Quizzes
            </span>
            <svg
              viewBox="0 0 20 20"
              fill="none"
              stroke="currentColor"
              className={cn('h-4 w-4 transition-transform', isQuizMenuOpen ? 'rotate-180' : 'rotate-0')}
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M5 8l5 5 5-5" />
            </svg>
          </button>
          <div className="mt-3 space-y-2">{renderQuizMenu()}</div>
        </div>
      </nav>
      <div className="mt-auto">
        <Button
          variant="outline"
          className="w-full"
          onClick={() => {
            clearAuthFlag();
            window.location.assign('/');
          }}
        >
          Log out
        </Button>
      </div>
    </aside>
  );
};

export default Sidebar;
