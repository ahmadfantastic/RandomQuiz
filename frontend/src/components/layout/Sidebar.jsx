import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { BookOpen, ChevronDown, ListChecks, LogOut, Sparkles, Users, User, Home, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import QuizStatusIcon from '@/components/quiz/QuizStatusIcon';
import { getQuizStatus } from '@/lib/quizStatus';
import api from '@/lib/api';
import { clearAuthFlag, hasAuthFlag } from '@/lib/auth';
import Avatar from '@/components/ui/Avatar';

const navItems = [
  {
    label: 'Dashboard',
    to: '/dashboard',
    icon: <Home className="h-5 w-5" />,
  },
  {
    label: 'Problem Banks',
    to: '/problem-banks',
    icon: <BookOpen className="h-5 w-5" />,
  },
  {
    label: 'Instructors',
    to: '/admin/instructors',
    icon: <Users className="h-5 w-5" />,
  },
  {
    label: 'Global Analysis',
    to: '/analysis/global',
    icon: <Sparkles className="h-5 w-5" />,
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
    is_admin_instructor: false,
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
          is_admin_instructor: res.data.is_admin_instructor || false,
        });
      })
      .catch(() => { });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    const handler = (event) => {
      if (!event?.detail) return;
      setProfile((prev) => ({
        ...prev,
        username: event.detail.username || prev.username,
        email: event.detail.email || prev.email,
        first_name: event.detail.first_name || prev.first_name,
        last_name: event.detail.last_name || prev.last_name,
        profile_picture_url: event.detail.profile_picture_url || prev.profile_picture_url,
      }));
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
                      to={`/quizzes/${quiz.id}/edit`}
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
          <Sparkles className="h-6 w-6 text-primary" />
          <p className="text-lg font-semibold uppercase tracking-[0.3em]">RANDOM Quiz</p>
        </div>
        <button className="rounded-md border p-2 lg:hidden" onClick={onClose} aria-label="Close navigation">
          <span className="sr-only">Close sidebar</span>
          <div className="h-4 w-4">
            <X className="h-full w-full" />
          </div>
        </button>
      </div>
      <nav className="mt-10 flex flex-1 flex-col gap-2">
        {navItems
          .filter((item) => {
            if (item.label === 'Instructors' && !profile.is_admin_instructor) return false;
            return true;
          })
          .map((item) => (
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
              <ListChecks className="h-4 w-4" />
              Quizzes
            </span>
            <ChevronDown
              className={cn(
                'h-4 w-4 transition-transform',
                isQuizMenuOpen ? 'rotate-180' : 'rotate-0'
              )}
            />
          </button>
          <div className="mt-3 space-y-2">{renderQuizMenu()}</div>
        </div>
      </nav>
      <div className="mt-auto space-y-3">
        <div className="rounded-2xl border border-border/80 bg-card/70 p-4 shadow-sm">
          <div className="flex items-center gap-3">
            <Avatar
              size={36}
              name={[profile.first_name, profile.last_name].filter(Boolean).join(' ') || profile.username}
              src={profile.profile_picture_url}
            />
            <div>
              <p className="text-xs uppercase tracking-widest text-muted-foreground">Profile</p>
              <p className="text-sm font-semibold">
                {[profile.first_name, profile.last_name].filter(Boolean).join(' ') || profile.username}
              </p>
              {profile.email && <p className="text-xs text-muted-foreground">{profile.email}</p>}
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="mt-3 w-full justify-start gap-2"
            to="/profile"
            onClick={onClose}
          >
            <User className="h-4 w-4" />
            View profile
          </Button>
        </div>
        <Button
          variant="outline"
          className="w-full flex items-center justify-center gap-2"
          onClick={() => {
            clearAuthFlag();
            window.location.assign('/');
          }}
        >
          <LogOut className="h-4 w-4" />
          Log out
        </Button>
      </div>
    </aside>
  );
};

export default Sidebar;
