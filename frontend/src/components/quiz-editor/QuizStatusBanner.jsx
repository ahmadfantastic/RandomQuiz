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
}) => {
  const toneClass = STATUS_CARD_TONES[statusKey] ?? 'border-slate-200 bg-background/80';
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
