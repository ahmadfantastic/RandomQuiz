import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import MDEditor from '@uiw/react-md-editor';
import '@uiw/react-markdown-preview/markdown.css';
import '@uiw/react-md-editor/markdown-editor.css';
import { Modal } from '@/components/ui/modal';
import QRCode from 'qrcode';
const LinkIcon = ({ className, ...props }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.7"
    className={cn('h-4 w-4 flex-shrink-0', className)}
    {...props}
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 17H6a5 5 0 0 1 0-10h3" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 7h3a5 5 0 0 1 0 10h-3" />
    <path strokeLinecap="round" strokeLinejoin="round" d="m8.5 11.5 7 7" />
  </svg>
);

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
  const handleDescriptionChange = (value) => {
    onDetailChange({ target: { name: 'description', value: value ?? '' } });
  };

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
  const [qrModalOpen, setQrModalOpen] = useState(false);
  const [qrDataUrl, setQrDataUrl] = useState('');
  const [qrLoading, setQrLoading] = useState(false);
  const [qrError, setQrError] = useState('');
  const absoluteQuizLink = useMemo(() => {
    if (!quiz?.public_id) return '';
    if (typeof window === 'undefined') return '';
    return `${window.location.origin}/q/${quiz.public_id}`;
  }, [quiz?.public_id]);
  const qrSourceLink = useMemo(() => {
    if (absoluteQuizLink) return absoluteQuizLink;
    if (typeof window === 'undefined' || !quizLink) return '';
    return `${window.location.origin}${quizLink}`;
  }, [absoluteQuizLink, quizLink]);
  const displayQuizLink = absoluteQuizLink || quizLink || '';
  const qrFileName = useMemo(() => {
    const title = (quiz?.title || 'quiz link').trim();
    const slug = title
      ? title
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '-')
          .replace(/^-+|-+$/g, '')
      : 'quiz-link';
    return `${slug || 'quiz-link'}-qr.png`;
  }, [quiz?.title]);
  useEffect(() => {
    setQrDataUrl('');
    setQrError('');
  }, [qrSourceLink]);
  const generateQrDataUrl = useCallback(async () => {
    if (!qrSourceLink) {
      return null;
    }
    if (qrDataUrl) {
      return qrDataUrl;
    }
    setQrError('');
    setQrLoading(true);
    try {
      const dataUrl = await QRCode.toDataURL(qrSourceLink, { width: 320, margin: 2 });
      setQrDataUrl(dataUrl);
      return dataUrl;
    } catch (error) {
      console.error('QR generation failed', error);
      setQrError('Unable to generate the QR code right now.');
      return null;
    } finally {
      setQrLoading(false);
    }
  }, [qrDataUrl, qrSourceLink]);
  const handleViewQr = useCallback(async () => {
    const dataUrl = await generateQrDataUrl();
    if (dataUrl) {
      setQrModalOpen(true);
    }
  }, [generateQrDataUrl]);
  const handleDownloadQr = useCallback(async () => {
    const dataUrl = await generateQrDataUrl();
    if (!dataUrl || typeof document === 'undefined') {
      return;
    }
    const link = document.createElement('a');
    link.href = dataUrl;
    link.download = qrFileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, [generateQrDataUrl, qrFileName]);

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
              <MDEditor
                value={details.description ?? ''}
                onChange={(value) => handleDescriptionChange(value)}
                height={200}
                preview="edit"
                textareaProps={{
                  id: 'quiz-description',
                  name: 'description',
                }}
              />
              <p className="text-xs text-muted-foreground">
                Use Markdown to format the quiz description; preview shows how it renders.
              </p>
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
          <div className="space-y-3">
            <div className="flex items-start gap-2 text-blue-600">
              <LinkIcon className="text-blue-600" aria-hidden />
              {displayQuizLink ? (
                <a
                  href={absoluteQuizLink || quizLink}
                  target="_blank"
                  rel="noreferrer"
                  className="break-words text-sm font-semibold text-blue-600 transition hover:text-blue-700"
                >
                  {displayQuizLink}
                </a>
              ) : (
                <span className="text-sm text-muted-foreground">
                  Configure the quiz before sharing the public link.
                </span>
              )}
            </div>
            <div className="flex flex-wrap gap-3">
              <Button onClick={handleCopyLink} disabled={!quiz}>
                Copy
              </Button>
              <Button variant="outline" to={quizLink} target="_blank" rel="noreferrer" disabled={!quizLink}>
                Open
              </Button>
              <Button
                size="sm"
                onClick={handleViewQr}
                variant="ghost"
                disabled={!qrSourceLink || qrLoading}
              >
                {qrLoading ? 'Generating QR…' : 'View QR'}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={handleDownloadQr}
                disabled={!qrSourceLink || qrLoading}
              >
                Download QR
              </Button>
            </div>
            {qrError && <p className="text-xs text-destructive">{qrError}</p>}
          </div>
          {!readyForStudents && (
            <p className="mt-3 text-sm text-amber-600">
              ⚠️ Configure at least one slot with problems before sharing
            </p>
          )}
          {copyMessage && <p className="mt-2 text-xs text-muted-foreground">{copyMessage}</p>}
        </CardContent>
      </Card>
      <Modal
        open={qrModalOpen}
        onOpenChange={setQrModalOpen}
        title="Quiz link QR code"
        description="Scan this code to open the quiz invitation."
      >
        <div className="flex flex-col items-center justify-center gap-4">
          {qrLoading && !qrDataUrl ? (
            <p className="text-sm text-muted-foreground">Generating the QR code…</p>
          ) : qrDataUrl ? (
            <img
              src={qrDataUrl}
              alt="Quiz link QR code"
              className="h-64 w-64 rounded-2xl border border-border object-contain"
            />
          ) : (
            <p className="text-sm text-muted-foreground">Unable to render the QR code right now.</p>
          )}
          <div className="flex flex-wrap justify-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownloadQr}
              disabled={!qrDataUrl || qrLoading}
            >
              Download PNG
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setQrModalOpen(false)}>
              Close
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default QuizOverviewTab;
