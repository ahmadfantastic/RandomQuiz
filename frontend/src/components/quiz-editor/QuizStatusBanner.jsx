import React from 'react';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

const STATUS_CARD_TONES = {
  draft: 'border-orange-300 bg-orange-50',
  published: 'border-emerald-300 bg-emerald-50',
  closed: 'border-sky-300 bg-sky-50',
};

const QuizStatusBanner = ({
  readyForStudents,
  schedulePreview,
  slotReadiness,
  attemptsSummary,
  handleCopyLink,
  copyMessage,
  statusKey,
  compact = false,
  customAction,
}) => {
  const toneClass = STATUS_CARD_TONES[statusKey] ?? 'border-slate-200 bg-background/80';

  if (compact) {
    return (
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              'flex h-8 w-8 items-center justify-center rounded-full',
              readyForStudents ? 'bg-emerald-500/20' : 'bg-amber-500/20'
            )}
          >
            {readyForStudents ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            ) : (
              <AlertTriangle className="h-4 w-4 text-amber-600" />
            )}
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-semibold leading-none">{schedulePreview.status}</span>
            <span className="text-[10px] text-muted-foreground">{schedulePreview.description}</span>
          </div>
        </div>

        <div className="h-8 w-px bg-border" />

        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold leading-none">{slotReadiness.ready}/{slotReadiness.total}</span>
            <span className="text-xs text-muted-foreground">Slots ready</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold leading-none">{attemptsSummary.completed}/{attemptsSummary.total}</span>
            <span className="text-xs text-muted-foreground">Completed</span>
          </div>
        </div>

        <div className="h-8 w-px bg-border" />

        <div className="flex items-center gap-2">
          {customAction ? (
            customAction
          ) : (
            <>
              <Button onClick={handleCopyLink} size="sm" variant="outline" className="h-8">
                Copy Link
              </Button>
              {copyMessage && <span className="text-xs text-muted-foreground animate-fade-in">{copyMessage}</span>}
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <Card className={cn('border-2', toneClass)}>
      <CardContent className="py-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div
              className={cn(
                'flex h-12 w-12 items-center justify-center rounded-full',
                readyForStudents ? 'bg-emerald-500/20' : 'bg-amber-500/20'
              )}
            >
              {readyForStudents ? (
                <CheckCircle2 className="h-6 w-6 text-emerald-600" />
              ) : (
                <AlertTriangle className="h-6 w-6 text-amber-600" />
              )}
            </div>
            <div>
              <p className="text-lg font-semibold">{schedulePreview.status}</p>
              <p className="text-sm text-muted-foreground">{schedulePreview.description}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-2xl font-bold">{slotReadiness.ready}/{slotReadiness.total}</p>
              <p className="text-xs text-muted-foreground">Slots ready</p>
            </div>
            <div className="text-right">
              <p className="text-2xl font-bold">{attemptsSummary.completed}/{attemptsSummary.total}</p>
              <p className="text-xs text-muted-foreground">Completed</p>
            </div>
            <Button onClick={handleCopyLink}>Copy Link</Button>
          </div>
        </div>
        {copyMessage && <p className="mt-2 text-xs text-muted-foreground">{copyMessage}</p>}
      </CardContent>
    </Card>
  );
};

export default QuizStatusBanner;
