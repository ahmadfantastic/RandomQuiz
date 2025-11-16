import React from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

const QuizOverviewTab = ({
  quiz,
  details,
  onDetailChange,
  onSaveDetails,
  detailsSaving,
  detailsError,
  quizLink,
  handleCopyLink,
  copyMessage,
  readyForStudents,
  scheduleState,
  onOpenQuiz,
  onCloseQuiz,
  scheduleActionLoading,
  scheduleActionError,
}) => {
  const isOpen = scheduleState?.isOpen;
  const handleToggle = () => {
    if (scheduleActionLoading || (!isOpen && !readyForStudents)) return;
    if (isOpen) {
      onCloseQuiz();
    } else {
      onOpenQuiz();
    }
  };
  const switchClasses = cn(
    'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
    isOpen ? 'bg-primary' : 'bg-muted'
  );
  const knobClasses = cn(
    'inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform',
    isOpen ? 'translate-x-5' : 'translate-x-1'
  );
  const startLabel = scheduleState?.startLabel || 'Not opened yet';
  const endLabel = scheduleState?.endLabel || 'Not closed yet';

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Quiz Details</CardTitle>
          <CardDescription>Basic information displayed to students and instructors</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={onSaveDetails}>
            <div className="space-y-2">
              <Label htmlFor="quiz-title">Title</Label>
              <Input
                id="quiz-title"
                name="title"
                value={details.title}
                onChange={onDetailChange}
                maxLength={120}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="quiz-description">Description</Label>
              <Textarea
                id="quiz-description"
                name="description"
                value={details.description}
                onChange={onDetailChange}
                rows={3}
                maxLength={500}
              />
            </div>
            {detailsError && <p className="text-sm text-destructive">{detailsError}</p>}
            <Button type="submit" disabled={detailsSaving} className="w-full">
              {detailsSaving ? 'Saving...' : 'Save Changes'}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Schedule</CardTitle>
          <CardDescription>Control when students can access this quiz</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between gap-3 rounded-lg border border-border/80 bg-background/70 p-3">
            <div>
              <p className="text-sm font-medium">Quiz access</p>
              <p className="text-xs text-muted-foreground">
                {isOpen ? 'Students can start attempts right now.' : 'New attempts are paused while the quiz is closed.'}
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={isOpen}
              onClick={handleToggle}
              className={switchClasses}
              disabled={scheduleActionLoading || (!isOpen && !readyForStudents)}
            >
              <span className={knobClasses} />
            </button>
          </div>
          {!readyForStudents && !isOpen && (
            <p className="text-xs text-destructive">
              At least one slot with a linked bank and problems is required before publishing.
            </p>
          )}
          <div className="text-sm text-muted-foreground space-y-1">
            <p>Last opened: {startLabel}</p>
            <p>Last closed: {endLabel}</p>
            {scheduleActionLoading && <p className="text-xs text-muted-foreground">Updating status…</p>}
          </div>
          {scheduleActionError && (
            <p className="text-sm text-destructive">{scheduleActionError}</p>
          )}
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Public Access Link</CardTitle>
          <CardDescription>Share this link with students to start collecting responses</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <Input value={quizLink} readOnly className="font-mono text-sm" />
            <Button onClick={handleCopyLink}>Copy</Button>
            <Button variant="outline" to={quizLink} target="_blank" rel="noreferrer">
              Open
            </Button>
          </div>
          {!readyForStudents && (
            <p className="mt-3 text-sm text-amber-600">
              ⚠️ Configure at least one slot with problems before sharing
            </p>
          )}
          {copyMessage && <p className="mt-2 text-xs text-muted-foreground">{copyMessage}</p>}
        </CardContent>
      </Card>
    </div>
  );
};

export default QuizOverviewTab;
