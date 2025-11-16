import React, { useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

const formatDateTime = (value) => {
  if (!value) return 'Not scheduled';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Not scheduled';
  return date.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
};

const QuizResponsesTab = ({
  attempts,
  attemptError,
  loadAttempts,
  openAttemptModal,
  requestAttemptDeletion,
}) => {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Student Responses</h3>
          <p className="text-sm text-muted-foreground">
            View and manage all student attempts
          </p>
        </div>
        <Button variant="outline" onClick={loadAttempts}>Refresh</Button>
      </div>

      {attemptError && (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="py-3 text-sm text-destructive">{attemptError}</CardContent>
        </Card>
      )}

      {!attempts.length ? (
        <Card>
          <CardContent className="py-12 text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted">
              <svg className="h-8 w-8 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <p className="text-lg font-semibold">No responses yet</p>
            <p className="text-sm text-muted-foreground">Responses will appear here once students start the quiz</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {attempts.map((attempt) => {
            const isCompleted = Boolean(attempt.completed_at);
            const answerCount = attempt.attempt_slots?.length || 0;
            return (
              <Card key={attempt.id} className="hover:shadow-md transition-shadow">
                <CardContent className="p-2">
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-4">
                      <div className={cn(
                        'flex h-10 w-10 items-center justify-center rounded-full',
                        isCompleted ? 'bg-emerald-100 text-emerald-600' : 'bg-slate-100 text-slate-600'
                      )}>
                        {isCompleted ? (
                          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        ) : (
                          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                        )}
                      </div>
                      <div>
                        <p className="font-semibold">{attempt.student_identifier || 'Unknown'}</p>
                        <p className="text-sm text-muted-foreground">
                          Started {formatDateTime(attempt.started_at)}
                          {isCompleted && ` • Completed ${formatDateTime(attempt.completed_at)}`}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-muted-foreground">{answerCount} answers</span>
                      <Button size="sm" onClick={() => openAttemptModal(attempt)}>
                        View
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => requestAttemptDeletion(attempt)}
                      >
                        <svg className="h-4 w-4 text-destructive" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default QuizResponsesTab;
