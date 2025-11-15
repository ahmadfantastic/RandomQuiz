import React, { useEffect, useMemo, useState } from 'react';
import AppShell from '@/components/layout/AppShell';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import api from '@/lib/api';
import OverviewCards from '@/features/dashboard/components/OverviewCards';
import QuizList from '@/features/dashboard/components/QuizList';

const DashboardPage = () => {
  const [quizzes, setQuizzes] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let isMounted = true;
    api
      .get('/api/quizzes/')
      .then((res) => {
        if (isMounted) {
          setQuizzes(res.data);
          setError('');
        }
      })
      .catch(() => setError('Unable to load quizzes right now.'))
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const upcoming = useMemo(() => quizzes.filter((quiz) => quiz.start_time), [quizzes]);

  return (
    <AppShell
      title="Instructor dashboard"
      description="Monitor quiz performance, edit schedules, and share access links from one place."
      actions={
        <>
          <Button variant="outline" to="/problem-banks">
            Problem banks
          </Button>
          <Button to="/admin/instructors">Team access</Button>
        </>
      }
    >
      <div className="space-y-10">
        {error && <p className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-2 text-sm text-destructive">{error}</p>}
        <OverviewCards quizzes={quizzes} isLoading={isLoading} />
        <div className="grid gap-6 lg:grid-cols-2">
          <QuizList quizzes={quizzes} isLoading={isLoading} />
          <Card>
            <CardHeader>
              <CardTitle>Upcoming windows</CardTitle>
              <CardDescription>Time frames pulled from your quiz settings.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {isLoading && <div className="h-12 animate-pulse rounded-md bg-muted" />}
              {!isLoading && upcoming.length === 0 && (
                <p className="text-sm text-muted-foreground">You have not scheduled any quizzes yet.</p>
              )}
              {!isLoading &&
                upcoming.slice(0, 4).map((quiz) => (
                  <div key={quiz.id} className="rounded-lg border p-4">
                    <p className="text-base font-semibold">{quiz.title}</p>
                    <p className="text-sm text-muted-foreground">
                      {quiz.start_time ? new Date(quiz.start_time).toLocaleString() : 'No start time'}
                      {quiz.end_time ? ` — ${new Date(quiz.end_time).toLocaleString()}` : ''}
                    </p>
                  </div>
                ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  );
};

export default DashboardPage;
