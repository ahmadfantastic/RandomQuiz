import React, { useCallback, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { previewQuizPdf } from '@/lib/printQuizPdf';

const DEFAULT_IDENTITY_INSTRUCTION = 'Required so your instructor can match your submission.';

const slugify = (value = '') => {
  const text = String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return text || 'quiz-print';
};

const QuizPrintTab = ({ quiz, details = {}, slots = [], rubric = { scale: [], criteria: [] } }) => {
  const [seed, setSeed] = useState(0);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState('');

  const printableFilename = useMemo(() => `${slugify(quiz?.title)}-printable.pdf`, [quiz?.title]);

  const printableSlots = useMemo(() => {
    return (slots || []).map((slot, index) => {
      const problems = Array.isArray(slot.slot_problems) ? slot.slot_problems : [];
      const hasProblems = problems.length > 0;
      const selectedProblem = hasProblems
        ? problems[Math.floor(Math.random() * problems.length)]
        : null;
      return { slot, problem: selectedProblem, index };
    });
  }, [slots, seed]);

  const ratingCriteria = useMemo(() => {
    return Array.isArray(rubric?.criteria) ? rubric.criteria : [];
  }, [rubric?.criteria]);

  const ratingScaleOptions = useMemo(() => {
    return Array.isArray(rubric?.scale) ? rubric.scale : [];
  }, [rubric?.scale]);

  const hasProblemContent = printableSlots.some((entry) => Boolean(entry.problem));
  const canShuffle = (slots || []).length > 0;

  const handleShuffle = () => setSeed((value) => value + 1);

  const getMissingFields = useCallback(() => {
    const missing = [];
    if (!details?.description?.trim()) {
      missing.push('quiz description');
    }
    if (!details?.identity_instruction?.trim()) {
      missing.push('identity instruction');
    }
    printableSlots.forEach(({ slot }) => {
      if (!slot?.instruction?.trim()) {
        missing.push(slot?.label ? `"${slot.label}" instruction` : 'a slot instruction');
      }
    });
    return missing;
  }, [details, printableSlots]);

  const handleDownloadPdf = useCallback(() => {
    if (!canShuffle) {
      return;
    }
    setDownloadError('');
    setIsDownloading(true);
    const missingFields = getMissingFields();
    if (missingFields.length) {
      setDownloadError(`Fill the ${missingFields.join(', ')} before printing.`);
      setIsDownloading(false);
      return;
    }
    previewQuizPdf({
      printableFilename,
      quiz,
      details,
      printableSlots,
      ratingCriteria,
      ratingScaleOptions,
    })
      .then(() => setIsDownloading(false))
      .catch((error) => {
        console.error('PDF generation failed', error);
        setDownloadError('Unable to generate the printable PDF right now.');
        setIsDownloading(false);
      });
  }, [
    printableFilename,
    canShuffle,
    details,
    printableSlots,
    quiz,
    ratingCriteria,
    ratingScaleOptions,
  ]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">Printable quiz</p>
          <p className="text-sm text-muted-foreground">
            Generate a randomized version of the quiz that students can write on.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={handleShuffle} disabled={!canShuffle}>
            Shuffle problems
          </Button>
          <Button
            onClick={handleDownloadPdf}
            disabled={!hasProblemContent || isDownloading}
          >
            {isDownloading ? 'Generating PDF…' : 'Download PDF'}
          </Button>
        </div>
      </div>
      {(!hasProblemContent || !canShuffle) && (
        <Card className="border border-muted/40 bg-muted/10">
          <CardHeader>
            <CardTitle className="text-sm">Slots need problems</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            Add at least one problem to a slot before downloading the printable quiz.
          </CardContent>
        </Card>
      )}
      {downloadError && <p className="text-sm text-destructive">{downloadError}</p>}

      <div className="rounded-2xl border border-muted/40 bg-white p-8 text-sm shadow-sm space-y-4">
        <h3 className="text-lg font-semibold">Selected problems</h3>
        <div className="mt-4 space-y-3">
          {printableSlots.map(({ slot, problem, index }) => (
            <div key={slot?.id ?? index} className="flex items-center justify-between gap-3 rounded-lg border border-muted/30 px-3 py-2">
              <div>
                <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">
                  Slot {slot?.order || index + 1}
                </p>
                <p className="text-sm font-semibold text-foreground">
                  {slot?.label || 'Untitled Slot'}
                </p>
                <p className="text-xs text-muted-foreground">
                  {problem?.display_label || 'No problem selected'}
                </p>
              </div>
              <span className="rounded-full border px-3 py-1 text-xs text-muted-foreground">
                {slot?.response_type === 'rating' ? 'Rating' : 'Open response'}
              </span>
            </div>
          ))}
        </div>
        <div className="rounded-lg border border-muted/30 px-3 py-2">
          <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">Student identifier</p>
          <div className="h-10 rounded-md border border-muted/40 bg-muted/10" />
          <p className="text-xs text-muted-foreground mt-2">
            Write the identifier students will use.
          </p>
        </div>
      </div>
    </div>
  );
};

export default QuizPrintTab;
