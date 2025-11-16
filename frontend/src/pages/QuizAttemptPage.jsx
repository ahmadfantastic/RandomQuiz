import React, { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import api from '@/lib/api';
import { cn } from '@/lib/utils';
import { decodeAttemptToken } from '@/lib/attemptToken';
import { useResponseConfig } from '@/lib/useResponseConfig';
import LikertRating from '@/components/quiz-attempt/LikertRating';
import { marked } from 'marked';
import DOMPurify from 'dompurify';

const RESPONSE_TYPES = {
  OPEN_TEXT: 'open_text',
  RATING: 'rating',
};

const QUIZ_CLOSED_MESSAGE = 'This quiz window has closed and new answers are no longer accepted.';
const QUIZ_CLOSED_PREFIX = 'This quiz window has closed';

marked.setOptions({ mangle: false });

const renderProblemMarkupHtml = (statement) => {
  if (!statement) {
    return '';
  }
  return DOMPurify.sanitize(marked.parse(statement));
};

const createEmptyAnswer = (slot) => {
  if (slot?.response_type === RESPONSE_TYPES.RATING) {
    return { response_type: RESPONSE_TYPES.RATING, ratings: {} };
  }
  return { response_type: RESPONSE_TYPES.OPEN_TEXT, text: '' };
};

const normalizeSlotAnswer = (slot, rawAnswer) => {
  if (slot?.response_type === RESPONSE_TYPES.RATING) {
    if (rawAnswer && typeof rawAnswer === 'object' && rawAnswer.ratings && typeof rawAnswer.ratings === 'object') {
      return { response_type: RESPONSE_TYPES.RATING, ratings: { ...rawAnswer.ratings } };
    }
    return createEmptyAnswer(slot);
  }
  if (rawAnswer && typeof rawAnswer === 'object' && typeof rawAnswer.text === 'string') {
    return { response_type: RESPONSE_TYPES.OPEN_TEXT, text: rawAnswer.text };
  }
  if (typeof rawAnswer === 'string') {
    return { response_type: RESPONSE_TYPES.OPEN_TEXT, text: rawAnswer };
  }
  return createEmptyAnswer(slot);
};

const buildAnswerMap = (slotList = []) =>
  slotList.reduce((acc, slot) => {
    acc[slot.slot] = normalizeSlotAnswer(slot, slot.answer_data);
    return acc;
  }, {});

const getRatingCriteriaCount = (config) => {
  return Array.isArray(config?.criteria) ? config.criteria.length : 0;
};

const isAnswerComplete = (slot, answer, ratingCriteriaCount) => {
  if (slot.response_type === RESPONSE_TYPES.RATING) {
    const ratings = answer?.ratings || {};
    const ratedCount = Object.keys(ratings).length;
    if (ratingCriteriaCount > 0) {
      return ratedCount === ratingCriteriaCount;
    }
    return ratedCount > 0;
  }
  return Boolean((answer?.text || '').trim());
};

const hasAnyInput = (slot, answer) => {
  if (slot.response_type === RESPONSE_TYPES.RATING) {
    return Object.keys(answer?.ratings || {}).length > 0;
  }
  return Boolean((answer?.text || '').trim());
};

const QuizAttemptPage = () => {
  const { attemptToken } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const locationAttemptId = location.state?.attemptId;
  const initialSlots = location.state?.slots || [];
  const initialQuizInfo = location.state?.quiz || null;
  const quizTitle = location.state?.quizTitle || initialQuizInfo?.title || 'Quiz attempt';
  const initialStudentIdentifier = location.state?.studentIdentifier;
  const attemptId = useMemo(() => decodeAttemptToken(attemptToken) || locationAttemptId || null, [attemptToken, locationAttemptId]);
  const attemptReference = useMemo(() => {
    if (!attemptToken) return 'Not available';
    const cleaned = attemptToken.replace(/=+$/, '');
    if (!cleaned) return 'Not available';
    return cleaned.slice(-8).toUpperCase();
  }, [attemptToken]);
  const hasAttemptReference = attemptReference !== 'Not available';

  const { config: responseConfig, error: responseConfigError, isLoading: isConfigLoading } = useResponseConfig();
  const ratingCriteriaCount = getRatingCriteriaCount(responseConfig);

  const [slots, setSlots] = useState(initialSlots);
  const [resolvedStudentIdentifier, setResolvedStudentIdentifier] = useState(initialStudentIdentifier);
  const [quizInfo, setQuizInfo] = useState(initialQuizInfo);
  const [answers, setAnswers] = useState(buildAnswerMap(initialSlots));
  const quizDescription = quizInfo?.description?.trim();
  const quizDescriptionMarkup = quizDescription ? renderProblemMarkupHtml(quizDescription) : '';
  const [banner, setBanner] = useState(null);
  const [savingState, setSavingState] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [showValidation, setShowValidation] = useState(false);
  const [attemptLoading, setAttemptLoading] = useState(false);
  const [attemptLoadError, setAttemptLoadError] = useState('');
  const [attemptCompleted, setAttemptCompleted] = useState(false);
  const [quizOpen, setQuizOpen] = useState(true);
  const [quizClosedMessage, setQuizClosedMessage] = useState('');

  useEffect(() => {
    if (Array.isArray(location.state?.slots) && location.state.slots.length) {
      setSlots(location.state.slots);
    }
  }, [location.state]);

  useEffect(() => {
    setAnswers(buildAnswerMap(slots));
    setSavingState(() => {
      const initialState = {};
      slots.forEach((slot) => {
        const normalized = normalizeSlotAnswer(slot, slot.answer_data);
        if (hasAnyInput(slot, normalized)) {
          initialState[slot.slot] = 'saved';
        }
      });
      return initialState;
    });
  }, [slots]);

  useEffect(() => {
    if (!attemptId) return undefined;
    let isActive = true;
    setAttemptLoading(true);
    setAttemptLoadError('');
    setAttemptCompleted(false);
    api
      .get(`/api/public/attempts/${attemptId}/`)
    .then((response) => {
      if (!isActive) return;
      const attempt = response.data;
      setAttemptCompleted(Boolean(attempt.completed_at));
      const attemptQuizIsOpen = attempt.quiz_is_open ?? true;
      setQuizOpen(attemptQuizIsOpen);
      if (attemptQuizIsOpen) {
        setQuizClosedMessage('');
      } else {
        setQuizClosedMessage(QUIZ_CLOSED_MESSAGE);
        setBanner({ type: 'error', message: QUIZ_CLOSED_MESSAGE });
      }
      setSlots(attempt.attempt_slots || []);
      setResolvedStudentIdentifier((current) => current || attempt.student_identifier);
      setQuizInfo(attempt.quiz || initialQuizInfo);
    })
      .catch((error) => {
        if (!isActive) return;
        const detail = error.response?.data?.detail;
        setAttemptLoadError(
          detail || 'We could not load this attempt. Please confirm the link and try again.'
        );
      })
      .finally(() => {
        if (isActive) {
          setAttemptLoading(false);
        }
      });
    return () => {
      isActive = false;
    };
  }, [attemptId]);

  const setSlotSaveState = (slotId, state) => {
    setSavingState((prev) => {
      const next = { ...prev };
      if (!state) {
        delete next[slotId];
      } else {
        next[slotId] = state;
      }
      return next;
    });
  };

  const answeredCount = useMemo(
    () =>
      slots.filter((slot) => {
        const answer = answers[slot.slot];
        return isAnswerComplete(slot, answer, ratingCriteriaCount);
      }).length,
    [slots, answers, ratingCriteriaCount]
  );
  const totalCount = slots.length;
  const progressPercent = totalCount === 0 ? 0 : Math.round((answeredCount / totalCount) * 100);
  const allAnswered = totalCount > 0 && answeredCount === totalCount;

  const handleAnswerChange = (slot, value) => {
    setAnswers((prev) => ({ ...prev, [slot.slot]: value }));
    setSlotSaveState(slot.slot, hasAnyInput(slot, value) ? 'dirty' : null);
  };

  const handleSave = async (slot) => {
    if (!quizOpen) {
      setBanner({
        type: 'error',
        message: quizClosedMessage || QUIZ_CLOSED_MESSAGE,
      });
      return;
    }
    const slotId = slot.slot;
    const slotLabel = slot.slot_label;
    const answer = answers[slotId];
    if (!isAnswerComplete(slot, answer, ratingCriteriaCount)) {
      setBanner({ type: 'error', message: `Please complete the response for ${slotLabel} before saving.` });
      setShowValidation(true);
      return;
    }
    setSlotSaveState(slotId, 'saving');
    try {
      await api.post(`/api/public/attempts/${attemptId}/slots/${slotId}/answer/`, { answer_data: answer });
      setSlotSaveState(slotId, 'saved');
      setBanner({ type: 'success', message: `${slotLabel} saved successfully.` });
    } catch (error) {
      setSlotSaveState(slotId, 'error');
      const detail = error.response?.data?.detail;
      if (detail?.startsWith(QUIZ_CLOSED_PREFIX)) {
        setQuizOpen(false);
        setQuizClosedMessage(detail);
      }
      const message = detail || `Unable to save ${slotLabel}. Please try again.`;
      setBanner({ type: 'error', message });
    }
  };

  const handleComplete = async () => {
    if (!quizOpen) {
      setBanner({
        type: 'error',
        message: quizClosedMessage || QUIZ_CLOSED_MESSAGE,
      });
      return;
    }
    setShowValidation(true);
    if (!allAnswered) {
      setBanner({ type: 'error', message: 'Answer every question before submitting the quiz.' });
      return;
    }
    setSubmitting(true);
    try {
      const payloadSlots = slots.map((slot) => ({
        slot_id: slot.slot,
        answer_data: answers[slot.slot] || createEmptyAnswer(slot),
      }));
      await api.post(`/api/public/attempts/${attemptId}/complete/`, { slots: payloadSlots });
      navigate('/thank-you', { state: { quizTitle, attemptReference, studentIdentifier: resolvedStudentIdentifier } });
    } catch (error) {
      const detail = error.response?.data?.detail;
      if (detail?.startsWith(QUIZ_CLOSED_PREFIX)) {
        setQuizOpen(false);
        setQuizClosedMessage(detail);
      }
      const message =
        detail ||
        'We were unable to submit your quiz. Your answers are safe - please try again.';
      setBanner({
        type: 'error',
        message,
      });
    } finally {
      setSubmitting(false);
    }
  };

  const loadingAttempt = attemptLoading && !slots.length;

  if (!attemptId) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
        <Card className="w-full max-w-xl text-center">
          <CardHeader>
            <CardTitle>We could not verify your attempt</CardTitle>
            <CardDescription>
              The link you used is missing the data we need to load your quiz. Please return to the invitation page and start
              again.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Button onClick={() => navigate(-1)} variant="outline">
              Go back
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (attemptLoadError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
        <Card className="w-full max-w-xl text-center">
          <CardHeader>
            <CardTitle>We could not load your attempt</CardTitle>
            <CardDescription>{attemptLoadError}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Button onClick={() => navigate(-1)} variant="outline">
              Go back
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (attemptCompleted) {
    return (
      <div className="min-h-screen bg-muted/5 px-4 py-10">
        <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
          <Card className="text-center">
            <CardHeader>
              <CardTitle>Attempt already submitted</CardTitle>
              <CardDescription>Thanks for finishing {quizTitle}. Your answers are locked in.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm text-muted-foreground">
              <p>{hasAttemptReference ? `Reference ${attemptReference}` : 'Reference unavailable'}</p>
              {resolvedStudentIdentifier && <p>Student {resolvedStudentIdentifier}</p>}
              <div className="flex flex-wrap items-center justify-center gap-3">
                <Button
                  onClick={() =>
                    navigate('/thank-you', {
                      state: { quizTitle, attemptReference, studentIdentifier: resolvedStudentIdentifier },
                    })
                  }
                  disabled={!hasAttemptReference}
                >
                  View submission receipt
                </Button>
                <Button variant="outline" onClick={() => navigate('/', { replace: true })}>
                  Back to home
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                If you need proof of your submission, use the receipt above or contact your instructor.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (loadingAttempt) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
        <Card className="w-full max-w-xl text-center">
          <CardHeader>
            <CardTitle>Loading your attempt</CardTitle>
            <CardDescription>Please wait while we fetch your problems.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-3 w-full animate-pulse rounded-full bg-muted" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!slots.length) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
        <Card className="w-full max-w-xl text-center">
          <CardHeader>
            <CardTitle>We could not load your quiz</CardTitle>
            <CardDescription>
              Use the quiz link you received to start a new attempt. If the issue continues, reach out to your instructor.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Button onClick={() => navigate(-1)} variant="outline">
              Go back
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-primary/5 via-background to-background">
        <div className="mx-auto w-full max-w-6xl px-4 py-10 sm:px-6 lg:px-10">
          <section className="rounded-3xl bg-primary px-6 py-8 text-primary-foreground shadow-xl">
            <p className="text-xs uppercase tracking-[0.2em] text-primary-foreground/75">In progress</p>
          <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">{quizTitle}</h1>
          {quizDescription && (
            quizDescriptionMarkup ? (
            <div className="mt-3 text-sm leading-relaxed text-primary-foreground/80">
              <div
                className="prose max-w-none text-sm markup-content"
                dangerouslySetInnerHTML={{ __html: quizDescriptionMarkup }}
              />
            </div>
            ) : (
              <p className="mt-3 text-sm text-primary-foreground/80 whitespace-pre-line">{quizDescription}</p>
            )
          )}
          <p className="mt-2 text-sm text-primary-foreground/80">
            Reference {attemptReference}
            {resolvedStudentIdentifier ? ` · ${resolvedStudentIdentifier}` : ''} · {totalCount} question{totalCount === 1 ? '' : 's'}
          </p>
        </section>

        <div className="mt-8 space-y-4">
          {banner && (
            <div
              className={cn(
                'rounded-2xl border px-4 py-3 text-sm shadow-sm sm:px-5',
                banner.type === 'error'
                  ? 'border-destructive/40 bg-destructive/10 text-destructive'
                  : 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700'
              )}
            >
              <div className="flex items-start justify-between gap-4">
                <p>{banner.message}</p>
                <button className="text-xs text-muted-foreground" onClick={() => setBanner(null)}>
                  Dismiss
                </button>
              </div>
            </div>
          )}

          <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(260px,1fr)]">
            <section className="order-2 space-y-5 lg:order-1">
              {slots.map((slot) => (
                <ProblemAnswer
                  key={slot.id}
                  slot={slot}
                  answer={answers[slot.slot] || createEmptyAnswer(slot)}
                  onChange={(value) => handleAnswerChange(slot, value)}
                  onSave={() => handleSave(slot)}
                  saveState={savingState[slot.slot]}
                  showValidation={showValidation}
                  ratingConfig={responseConfig}
                  ratingCriteriaCount={ratingCriteriaCount}
                  ratingConfigError={responseConfigError}
                  isRatingConfigLoading={isConfigLoading}
                  quizOpen={quizOpen}
                  quizClosedMessage={quizClosedMessage}
                />
              ))}
            </section>

            <aside className="order-1 space-y-6 lg:order-2">
              <Card className="border-primary/40 shadow-lg">
                <CardHeader>
                  <CardTitle>Submission status</CardTitle>
                  <CardDescription>Keep saving as you go and submit when you&apos;re confident.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <div className="mb-2 flex items-center justify-between text-sm font-medium">
                      <span>
                        {answeredCount} of {totalCount} answered
                      </span>
                      <span>{progressPercent}%</span>
                    </div>
                    <div className="h-2 rounded-full bg-muted">
                      <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${progressPercent}%` }} />
                    </div>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {allAnswered
                      ? 'Nice work! Double-check your responses before sending your quiz.'
                      : `Answer ${totalCount - answeredCount} more question${totalCount - answeredCount === 1 ? '' : 's'} to unlock submission.`}
                  </p>
                  <Button
                    className="w-full text-base font-semibold"
                    size="lg"
                    onClick={handleComplete}
                    disabled={!allAnswered || submitting || !quizOpen}
                  >
                    {submitting ? 'Submitting...' : 'Submit quiz'}
                  </Button>
                  {!allAnswered && showValidation && (
                    <p className="text-sm font-medium text-destructive">All questions are required before submitting.</p>
                  )}
                  {!quizOpen && (
                    <p className="text-sm font-medium text-destructive">
                      {quizClosedMessage || QUIZ_CLOSED_MESSAGE}
                    </p>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Helpful reminders</CardTitle>
                  <CardDescription>Everything you do is saved to this attempt.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm text-muted-foreground">
                  <p>1. Fill in an answer for every problem - blank responses are not allowed.</p>
                  <p>2. Use the "Save answer" button if you pause or switch devices.</p>
                  <p>3. When all problems show as answered, submit once. You cannot edit afterwards.</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Attempt details</CardTitle>
                </CardHeader>
                <CardContent>
                  <dl className="space-y-2 text-sm">
                    <div className="flex justify-between border-b pb-2 text-muted-foreground">
                      <dt>Attempt reference</dt>
                      <dd className="text-foreground font-medium">{attemptReference}</dd>
                    </div>
                    {resolvedStudentIdentifier && (
                      <div className="flex justify-between border-b pb-2 text-muted-foreground">
                        <dt>Student</dt>
                        <dd className="text-foreground font-medium">{resolvedStudentIdentifier}</dd>
                      </div>
                    )}
                    <div className="flex justify-between text-muted-foreground">
                      <dt>Questions</dt>
                      <dd className="text-foreground font-medium">{totalCount}</dd>
                    </div>
                  </dl>
                </CardContent>
              </Card>
            </aside>
          </div>
        </div>
      </div>
    </div>
  );
};

const ProblemAnswer = ({
  slot,
  answer,
  onChange,
  onSave,
  saveState,
  showValidation,
  ratingConfig,
  ratingCriteriaCount,
  ratingConfigError,
  isRatingConfigLoading,
  quizOpen,
  quizClosedMessage,
}) => {
  const isRating = slot.response_type === RESPONSE_TYPES.RATING;
  const state = saveState || (hasAnyInput(slot, answer) ? 'dirty' : null);
  const isSaving = state === 'saving';
  const isSaved = state === 'saved';
  const isComplete = isAnswerComplete(slot, answer, ratingCriteriaCount);
  const isLocked = !quizOpen;
  const hasError = !isLocked && showValidation && !isComplete;
  const problemLabel = slot.problem_display_label || 'Problem';
  const instructionText = slot.slot_instruction?.trim();
  const statementMarkupHtml = slot.problem_statement ? renderProblemMarkupHtml(slot.problem_statement) : '';
  const criteria = Array.isArray(ratingConfig?.criteria) ? ratingConfig.criteria : [];
  const scale = Array.isArray(ratingConfig?.scale) ? ratingConfig.scale : [];
  const isRatingConfigReady = !isRating || (criteria.length > 0 && scale.length > 0);
  const closureMessage = quizClosedMessage || QUIZ_CLOSED_MESSAGE;
  let statusMessage = '';
  if (isLocked) {
    statusMessage = closureMessage;
  } else if (hasError) {
    statusMessage = isRating ? 'Provide a rating for each criterion.' : 'This question needs an answer.';
  } else if (state === 'dirty') {
    statusMessage = 'Unsaved changes - save before you leave this page.';
  } else if (isSaved) {
    statusMessage = 'Saved just now.';
  } else if (!state && !isSaved) {
    statusMessage = 'Answer is required before submitting.';
  }

  const handleRatingSelection = (criterionId, optionValue) => {
    const nextRatings = { ...(answer?.ratings || {}) };
    nextRatings[criterionId] = optionValue;
    onChange({ response_type: RESPONSE_TYPES.RATING, ratings: nextRatings });
  };

  const renderRatingFields = () => {
    if (isRatingConfigLoading) {
      return <p className="mt-5 text-sm text-muted-foreground">Loading the rating rubric…</p>;
    }
    if (!isRatingConfigReady) {
      return (
        <p className="mt-5 rounded-lg border border-dashed p-3 text-sm text-destructive">
          {ratingConfigError || 'We were unable to load the rating rubric. Please refresh this page or contact your instructor.'}
        </p>
      );
    }
    return (
      <LikertRating
        criteria={criteria}
        scale={scale}
        selectedRatings={answer?.ratings || {}}
        onRatingSelect={handleRatingSelection}
        slotId={slot.id}
        disabled={!quizOpen}
      />
    );
  };

  return (
    <article
      className={cn(
        'rounded-3xl border bg-card/70 p-6 shadow-sm backdrop-blur-sm transition-colors',
        hasError ? 'border-destructive/60 bg-destructive/5' : 'border-border'
      )}
    > 
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">{slot.slot_label}</p>
          <p className="mt-1 text-foreground">
            <span className="rounded-full bg-blue-400 px-2 py-1 mr-1 text-xs font-medium text-accent">
              {instructionText}
            </span>
          </p>
        </div>
        {isSaved && <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-600">Saved</span>}
        {state === 'error' && <span className="rounded-full bg-destructive/10 px-3 py-1 text-xs font-medium text-destructive">Error</span>}
      </div>
      {statementMarkupHtml ? (
        <div className="mt-4 text-sm leading-relaxed text-muted-foreground">
          <div
            className="prose max-w-none text-sm markup-content"
            dangerouslySetInnerHTML={{ __html: statementMarkupHtml }}
          />
        </div>
      ) : (
        <p className="mt-4 whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">{slot.problem_statement}</p>
      )}
      {isRating ? (
        renderRatingFields()
      ) : (
        <Textarea
          value={answer?.text || ''}
          onChange={(e) => onChange({ response_type: RESPONSE_TYPES.OPEN_TEXT, text: e.target.value })}
          placeholder="Type your work and final answer here..."
          className="mt-5 min-h-[150px] resize-y"
          disabled={!quizOpen}
        />
      )}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm">
        <p className={cn(isLocked || hasError ? 'text-destructive' : 'text-muted-foreground')}>
          {statusMessage}
        </p>
        <Button
          size="sm"
          onClick={onSave}
          disabled={
            isSaving ||
            !isComplete ||
            (isRating && !isRatingConfigReady) ||
            !quizOpen
          }
        >
          {isSaving ? 'Saving...' : 'Save answer'}
        </Button>
      </div>
    </article>
  );
};

export default QuizAttemptPage;
