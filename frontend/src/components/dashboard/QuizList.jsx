import React from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

const QuizList = ({ quizzes, isLoading }) => {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Recent quizzes</CardTitle>
          <CardDescription>Loading quiz data…</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map((item) => (
              <div key={item} className="h-12 animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!quizzes.length) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Recent quizzes</CardTitle>
          <CardDescription>Quizzes you create will appear here.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">No quizzes yet.</p>
          <Button size="sm" to="/quizzes/new">
            Create a quiz
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent quizzes</CardTitle>
        <CardDescription>Jump back into editing or share the public link.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {quizzes.slice(0, 4).map((quiz) => (
          <div key={quiz.id} className="rounded-lg border p-4">
            <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <Link to={`/quizzes/${quiz.id}/edit`} className="text-base font-semibold hover:underline">
                  {quiz.title}
                </Link>
                <p className="text-sm text-muted-foreground">{quiz.description || 'No description provided'}</p>
              </div>
              <div className="text-sm text-muted-foreground">
                Public link: <span className="font-medium text-foreground">/q/{quiz.public_id}</span>
              </div>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
};

export default QuizList;
