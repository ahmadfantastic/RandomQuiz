import React, { useEffect, useMemo, useState } from 'react';
import AppShell from '@/components/layout/AppShell';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import api from '@/lib/api';
import OverviewCards from '@/features/dashboard/components/OverviewCards';
import QuizStatusIcon from '@/components/quiz/QuizStatusIcon';
import { getQuizStatus } from '@/lib/quizStatus';
import { hasAuthFlag } from '@/lib/auth';

const DashboardPage = () => {
  const [quizzes, setQuizzes] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [stats, setStats] = useState(null);

  useEffect(() => {
    if (!hasAuthFlag()) {
      setError('Sign in to view dashboard stats.');
      setIsLoading(false);
      return;
    }
    let isMounted = true;
    api
      .get('/api/dashboard/stats/')
      .then((res) => {
        if (isMounted) {
          const data = res.data || {};
          setStats(data);
          setQuizzes(data.quizzes || []);
          setError('');
        }
      })
      .catch(() => setError('Unable to load dashboard stats right now.'))
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const upcoming = useMemo(() => (stats?.quizzes || quizzes).filter((quiz) => quiz.start_time), [stats, quizzes]);

  return (
    <AppShell
      title="Dashboard"
      description="Monitor your quizzes and track student activity"
    >
      <div className="space-y-6">
        {error && <p className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-2 text-sm text-destructive">{error}</p>}

        <OverviewCards stats={stats} isLoading={isLoading} />

        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Recent Quizzes</CardTitle>
                  <CardDescription>Your latest quizzes and their status</CardDescription>
                </div>
                <Button variant="ghost" size="sm" to="/quizzes">
                  View all
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {isLoading && (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-16 animate-pulse rounded-md bg-muted" />
                  ))}
                </div>
              )}

              {!isLoading && (quizzes || []).length === 0 && (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <p className="text-sm text-muted-foreground">No quizzes yet</p>
                  <Button className="mt-4" size="sm" to="/quizzes/new">
                    Create your first quiz
                  </Button>
                </div>
              )}

              {!isLoading && (quizzes || []).length > 0 && (
                <div className="space-y-3">
                  {(quizzes || []).slice(0, 5).map((quiz) => {
                    const status = getQuizStatus(quiz);
                    return (
                      <div key={quiz.id} className="flex items-center justify-between rounded-lg border p-4 transition-colors hover:bg-muted/50">
                        <div className="flex-1 min-w-0">
                          <a href={`/quizzes/${quiz.id}/edit`} className="font-medium hover:underline">
                            {quiz.title}
                          </a>
                          <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                            {quiz.public_id && (
                              <span className="font-mono">/q/{quiz.public_id}</span>
                            )}
                            {quiz.start_time && (
                              <span>
                                {new Date(quiz.start_time) > new Date() ? 'Starts' : 'Started'}{' '}
                                {new Date(quiz.start_time).toLocaleDateString()}
                              </span>
                            )}
                            {!quiz.public_id && !quiz.start_time && (
                              <span className="text-orange-600">Draft</span>
                            )}
                          </div>
                        </div>
                        <div className="ml-4 flex items-center gap-2">
                          <span
                            className={`flex items-center gap-2 rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-wide ${status.tone}`}
                          >
                            <QuizStatusIcon statusKey={status.key} className="h-3 w-3 text-current" />
                            {status.label}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Top Performers</CardTitle>
                <CardDescription>Most attempted quizzes</CardDescription>
              </CardHeader>
              <CardContent>
                {isLoading && (
                  <div className="space-y-3">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="h-12 animate-pulse rounded-md bg-muted" />
                    ))}
                  </div>
                )}

                {!isLoading && (!stats?.top_quizzes || stats.top_quizzes.length === 0) && (
                  <p className="text-sm text-muted-foreground">No attempts yet</p>
                )}

                {!isLoading && stats?.top_quizzes && stats.top_quizzes.length > 0 && (
                  <div className="space-y-3">
                    {stats.top_quizzes.map((q, idx) => (
                      <div key={q.quiz_id} className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
                          {idx + 1}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="truncate text-sm font-medium">{q.title}</p>
                          <p className="text-xs text-muted-foreground">{q.attempts} attempts</p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {!isLoading && upcoming.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Upcoming</CardTitle>
                  <CardDescription>Scheduled quiz windows</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {upcoming.slice(0, 3).map((quiz) => (
                      <div key={quiz.id} className="rounded-lg border p-3">
                        <p className="text-sm font-medium">{quiz.title}</p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {new Date(quiz.start_time).toLocaleDateString('en-US', {
                            month: 'short',
                            day: 'numeric',
                            hour: 'numeric',
                            minute: '2-digit',
                          })}
                        </p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
};

export default DashboardPage;
