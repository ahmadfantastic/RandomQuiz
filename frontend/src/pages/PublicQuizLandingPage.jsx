import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import api from '@/lib/api';
import { encodeAttemptToken } from '@/lib/attemptToken';
import { renderProblemMarkupHtml } from '@/lib/markdown';

const DEFAULT_IDENTITY_INSTRUCTION = 'Required so your instructor can match your submission.';

const formatDateTime = (value) => {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
};

const getQuizAvailability = (quiz) => {
  if (!quiz) {
    return null;
  }
  if (quiz.is_open) {
    return {
      key: 'open',
      label: 'Open for attempts',
      buttonLabel: 'Start attempt',
      message: '',
      errorMessage: '',
      canAttempt: true,
    };
  }
  const now = Date.now();
  const start = quiz.start_time ? new Date(quiz.start_time).getTime() : null;
  const end = quiz.end_time ? new Date(quiz.end_time).getTime() : null;

  if (end && now > end) {
    const message = 'This quiz window has ended and new attempts are not accepted.';
    return {
      key: 'closed',
      label: 'Closed right now',
      buttonLabel: 'Quiz closed',
      message,
      errorMessage: message,
      canAttempt: false,
    };
  }

  const startMessage = start
    ? `Opens ${formatDateTime(quiz.start_time)}. Check back then for the invitation.`
    : 'The instructor has not opened this quiz yet. Check the window information above.';
  return {
    key: 'not_open',
    label: 'Not open yet',
    buttonLabel: 'Not open yet',
    message: startMessage,
    errorMessage: startMessage,
    canAttempt: false,
  };
};

const PublicQuizLandingPage = () => {
  const { publicId } = useParams();
  const [quiz, setQuiz] = useState(null);
  const [identifier, setIdentifier] = useState('');
  const [identifierError, setIdentifierError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [loadingError, setLoadingError] = useState('');
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState('');
  const navigate = useNavigate();
  const descriptionMarkup = useMemo(() => {
    const text = quiz?.description?.trim();
    return text ? renderProblemMarkupHtml(text) : '';
  }, [quiz?.description]);

  const identityInstructionMarkup = useMemo(() => {
    const text = (quiz?.identity_instruction || DEFAULT_IDENTITY_INSTRUCTION).trim();
    return text ? renderProblemMarkupHtml(text) : '';
  }, [quiz?.identity_instruction]);

  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);
    setLoadingError('');
    api
      .get(`/api/public/quizzes/${publicId}/`)
      .then((res) => {
        if (isMounted) {
          setQuiz(res.data);
          setLoadingError('');
        }
      })
      .catch(() => {
        if (isMounted) {
          setQuiz(null);
          setLoadingError('We were unable to load this quiz. Double-check your link or try again in a moment.');
        }
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [publicId]);

  const quizWindow = useMemo(() => {
    if (!quiz) return 'No schedule shared for this quiz.';
    const start = formatDateTime(quiz.start_time);
    const end = formatDateTime(quiz.end_time);
    if (!start && !end) return 'No schedule shared for this quiz.';
    if (start && !end) return `Opens ${start}`;
    if (!start && end) return `Closes ${end}`;
    return `${start} — ${end}`;
  }, [quiz]);

  const quizAvailability = useMemo(() => getQuizAvailability(quiz), [quiz]);

  const handleStart = async (event) => {
    event.preventDefault();
    const trimmed = identifier.trim();
    if (!trimmed) {
      setIdentifierError('Enter the identifier your instructor requested.');
      return;
    }
    if (!quizAvailability?.canAttempt) {
      setStartError(quizAvailability?.errorMessage || 'This quiz is currently closed.');
      return;
    }
    setIdentifierError('');
    setStartError('');
    setStarting(true);
    try {
      const res = await api.post(`/api/public/quizzes/${publicId}/start/`, { student_identifier: trimmed });
      const attemptToken = encodeAttemptToken(res.data.attempt_id);
      navigate(`/attempts/${attemptToken}`, {
        state: {
          slots: res.data.slots,
          attemptId: res.data.attempt_id,
          quiz,
          quizTitle: quiz?.title,
          studentIdentifier: trimmed,
        },
      });
    } catch (error) {
      if (error?.response?.data?.detail) {
        setStartError(error.response.data.detail);
      } else {
        setStartError('We could not start your attempt. Please try again.');
      }
    } finally {
      setStarting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
        <Card className="w-full max-w-xl">
          <CardHeader>
            <CardTitle>Loading Quiz</CardTitle>
            <CardDescription>Hang tight, we are verifying the quiz link.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-3 w-full animate-pulse rounded-full bg-muted" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (loadingError || !quiz) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/40 px-4 text-center">
        <Card className="w-full max-w-xl">
          <CardHeader>
            <CardTitle>Quiz Unavailable</CardTitle>
            <CardDescription>{loadingError}</CardDescription>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            If this link was provided by your instructor, let them know you are unable to access it.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-primary/10 via-background to-background py-10">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-4 sm:px-6 lg:px-8">
        <header className="rounded-3xl bg-primary px-6 py-8 text-primary-foreground shadow-xl">
          <p className="text-xs uppercase tracking-[0.3em] text-primary-foreground/75">Quiz Invitation</p>
          <h1 className="mt-4 text-3xl font-semibold sm:text-4xl">{quiz.title}</h1>
          <dl className="mt-6 flex flex-wrap gap-6 text-sm text-primary-foreground/80">
            <div>
              <dt className="uppercase tracking-widest text-xs text-primary-foreground/60">Window</dt>
              <dd className="text-base text-primary-foreground">{quizWindow}</dd>
            </div>
            <div>
              <dt className="uppercase tracking-widest text-xs text-primary-foreground/60">Status</dt>
              <dd className="text-base font-semibold">
                {quizAvailability?.label || 'Checking status...'}
              </dd>
            </div>
          </dl>
        </header>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
          <Card className="order-2 border-primary/30 shadow-lg lg:order-1">
            <CardHeader>
              <CardTitle>Instruction</CardTitle>
            </CardHeader>
            <CardContent className="pt-0 space-y-4 text-muted-foreground">
              {descriptionMarkup ? (
                <div
                  className="prose max-w-none text-sm text-muted-foreground markup-content"
                  dangerouslySetInnerHTML={{ __html: descriptionMarkup }}
                />
              ) : (
                <p>{quiz.description}</p>
              )}
            </CardContent>
          </Card>

          <Card className="order-1 shadow-lg lg:order-2">
            <CardHeader>
              <CardTitle>Confirm your Identity</CardTitle>
              <CardDescription className="pt-4 text-sm text-muted-foreground">
                {identityInstructionMarkup ? (
                  <div
                    className="prose max-w-none text-sm text-muted-foreground markup-content"
                    dangerouslySetInnerHTML={{ __html: identityInstructionMarkup }}
                  />
                ) : (
                  DEFAULT_IDENTITY_INSTRUCTION
                )}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form className="space-y-5" onSubmit={handleStart}>
                <div className="space-y-2">
                  <Label htmlFor="identifier">Identifier</Label>
                  <Input
                    id="identifier"
                    placeholder="School email, student ID, etc."
                    value={identifier}
                    onChange={(e) => {
                      setIdentifier(e.target.value);
                      if (identifierError) setIdentifierError('');
                      if (startError) setStartError('');
                    }}
                    disabled={starting}
                  />
                  {identifierError && <p className="text-sm text-destructive">{identifierError}</p>}
                </div>
                {startError && <p className="text-sm text-destructive">{startError}</p>}
                <Button
                  className="w-full text-base font-semibold"
                  size="lg"
                  type="submit"
                  disabled={!quizAvailability?.canAttempt || starting}
                >
                  {starting ? 'Starting attempt...' : quizAvailability?.buttonLabel || 'Start attempt'}
                </Button>
                {quizAvailability && !quizAvailability.canAttempt && quizAvailability.message && (
                  <p className="text-sm text-muted-foreground">{quizAvailability.message}</p>
                )}
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default PublicQuizLandingPage;
