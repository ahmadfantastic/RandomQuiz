import React, { useMemo } from 'react';
import { CheckCircle2, Clock, FileText, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import DateBadge from '@/components/ui/date-badge';

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
              <FileText className="h-8 w-8 text-muted-foreground" />
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
                      <div
                        className={cn(
                          'flex h-10 w-10 items-center justify-center rounded-full',
                          isCompleted ? 'bg-emerald-100 text-emerald-600' : 'bg-slate-100 text-slate-600'
                        )}
                      >
                        {isCompleted ? (
                          <CheckCircle2 className="h-5 w-5" />
                        ) : (
                          <Clock className="h-5 w-5" />
                        )}
                      </div>
                      <div>
                        <p className="font-semibold">{attempt.student_identifier || 'Unknown'}</p>
                        <p className="text-sm text-muted-foreground flex flex-wrap items-center gap-2">
                          <span>Started</span>
                          <DateBadge value={attempt.started_at} fallback="Not available" />
                          {isCompleted && (
                            <>
                              <span className="text-muted-foreground">•</span>
                              <span>Completed</span>
                              <DateBadge value={attempt.completed_at} fallback="Not available" />
                            </>
                          )}
                        </p>
                        <p className="text-sm text-muted-foreground flex flex-wrap items-center gap-2">
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
                        <Trash2 className="h-4 w-4 text-destructive" />
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
