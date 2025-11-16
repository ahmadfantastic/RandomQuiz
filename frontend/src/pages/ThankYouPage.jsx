import React, { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

const ThankYouPage = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const quizTitle = location.state?.quizTitle || 'your quiz';
  const attemptReference = location.state?.attemptReference || 'Unavailable';
  const studentIdentifier = location.state?.studentIdentifier;
  const landingUrl = location.state?.landingUrl;
  const [copyStatus, setCopyStatus] = useState('');

  const referenceLabel = useMemo(() => {
    if (!attemptReference || attemptReference === 'Unavailable') return 'Reference unavailable';
    return `Reference ${attemptReference}`;
  }, [attemptReference]);

  const handleCopyReference = async () => {
    if (!attemptReference || attemptReference === 'Unavailable') return;
    if (typeof navigator === 'undefined' || !navigator.clipboard) {
      setCopyStatus('Copy manually if needed.');
      setTimeout(() => setCopyStatus(''), 2500);
      return;
    }
    try {
      await navigator.clipboard.writeText(attemptReference);
      setCopyStatus('Reference copied to clipboard.');
    } catch (error) {
      setCopyStatus('Unable to copy automatically.');
    } finally {
      setTimeout(() => setCopyStatus(''), 2500);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-primary/5 via-background to-background">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-8 px-4 py-12 sm:px-6 lg:px-8">
        <section className="rounded-3xl bg-primary px-6 py-8 text-primary-foreground shadow-xl">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:gap-6">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary-foreground/20 text-primary-foreground">
              <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div>
              <p className="text-sm uppercase tracking-[0.3em] text-primary-foreground/75">Submission received</p>
              <h1 className="mt-2 text-3xl font-semibold sm:text-4xl">Thank you for finishing {quizTitle}</h1>
              <p className="mt-2 text-base text-primary-foreground/80">
                Your answers are locked in. You will hear from your instructor once grading is complete.
              </p>
            </div>
          </div>
        </section>

        <div className="grid gap-6 md:grid-cols-2">
          <Card className="border-primary/30 shadow-lg">
            <CardHeader>
              <CardTitle>Submission summary</CardTitle>
              <CardDescription>Save this information for your records.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="rounded-2xl border bg-muted/40 p-4">
                <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">Status</p>
                <p className="mt-1 text-lg font-semibold text-foreground">Submitted successfully</p>
                <p className="text-sm text-muted-foreground">{referenceLabel}</p>
              </div>
              {studentIdentifier && (
                <div className="flex items-center justify-between rounded-2xl border px-4 py-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground">Student</p>
                    <p className="text-base font-semibold text-foreground">{studentIdentifier}</p>
                  </div>
                </div>
              )}
              <div className="flex flex-wrap items-center gap-3">
                <Button onClick={handleCopyReference} disabled={!attemptReference || attemptReference === 'Unavailable'}>
                  Copy submission reference
                </Button>
                <Button variant="outline" onClick={() => window.print()}>
                  Download / Print receipt
                </Button>
                {landingUrl ? (
                  <Button variant="ghost" to={landingUrl}>
                    Back to quiz info
                  </Button>
                ) : (
                  <Button variant="ghost" onClick={() => navigate('/', { replace: true })}>
                    Go to home
                  </Button>
                )}
              </div>
              {copyStatus && <p className="text-xs text-muted-foreground">{copyStatus}</p>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>What happens next</CardTitle>
              <CardDescription>Your instructor has everything they need.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-muted-foreground">
              <p>1. Close this window or return to your course dashboard once you are done.</p>
              <p>2. Keep the submission reference above in case you need to confirm your attempt.</p>
              <p>3. If the quiz required uploaded work, follow the instructions you were given.</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default ThankYouPage;
