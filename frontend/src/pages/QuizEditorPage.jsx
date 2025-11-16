import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import AppShell from '@/components/layout/AppShell';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Modal } from '@/components/ui/modal';
import api from '@/lib/api';
import { cn } from '@/lib/utils';
import { getQuizStatus } from '@/lib/quizStatus';
import { useResponseConfig } from '@/lib/useResponseConfig';
import { RESPONSE_TYPE_OPTIONS, getResponseTypeLabel } from '@/lib/responseTypes';
import QuizStatusBanner from '@/components/quiz-editor/QuizStatusBanner';
import QuizOverviewTab from '@/components/quiz-editor/QuizOverviewTab';
import QuizSlotsTab from '@/components/quiz-editor/QuizSlotsTab';
import QuizResponsesTab from '@/components/quiz-editor/QuizResponsesTab';
import QuizAllowedInstructorsTab from '@/components/quiz-editor/QuizAllowedInstructorsTab';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import useProblemStatements from '@/lib/useProblemStatements';

const TABS = {
  OVERVIEW: 'overview',
  SLOTS: 'slots',
  RESPONSES: 'responses',
  INSTRUCTORS: 'instructors',
};

const defaultSlotForm = { label: '', instruction: '', problem_bank: '', response_type: 'open_text' };

const formatDateTime = (value) => {
  if (!value) return 'Not scheduled';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Not scheduled';
  return date.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
};

const normalizeSlot = (slot) => ({
  ...slot,
  response_type: slot.response_type || 'open_text',
  order: typeof slot.order === 'number' ? slot.order.toString() : slot.order || '',
  slot_problems: Array.isArray(slot.slot_problems) ? slot.slot_problems : [],
  instruction: slot.instruction ?? '',
  original_problem_bank: slot.problem_bank ?? null,
  pending_bank_change: false,
});

const renderProblemMarkupHtml = (statement) => {
  if (!statement) {
    return '';
  }
  try {
    const dirty = marked.parse(statement);
    return DOMPurify.sanitize(dirty);
  } catch {
    return '';
  }
};

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const mixChannel = (start, end, ratio) => Math.round(start + (end - start) * ratio);

const toHexChannel = (value) => value.toString(16).padStart(2, '0');

const RATING_COLOR_STOPS = {
  low: [239, 68, 68],
  mid: [249, 115, 22],
  high: [34, 197, 94],
};

const getGradientColor = (normalized) => {
  const normalizedValue = clamp(normalized ?? 0.5, 0, 1);
  const isLowHalf = normalizedValue <= 0.5;
  const startColor = isLowHalf ? RATING_COLOR_STOPS.low : RATING_COLOR_STOPS.mid;
  const endColor = isLowHalf ? RATING_COLOR_STOPS.mid : RATING_COLOR_STOPS.high;
  const ratio = isLowHalf ? normalizedValue / 0.5 : (normalizedValue - 0.5) / 0.5;
  const [r, g, b] = startColor.map((channel, index) => mixChannel(channel, endColor[index], ratio));
  return `#${toHexChannel(r)}${toHexChannel(g)}${toHexChannel(b)}`;
};

const getRatingIndicatorStyles = (value, range) => {
  if (value === undefined || value === null) {
    return { backgroundColor: '#e2e8f0', color: '#0f172a' };
  }
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return { backgroundColor: '#e2e8f0', color: '#0f172a' };
  }
  const { min, max } = range || {};
  const hasRange = Number.isFinite(min) && Number.isFinite(max);
  const normalized = hasRange
    ? max === min
      ? 0.5
      : clamp((numericValue - min) / (max - min), 0, 1)
    : 0.5;
  const backgroundColor = getGradientColor(normalized);
  const color = normalized <= 0.55 ? '#ffffff' : '#0f172a';
  return { backgroundColor, color };
};

const QuizEditorPage = () => {
  const { quizId } = useParams();
  const quizIdNumber = Number(quizId);
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState(TABS.OVERVIEW);
  const [quiz, setQuiz] = useState(null);
  const [quizzes, setQuizzes] = useState([]);
  const [isLoadingQuiz, setIsLoadingQuiz] = useState(true);
  const [isLoadingQuizzes, setIsLoadingQuizzes] = useState(true);
  const [banks, setBanks] = useState([]);
  const [isLoadingBanks, setIsLoadingBanks] = useState(true);
  const [slots, setSlots] = useState([]);
  const [attempts, setAttempts] = useState([]);
  const [details, setDetails] = useState({ title: '', description: '' });
  const [detailsSaving, setDetailsSaving] = useState(false);
  const [detailsError, setDetailsError] = useState('');
  const [scheduleActionLoading, setScheduleActionLoading] = useState(false);
  const [scheduleActionError, setScheduleActionError] = useState('');
  const [pageError, setPageError] = useState('');
  const [slotForm, setSlotForm] = useState(() => ({ ...defaultSlotForm }));
  const [slotFormError, setSlotFormError] = useState('');
  const [isCreatingSlot, setIsCreatingSlot] = useState(false);
  const [slotError, setSlotError] = useState('');
  const [savingSlotId, setSavingSlotId] = useState(null);
  const [slotProblemOptions, setSlotProblemOptions] = useState({});
  const [isSelectingAllProblems, setIsSelectingAllProblems] = useState(false);
  const [expandedSlotProblems, setExpandedSlotProblems] = useState({});
  const { statements: slotProblemStatements, loadStatement: loadSlotProblemStatement } =
    useProblemStatements();
  const [attemptError, setAttemptError] = useState('');
  const [attemptToDelete, setAttemptToDelete] = useState(null);
  const [isDeletingAttempt, setIsDeletingAttempt] = useState(false);
  const [copyMessage, setCopyMessage] = useState('');
  const [isSlotModalOpen, setIsSlotModalOpen] = useState(false);
  const [activeSlotId, setActiveSlotId] = useState(null);
  const [selectedAttempt, setSelectedAttempt] = useState(null);
  const [previewedProblem, setPreviewedProblem] = useState(null);
  const [allowedInstructors, setAllowedInstructors] = useState([]);
  const [canManageAllowedInstructors, setCanManageAllowedInstructors] = useState(false);
  const [instructorId, setInstructorId] = useState('');
  const [instructorError, setInstructorError] = useState('');
  const pendingBankRequests = useRef(new Set());
  const { config: responseConfig } = useResponseConfig();

  const ratingCriteria = useMemo(() => {
    return Array.isArray(responseConfig?.criteria) ? responseConfig.criteria : [];
  }, [responseConfig]);

  const ratingScaleOptions = useMemo(() => {
    return Array.isArray(responseConfig?.scale) ? responseConfig.scale : [];
  }, [responseConfig]);

  const ratingScaleLabelMap = useMemo(() => {
    if (!ratingScaleOptions.length) {
      return {};
    }
    return ratingScaleOptions.reduce((acc, option) => {
      acc[`${option.value}`] = option.label;
      return acc;
    }, {});
  }, [ratingScaleOptions]);

  const ratingScaleRange = useMemo(() => {
    const numericValues = ratingScaleOptions
      .map((option) => Number(option.value))
      .filter((value) => Number.isFinite(value));
    if (!numericValues.length) {
      return { min: null, max: null };
    }
    return {
      min: Math.min(...numericValues),
      max: Math.max(...numericValues),
    };
  }, [ratingScaleOptions]);

  const previewStatementMarkup = useMemo(
    () => (previewedProblem ? renderProblemMarkupHtml(previewedProblem.statement) : ''),
    [previewedProblem]
  );

  const openSlotModal = () => {
    setSlotForm({ ...defaultSlotForm });
    setSlotFormError('');
    setIsSlotModalOpen(true);
  };

  const closeSlotModal = () => {
    setIsSlotModalOpen(false);
    setSlotForm({ ...defaultSlotForm });
    setSlotFormError('');
  };

  const openSlotDetailModal = (slotId) => {
    setSlotError('');
    setActiveSlotId(slotId);
  };

  const closeSlotDetailModal = () => {
    setActiveSlotId(null);
  };

  const openAttemptModal = (attempt) => {
    setSelectedAttempt(attempt);
    setPreviewedProblem(null);
  };

  const closeAttemptModal = () => {
    setSelectedAttempt(null);
    setPreviewedProblem(null);
  };

  const loadBankProblems = useCallback(
    (bankId) => {
      if (!bankId || slotProblemOptions[bankId] || pendingBankRequests.current.has(bankId)) {
        return;
      }
      pendingBankRequests.current.add(bankId);
      api
        .get(`/api/problem-banks/${bankId}/problems/`)
        .then((res) => {
          setSlotProblemOptions((prev) => ({ ...prev, [bankId]: res.data }));
          setSlotError('');
        })
        .catch(() => {
          setSlotError('Unable to load the problems for one of the banks.');
        })
        .finally(() => {
          pendingBankRequests.current.delete(bankId);
        });
    },
    [slotProblemOptions]
  );

  const loadQuizList = () => {
    setIsLoadingQuizzes(true);
    api
      .get('/api/quizzes/')
      .then((res) => setQuizzes(res.data))
      .catch(() => {})
      .finally(() => setIsLoadingQuizzes(false));
  };

  const loadBanks = () => {
    setIsLoadingBanks(true);
    api
      .get('/api/problem-banks/')
      .then((res) => setBanks(res.data))
      .catch(() => setBanks([]))
      .finally(() => setIsLoadingBanks(false));
  };

  const loadAttempts = () => {
    return api
      .get(`/api/quizzes/${quizId}/attempts/`)
      .then((res) => {
        setAttempts(res.data);
        setAttemptError('');
      })
      .catch(() => setAttemptError('Unable to load student responses.'));
  };

  const toggleProblemDetails = (slotId, problemId) => {
    const isCurrentlyExpanded = expandedSlotProblems[slotId]?.includes(problemId);
    setExpandedSlotProblems((prev) => {
      const current = new Set(prev[slotId] ?? []);
      if (isCurrentlyExpanded) {
        current.delete(problemId);
      } else {
        current.add(problemId);
      }
      return { ...prev, [slotId]: Array.from(current) };
    });
    if (!isCurrentlyExpanded) {
      const entry = slotProblemStatements[problemId];
      if (!entry?.statement && !entry?.loading) {
        loadSlotProblemStatement(problemId);
      }
    }
  };

  const requestAttemptDeletion = (attempt) => {
    setAttemptToDelete(attempt);
    setAttemptError('');
  };

  const closeAttemptDeleteModal = () => {
    if (isDeletingAttempt) return;
    setAttemptToDelete(null);
  };

  const handleDeleteAttempt = async () => {
    if (!attemptToDelete) return;
    setIsDeletingAttempt(true);
    try {
      await api.delete(`/api/quizzes/${quizId}/attempts/${attemptToDelete.id}/`);
      setAttemptError('');
      setAttemptToDelete(null);
      await loadAttempts();
    } catch (error) {
      const detail = error.response?.data?.detail || 'Unable to delete this attempt right now.';
      setAttemptError(detail);
    } finally {
      setIsDeletingAttempt(false);
    }
  };

  const loadSlots = () => {
    return api
      .get(`/api/quizzes/${quizId}/slots/`)
      .then((res) => {
        setSlots(res.data.map(normalizeSlot));
        setSlotError('');
      })
      .catch(() => setSlotError('Unable to load slots right now.'));
  };

  const loadAllowedInstructors = () => {
    api
      .get(`/api/quizzes/${quizId}/allowed-instructors/`)
      .then((res) => {
        const responseData = res.data;
        const instructors = Array.isArray(responseData)
          ? responseData
          : responseData?.instructors ?? [];
        const canManage = Array.isArray(responseData)
          ? false
          : Boolean(responseData?.can_manage);
        setAllowedInstructors(instructors);
        setCanManageAllowedInstructors(canManage);
        setInstructorError('');
      })
      .catch(() => {
        setInstructorError('Unable to load allowed instructors.');
        setCanManageAllowedInstructors(false);
      });
  };

  const handleAddInstructor = async () => {
    if (!instructorId.trim()) return;
    if (!canManageAllowedInstructors) {
      setInstructorError('Only the quiz owner can add instructors.');
      return;
    }
    try {
      await api.post(`/api/quizzes/${quizId}/allowed-instructors/`, { instructor_username: instructorId });
      setInstructorId('');
      setInstructorError('');
      loadAllowedInstructors();
    } catch (error) {
      const detail = error.response?.data?.detail || 'Unable to add instructor.';
      setInstructorError(detail);
    }
  };

  const handleRemoveInstructor = async (id) => {
    if (!canManageAllowedInstructors) {
      setInstructorError('Only the quiz owner can remove instructors.');
      return;
    }
    try {
      await api.delete(`/api/quizzes/${quizId}/allowed-instructors/${id}/`);
      setInstructorError('');
      loadAllowedInstructors();
    } catch (error) {
      const detail = error.response?.data?.detail || 'Unable to remove instructor.';
      setInstructorError(detail);
    }
  };

  const loadQuizData = () => {
    setIsLoadingQuiz(true);
    Promise.all([
      api.get(`/api/quizzes/${quizId}/`),
      api.get(`/api/quizzes/${quizId}/slots/`),
      api.get(`/api/quizzes/${quizId}/attempts/`),
    ])
      .then(([quizRes, slotsRes, attemptsRes]) => {
        setQuiz(quizRes.data);
        setDetails({
          title: quizRes.data.title || '',
          description: quizRes.data.description || '',
        });
        setSlots(slotsRes.data.map(normalizeSlot));
        setAttempts(attemptsRes.data);
        setPageError('');
      })
      .catch((error) => {
        if (error?.response?.status === 404) {
          navigate('/dashboard', { replace: true });
          return;
        }
        setPageError('Unable to load quiz details. Please refresh the page.');
      })
      .finally(() => setIsLoadingQuiz(false));
  };

  useEffect(() => {
    loadBanks();
  }, []);

  useEffect(() => {
    loadQuizList();
  }, [quizId]);

  useEffect(() => {
    setSlotProblemOptions({});
    pendingBankRequests.current.clear();
    loadQuizData();
    loadAllowedInstructors();
  }, [quizId]);

  useEffect(() => {
    slots.forEach((slot) => {
      loadBankProblems(slot.problem_bank);
    });
  }, [slots, loadBankProblems]);

  useEffect(() => {
    if (!isSlotModalOpen) return undefined;
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') {
        closeSlotModal();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isSlotModalOpen]);

  const slotReadiness = useMemo(() => {
    const total = slots.length;
    const ready = slots.filter((slot) => slot.slot_problems?.length).length;
    return { ready, total };
  }, [slots]);

  const schedulePreview = useMemo(() => {
    if (!quiz) return { status: 'Draft', description: 'Add problem slots to get this quiz ready.' };
    const now = Date.now();
    const start = quiz.start_time ? new Date(quiz.start_time).getTime() : null;
    const end = quiz.end_time ? new Date(quiz.end_time).getTime() : null;
    if (start && now < start) {
      return { status: 'Scheduled', description: `Opens ${formatDateTime(quiz.start_time)}` };
    }
    if (end && now > end) {
      return { status: 'Closed', description: `Closed ${formatDateTime(quiz.end_time)}` };
    }
    if (start && (!end || now <= end)) {
      return { status: 'Open', description: 'Students can join using the public link below.' };
    }
    return { status: 'Draft', description: 'Share the public link whenever you are ready.' };
  }, [quiz]);

  const quizStatusKey = useMemo(() => {
    if (!quiz) return null;
    return getQuizStatus(quiz).key;
  }, [quiz]);

  const scheduleState = useMemo(() => {
    if (!quiz) return null;
    const startLabel = quiz.start_time ? formatDateTime(quiz.start_time) : 'Not opened yet';
    let endLabel = 'Not closed yet';
    if (quiz.end_time) {
      endLabel = formatDateTime(quiz.end_time);
    } else if (quiz.start_time) {
      endLabel = 'Still open';
    }
    const isOpen = Boolean(quiz.start_time && !quiz.end_time);
    return { startLabel, endLabel, isOpen };
  }, [quiz]);

  const handleDetailChange = (event) => {
    const { name, value } = event.target;
    setDetails((prev) => ({ ...prev, [name]: value }));
    setDetailsError('');
  };

  const handleSaveDetails = async (event) => {
    event.preventDefault();
    if (!quiz) return;
    if (!details.title.trim()) {
      setDetailsError('Quiz title is required.');
      return;
    }
    setDetailsSaving(true);
    try {
      const payload = {
        title: details.title.trim(),
        description: details.description.trim(),
      };
      const response = await api.patch(`/api/quizzes/${quiz.id}/`, payload);
      setQuiz(response.data);
      setDetailsError('');
    } catch (error) {
      const data = error.response?.data;
      const detail = data?.detail || data?.title?.[0] || 'Could not save the quiz details.';
      setDetailsError(detail);
    } finally {
      setDetailsSaving(false);
    }
  };

  const notifyQuizStatusChange = (updatedQuiz) => {
    if (typeof window === 'undefined') return;
    window.dispatchEvent(new CustomEvent('quizStatusChanged', { detail: updatedQuiz }));
  };

  const handleOpenQuiz = async () => {
    if (!quiz) return;
    setScheduleActionError('');
    if (!readyForStudents) {
      setScheduleActionError('Add at least one slot with problems before publishing this quiz.');
      return;
    }
    setScheduleActionLoading(true);
    try {
      const response = await api.post(`/api/quizzes/${quiz.id}/open/`);
      setQuiz(response.data);
      notifyQuizStatusChange(response.data);
    } catch (error) {
      const detail = error.response?.data?.detail || 'Unable to open the quiz right now.';
      setScheduleActionError(detail);
    } finally {
      setScheduleActionLoading(false);
    }
  };

  const handleCloseQuiz = async () => {
    if (!quiz) return;
    setScheduleActionError('');
    setScheduleActionLoading(true);
    try {
      const response = await api.post(`/api/quizzes/${quiz.id}/close/`);
      setQuiz(response.data);
      notifyQuizStatusChange(response.data);
    } catch (error) {
      const detail = error.response?.data?.detail || 'Unable to close the quiz right now.';
      setScheduleActionError(detail);
    } finally {
      setScheduleActionLoading(false);
    }
  };

  const handleSlotFormChange = (event) => {
    const { name, value } = event.target;
    setSlotForm((prev) => ({ ...prev, [name]: value }));
    setSlotFormError('');
  };

  const handleCreateSlot = async (event) => {
    event.preventDefault();
    if (!slotForm.label.trim()) {
      setSlotFormError('Provide a label for the slot.');
      return;
    }
    if (!slotForm.problem_bank) {
      setSlotFormError('Select a problem bank for this slot.');
      return;
    }
    setIsCreatingSlot(true);
    try {
      const payload = {
        label: slotForm.label.trim(),
        instruction: slotForm.instruction.trim(),
        problem_bank: Number(slotForm.problem_bank),
        response_type: slotForm.response_type,
      };
      await api.post(`/api/quizzes/${quizId}/slots/`, payload);
      closeSlotModal();
      loadSlots();
    } catch (error) {
      const detail = error.response?.data?.detail || error.response?.data?.order?.[0] || 'Could not add the slot yet.';
      setSlotFormError(detail);
    } finally {
      setIsCreatingSlot(false);
    }
  };

  const handleSlotChange = (slotId, field, value) => {
    if (field === 'problem_bank' && (value === '' || value === null)) {
      setSlotError('Each slot must stay linked to a problem bank.');
      return;
    }
    setSlots((prev) =>
      prev.map((slot) => {
        if (slot.id !== slotId) {
          return slot;
        }
        if (field === 'problem_bank') {
          const normalizedValue = Number(value);
          const shouldReset = normalizedValue !== slot.problem_bank;
          const selectedBank = normalizedValue ? banks.find((bank) => bank.id === normalizedValue) : null;
          return {
            ...slot,
            problem_bank: normalizedValue,
            problem_bank_name: selectedBank ? selectedBank.name : null,
            pending_bank_change: normalizedValue !== slot.original_problem_bank,
            ...(shouldReset ? { slot_problems: [] } : {}),
          };
        }
        return {
          ...slot,
          [field]: value,
        };
      })
    );
    if (field === 'problem_bank') {
      const normalizedValue = Number(value);
      if (normalizedValue) {
        loadBankProblems(normalizedValue);
      }
      setSlotError('');
    }
  };

  const handleSaveSlot = async (slot) => {
    if (!slot.label.trim()) {
      setSlotError('Slot label cannot be empty.');
      return;
    }
    const selectedBankId = Number(slot.problem_bank);
    if (!selectedBankId) {
      setSlotError('Each slot must have a problem bank.');
      return;
    }
  setSavingSlotId(slot.id);
  setSlotError('');
  try {
    const trimmedInstruction = (slot.instruction || '').trim();
    await api.patch(`/api/slots/${slot.id}/`, {
      label: slot.label.trim(),
      problem_bank: selectedBankId,
      response_type: slot.response_type,
      instruction: trimmedInstruction,
    });
      loadSlots();
    } catch (error) {
      const detail = error.response?.data?.detail || error.response?.data?.label?.[0] || 'Unable to update the slot.';
      setSlotError(detail);
    } finally {
      setSavingSlotId(null);
    }
  };

  const toggleSlotProblem = async (slot, problem) => {
    if (!slot.problem_bank) {
      setSlotError('Assign a problem bank to the slot before choosing problems.');
      return;
    }
    if (slot.pending_bank_change) {
      setSlotError('Save the slot after changing its bank before selecting problems.');
      return;
    }
    const existing = slot.slot_problems.find((sp) => sp.problem === problem.id);
    try {
      if (existing) {
        await api.delete(`/api/slot-problems/${existing.id}/`);
      } else {
        await api.post(`/api/slots/${slot.id}/slot-problems/`, { problem_ids: [problem.id] });
      }
      loadSlots();
    } catch {
      setSlotError('Unable to update the problem selection right now.');
    }
  };

  const selectAllSlotProblems = async (slot) => {
    if (!slot.problem_bank) {
      setSlotError('Assign a problem bank to the slot before choosing problems.');
      return;
    }
    if (slot.pending_bank_change) {
      setSlotError('Save the slot after changing its bank before selecting problems.');
      return;
    }
    const problems = slotProblemOptions[slot.problem_bank];
    if (!problems?.length) {
      return;
    }
    const existingProblemIds = new Set(slot.slot_problems.map((sp) => sp.problem));
    const missingProblemIds = problems
      .filter((problem) => !existingProblemIds.has(problem.id))
      .map((problem) => problem.id);
    if (!missingProblemIds.length) {
      return;
    }
    setIsSelectingAllProblems(true);
    try {
      await api.post(`/api/slots/${slot.id}/slot-problems/`, { problem_ids: missingProblemIds });
      await loadSlots();
      setSlotError('');
    } catch {
      setSlotError('Unable to add all problems right now.');
    } finally {
      setIsSelectingAllProblems(false);
    }
  };

  const handleCopyLink = async () => {
    if (!quiz) return;
    const base = typeof window !== 'undefined' ? window.location.origin : '';
    const link = `${base}/q/${quiz.public_id}`;
    try {
      await navigator.clipboard.writeText(link);
      setCopyMessage('Copied link to clipboard');
    } catch {
      setCopyMessage('Unable to copy link.');
    }
  };

  useEffect(() => {
    if (!copyMessage) return undefined;
    const timeout = setTimeout(() => setCopyMessage(''), 2500);
    return () => clearTimeout(timeout);
  }, [copyMessage]);

  const quizLink = quiz ? `/q/${quiz.public_id}` : '';
  const canCreateSlot = Boolean(slotForm.label.trim() && slotForm.problem_bank);
  const readyForStudents = slotReadiness.total > 0 && slotReadiness.ready === slotReadiness.total;
  const activeSlot = useMemo(() => {
    if (activeSlotId === null) {
      return null;
    }
    return slots.find((slot) => slot.id === activeSlotId) || null;
  }, [activeSlotId, slots]);

  const renderSlotProblems = (slot) => {
    const renderHeader = (action = null) => (
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold">Eligible problems</p>
        {action}
      </div>
    );

    if (!slot.problem_bank) {
      return (
        <div className="space-y-3">
          {renderHeader()}
          <p className="text-sm text-muted-foreground">Select a problem bank above to enable this slot.</p>
        </div>
      );
    }
    const problems = slotProblemOptions[slot.problem_bank];
    if (!problems) {
      return (
        <div className="space-y-3">
          {renderHeader()}
          <p className="text-sm text-muted-foreground">Loading the problems for this bank…</p>
        </div>
      );
    }
    if (!problems.length) {
      return (
        <div className="space-y-3">
          {renderHeader()}
          <p className="text-sm text-muted-foreground">No problems in this bank yet. Add them from the problem bank manager.</p>
        </div>
      );
    }
    const disableChanges = Boolean(slot.pending_bank_change);
    const existingProblemIds = new Set(slot.slot_problems.map((sp) => sp.problem));
    const missingProblemIds = problems
      .filter((problem) => !existingProblemIds.has(problem.id))
      .map((problem) => problem.id);
    const canSelectAll = missingProblemIds.length > 0;
    const selectAllAction = canSelectAll ? (
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={disableChanges || isSelectingAllProblems}
        onClick={() => selectAllSlotProblems(slot)}
      >
        {isSelectingAllProblems ? 'Selecting…' : 'Select all'}
      </Button>
    ) : null;
    return (
      <div className="space-y-3">
        {renderHeader(selectAllAction)}
        {disableChanges && (
          <p className="text-sm text-muted-foreground">Save this slot to confirm the bank before selecting problems.</p>
        )}
        {problems.map((problem, index) => {
          const linked = slot.slot_problems.find((sp) => sp.problem === problem.id);
          const displayIndex = problem.order_in_bank ?? index + 1;
          const displayLabel = `Problem ${displayIndex}`;
          const expandedIds = new Set(expandedSlotProblems[slot.id] ?? []);
          const isExpanded = expandedIds.has(problem.id);
          const entry = slotProblemStatements[problem.id];
          const hasStatementEntry = entry && 'statement' in entry;
          const rawStatement = hasStatementEntry ? entry.statement : '';
          const statementText = rawStatement?.trim();
          const statementMarkupHtml = statementText ? renderProblemMarkupHtml(rawStatement) : '';
          const isStatementLoading = !entry || Boolean(entry.loading);
          const statementError = entry?.error;
          return (
            <div key={problem.id} className="space-y-2 rounded-lg border border-muted/40 bg-background/60 p-3">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  role="checkbox"
                  aria-checked={Boolean(linked)}
                  className={cn(
                    'flex h-6 w-6 items-center justify-center rounded-md border transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                    linked
                      ? 'border-primary/70 bg-primary text-background'
                      : 'border-border bg-transparent text-muted-foreground',
                    disableChanges && 'pointer-events-none opacity-50'
                  )}
                  onClick={() => toggleSlotProblem(slot, problem)}
                  disabled={disableChanges}
                >
                  {linked && (
                    <svg viewBox="0 0 16 16" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                      <path d="M3.75 8.75l3.25 3.25 5.25-5.5" />
                    </svg>
                  )}
                </button>
                <button
                  type="button"
                  className="flex-1 text-left text-sm font-semibold text-foreground transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  onClick={() => toggleProblemDetails(slot.id, problem.id)}
                  aria-expanded={isExpanded}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span>{displayLabel}</span>
                    <span className="text-xs text-muted-foreground">{isExpanded ? 'Hide details' : 'Show details'}</span>
                  </div>
                </button>
              </div>
              {isExpanded && (
                <div className="rounded-md border border-muted/30 bg-muted/10 p-3 text-sm">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Description</p>
                  {isStatementLoading ? (
                    <p className="mt-2 text-sm text-muted-foreground">Loading problem markup…</p>
                  ) : statementError ? (
                    <p className="mt-2 text-sm text-destructive">{statementError}</p>
                  ) : statementMarkupHtml ? (
                    <div
                      className="mt-2 text-sm text-foreground"
                      dangerouslySetInnerHTML={{ __html: statementMarkupHtml }}
                    />
                  ) : (
                    <p className="mt-2 text-sm text-muted-foreground">No description provided.</p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  const attemptsSummary = useMemo(() => {
    const total = attempts.length;
    const completed = attempts.filter((attempt) => Boolean(attempt.completed_at)).length;
    return { total, completed };
  }, [attempts]);

  const renderAttemptAnswer = (attemptSlot) => {
    if (attemptSlot.response_type === 'rating') {
      const ratings = attemptSlot.answer_data?.ratings;
      if (!ratings || typeof ratings !== 'object' || !Object.keys(ratings).length) {
        return <span className="text-muted-foreground">No rating submitted.</span>;
      }
      const rows = (ratingCriteria.length
        ? ratingCriteria.map((criterion) => ({
            id: criterion.id,
            name: criterion.name,
            description: criterion.description,
            value: ratings[criterion.id],
          }))
        : Object.entries(ratings).map(([id, value]) => ({ id, name: id, description: '', value }))
      ).filter((row) => row.id);
      if (!rows.length) {
        return <span className="text-muted-foreground">No rating submitted.</span>;
      }
      return (
        <div className="space-y-3">
          {rows.map((row) => {
            const valueKey = `${row.value}`;
            const scaleLabel =
              valueKey && ratingScaleLabelMap[valueKey] ? ratingScaleLabelMap[valueKey] : null;
            const indicatorStyles = getRatingIndicatorStyles(row.value, ratingScaleRange);
            const bubbleValue = row.value === undefined || row.value === null ? '—' : `${row.value}`;
            const helperLabel = scaleLabel
              ? row.value === undefined || row.value === null
                ? scaleLabel
                : `${scaleLabel} (${row.value})`
              : null;
            return (
              <div
                key={row.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-muted/40 bg-card/80 px-3 py-3 text-sm"
              >
                <div className="flex-1 space-y-1">
                  <p className="font-semibold text-foreground">{row.name}</p>
                  {helperLabel && <p className="text-xs text-muted-foreground">{helperLabel}</p>}
                </div>
                <div className="flex flex-col items-end justify-center gap-1">
                  <span className="text-[10px] font-semibold uppercase tracking-[0.3em] text-muted-foreground">Rating</span>
                  <div
                    className="flex h-12 min-w-[3.25rem] items-center justify-center rounded-full border px-3 text-sm font-semibold tracking-tight"
                    style={{
                      backgroundColor: indicatorStyles.backgroundColor,
                      borderColor: indicatorStyles.backgroundColor,
                      color: indicatorStyles.color,
                    }}
                  >
                    {bubbleValue}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      );
    }
    const text = (attemptSlot.answer_data?.text || '').trim();
    if (!text) {
      return <span className="text-muted-foreground">No answer submitted.</span>;
    }
    return <p className="whitespace-pre-wrap">{text}</p>;
  };

  return (
    <AppShell
      title={quiz ? quiz.title : 'Quiz workspace'}
      description="Configure quiz settings, manage problem slots, and review student responses."
      actions={
        <>
          <Button variant="outline" to="/dashboard">
            Dashboard
          </Button>
          {quiz && (
            <Button to={quizLink} target="_blank" rel="noreferrer">
              Preview
            </Button>
          )}
        </>
      }
    >
      {isLoadingQuiz ? (
        <div className="space-y-4">
          <div className="h-24 animate-pulse rounded-xl bg-muted" />
          <div className="h-24 animate-pulse rounded-xl bg-muted" />
          <div className="h-24 animate-pulse rounded-xl bg-muted" />
        </div>
      ) : !quiz ? (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="py-8 text-center text-destructive">
            <p className="text-lg font-semibold">Quiz not found</p>
            <p className="text-sm">This quiz may have been deleted or you don't have access.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {pageError && (
            <Card className="border-destructive/30 bg-destructive/5">
              <CardContent className="py-4 text-sm text-destructive">{pageError}</CardContent>
            </Card>
          )}

          {/* Status Banner */}
          <QuizStatusBanner
            readyForStudents={readyForStudents}
            schedulePreview={schedulePreview}
            slotReadiness={slotReadiness}
            attemptsSummary={attemptsSummary}
            handleCopyLink={handleCopyLink}
            copyMessage={copyMessage}
            statusKey={quizStatusKey}
          />

          {/* Tab Navigation */}
          <div className="border-b">
            <nav className="flex gap-6">
              {[
                { id: TABS.OVERVIEW, label: 'Overview', icon: '📋' },
                { id: TABS.SLOTS, label: 'Problem Slots', icon: '🎲', badge: slotReadiness.total },
                { id: TABS.RESPONSES, label: 'Responses', icon: '📝', badge: attempts.length },
                { id: TABS.INSTRUCTORS, label: 'Instructors', icon: '👥', badge: allowedInstructors.length },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    'flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition-colors',
                    activeTab === tab.id
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground'
                  )}
                >
                  <span>{tab.icon}</span>
                  <span>{tab.label}</span>
                  {tab.badge !== undefined && (
                    <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs">
                      {tab.badge}
                    </span>
                  )}
                </button>
              ))}
            </nav>
          </div>

          {/* Tab Content */}
          <div className="min-h-[400px]">
            {activeTab === TABS.OVERVIEW && (
              <QuizOverviewTab
                quiz={quiz}
                details={details}
                onDetailChange={handleDetailChange}
                onSaveDetails={handleSaveDetails}
                detailsSaving={detailsSaving}
                detailsError={detailsError}
                quizLink={quizLink}
                handleCopyLink={handleCopyLink}
                copyMessage={copyMessage}
                readyForStudents={readyForStudents}
                scheduleState={scheduleState}
                onOpenQuiz={handleOpenQuiz}
                onCloseQuiz={handleCloseQuiz}
                scheduleActionLoading={scheduleActionLoading}
                scheduleActionError={scheduleActionError}
              />
            )}

            {activeTab === TABS.SLOTS && (
              <QuizSlotsTab
                slots={slots}
                banks={banks}
                isLoadingBanks={isLoadingBanks}
                slotError={slotError}
                openSlotModal={openSlotModal}
                openSlotDetailModal={openSlotDetailModal}
                loadSlots={loadSlots}
              />
            )}

            {activeTab === TABS.RESPONSES && (
              <QuizResponsesTab
                attempts={attempts}
                attemptError={attemptError}
                loadAttempts={loadAttempts}
                openAttemptModal={openAttemptModal}
                requestAttemptDeletion={requestAttemptDeletion}
              />
            )}

            {activeTab === TABS.INSTRUCTORS && (
              <QuizAllowedInstructorsTab
                allowedInstructors={allowedInstructors}
                instructorId={instructorId}
                setInstructorId={setInstructorId}
                handleAddInstructor={handleAddInstructor}
                handleRemoveInstructor={handleRemoveInstructor}
                canManageCollaborators={canManageAllowedInstructors}
                loadInstructors={loadAllowedInstructors}
                instructorError={instructorError}
              />
            )}
          </div>

          {/* Quick Switch Sidebar */}
          {!isLoadingQuizzes && quizzes.length > 1 && (
            <Card className="mt-8">
              <CardHeader>
                <CardTitle className="text-base">Switch Quiz</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {quizzes.slice(0, 5).map((item) => (
                    <Button
                      key={item.id}
                      variant={quizIdNumber === item.id ? 'default' : 'outline'}
                      size="sm"
                      to={`/quizzes/${item.id}`}
                    >
                      {item.title}
                    </Button>
                  ))}
                  {quizzes.length > 5 && (
                    <Button variant="outline" size="sm" to="/dashboard">
                      View all
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
      <Modal
        open={Boolean(selectedAttempt)}
        onOpenChange={(open) => {
          if (!open) {
            closeAttemptModal();
          }
        }}
        title="Student attempt"
        description="View the answers recorded for every slot."
      >
        {selectedAttempt ? (
          <div className="space-y-4">
            <div className="rounded-md bg-muted/50 p-3 text-sm">
              <p>
                Attempt:{' '}
                <span className="font-semibold">
                  {selectedAttempt.student_identifier || 'Unknown student'}
                </span>
              </p>
              <p className="text-muted-foreground">
                Started {formatDateTime(selectedAttempt.started_at)}
                {selectedAttempt.completed_at ? ` · Completed ${formatDateTime(selectedAttempt.completed_at)}` : ' · In progress'}
              </p>
            </div>
            <div className="space-y-4">
              {(selectedAttempt.attempt_slots || []).map((slot) => {
                const slotLabel = slot.slot_label || 'Slot';
                const problemLabel = slot.problem_display_label || 'Problem';
                return (
                  <div key={slot.id} className="rounded-md border bg-background p-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-[11px] font-semibold uppercase tracking-[0.4em] text-muted-foreground">
                          {slotLabel}
                        </p>
                        <p className="text-sm font-semibold text-foreground">{problemLabel}</p>
                      </div>
                      {slot.problem_statement && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            setPreviewedProblem({
                              slotLabel,
                              problemLabel,
                              statement: slot.problem_statement,
                            })
                          }
                        >
                          Show problem
                        </Button>
                      )}
                    </div>
                    <div className="mt-3 rounded-md bg-muted/50 p-3 text-sm text-foreground">
                      {renderAttemptAnswer(slot)}
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={closeAttemptModal}>
                Close
              </Button>
              <Button
                variant="destructive"
                onClick={() => {
                  if (selectedAttempt) {
                    requestAttemptDeletion(selectedAttempt);
                  }
                  closeAttemptModal();
                }}
              >
                Delete attempt
              </Button>
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Loading attempt details…</p>
        )}
      </Modal>
      <Modal
        open={Boolean(previewedProblem)}
        onOpenChange={() => setPreviewedProblem(null)}
        title={previewedProblem?.problemLabel || 'Problem statement'}
        description={
          previewedProblem?.slotLabel ? `Slot ${previewedProblem.slotLabel}` : undefined
        }
        className="max-w-3xl"
      >
        {previewedProblem ? (
          previewStatementMarkup ? (
            <div
              className="prose max-w-none text-sm text-foreground"
              dangerouslySetInnerHTML={{ __html: previewStatementMarkup }}
            />
          ) : (
            <p className="text-sm text-muted-foreground">No statement is available for this problem.</p>
          )
        ) : (
          <p className="text-sm text-muted-foreground">Preparing problem details…</p>
        )}
      </Modal>
      <Modal
        open={Boolean(activeSlot)}
        onOpenChange={(open) => {
          if (!open) {
            closeSlotDetailModal();
          }
        }}
        title="Manage slot"
        description="Adjust the label, bank, response type, and selected problems."
      >
        {activeSlot ? (
          <form
            className="space-y-5"
            onSubmit={(event) => {
              event.preventDefault();
              handleSaveSlot(activeSlot);
            }}
          >
            <div className="space-y-2">
              <Label htmlFor="detail-slot-label">Label</Label>
              <Input
                id="detail-slot-label"
                value={activeSlot.label}
                onChange={(event) => handleSlotChange(activeSlot.id, 'label', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="detail-slot-bank">Problem bank</Label>
              <select
                id="detail-slot-bank"
                value={activeSlot.problem_bank ?? ''}
                onChange={(event) => handleSlotChange(activeSlot.id, 'problem_bank', event.target.value)}
                className="h-10 w-full rounded-md border px-3 text-sm"
                disabled={isLoadingBanks || !banks.length}
              >
                <option value="" disabled>
                  Select a bank
                </option>
                {banks.map((bank) => (
                  <option key={bank.id} value={bank.id}>
                    {bank.name}
                  </option>
                ))}
              </select>
              <p className="text-xs text-muted-foreground">
                Switching banks clears the selected slot problems. Save after making a change.
              </p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="detail-slot-response">Response type</Label>
              <select
                id="detail-slot-response"
                value={activeSlot.response_type || 'open_text'}
                onChange={(event) => handleSlotChange(activeSlot.id, 'response_type', event.target.value)}
                className="h-10 w-full rounded-md border px-3 text-sm"
              >
                {RESPONSE_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <p className="text-xs text-muted-foreground">Choose how students will respond in this slot.</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="detail-slot-instruction">Instructions for students</Label>
              <Textarea
                id="detail-slot-instruction"
                value={activeSlot.instruction ?? ''}
                onChange={(event) => handleSlotChange(activeSlot.id, 'instruction', event.target.value)}
                placeholder="Explain what students should include in their answer."
                className="min-h-[100px]"
              />
              <p className="text-xs text-muted-foreground">
                This guidance appears above the problem when students respond to the slot.
              </p>
            </div>
            {slotError && <p className="text-sm text-destructive">{slotError}</p>}
            <div className="space-y-2">
              {renderSlotProblems(activeSlot)}
            </div>
            <div className="flex justify-end gap-3">
              <Button type="button" variant="outline" onClick={closeSlotDetailModal}>
                Close
              </Button>
              <Button type="submit" variant="secondary" disabled={savingSlotId === activeSlot.id}>
                {savingSlotId === activeSlot.id ? 'Saving…' : 'Save slot'}
              </Button>
            </div>
          </form>
        ) : (
          <p className="text-sm text-muted-foreground">Loading slot details…</p>
        )}
      </Modal>
      <Modal
        open={Boolean(attemptToDelete)}
        onOpenChange={(open) => {
          if (!open) {
            closeAttemptDeleteModal();
          }
        }}
        title="Delete attempt"
        description="Are you sure you want to delete this attempt? This will remove the answers for every slot."
      >
        <div className="space-y-4">
          <div className="rounded-md bg-muted/50 p-3 text-sm">
            <p>
              Attempt:{' '}
              <span className="font-semibold">
                {attemptToDelete?.student_identifier || 'Unknown student'}
              </span>
            </p>
            <p className="text-muted-foreground">
              Started {attemptToDelete ? formatDateTime(attemptToDelete.started_at) : '—'}
            </p>
          </div>
          <p className="text-sm text-muted-foreground">
            This action cannot be undone and will delete all answers recorded for each problem slot in this attempt.
          </p>
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={closeAttemptDeleteModal} disabled={isDeletingAttempt}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteAttempt} disabled={isDeletingAttempt}>
              {isDeletingAttempt ? 'Deleting…' : 'Delete attempt'}
            </Button>
          </div>
        </div>
      </Modal>
      {isSlotModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 px-4 backdrop-blur-sm" onClick={closeSlotModal}>
          <div
            className="w-full max-w-lg rounded-2xl border bg-background p-6 shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-semibold">Add slot</h3>
                <p className="text-sm text-muted-foreground">Name the slot and choose which problem bank feeds it.</p>
              </div>
              <button type="button" className="text-sm text-muted-foreground hover:text-foreground" onClick={closeSlotModal}>
                Close
              </button>
            </div>
            <form className="space-y-5" onSubmit={handleCreateSlot}>
              <div className="space-y-2">
                <Label htmlFor="modal-slot-label">Label</Label>
                <Input
                  id="modal-slot-label"
                  name="label"
                  value={slotForm.label}
                  onChange={handleSlotFormChange}
                  placeholder="Intro problem"
                  autoFocus
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="modal-slot-bank">Problem bank</Label>
                <select
                  id="modal-slot-bank"
                  name="problem_bank"
                  value={slotForm.problem_bank}
                  onChange={handleSlotFormChange}
                  className="h-10 w-full rounded-md border px-3 text-sm"
                  disabled={isLoadingBanks || !banks.length}
                >
                  <option value="" disabled>
                    Select a bank
                  </option>
                  {banks.map((bank) => (
                    <option key={bank.id} value={bank.id}>
                      {bank.name}
                    </option>
                  ))}
                </select>
                {!isLoadingBanks && !banks.length && (
                  <p className="text-xs text-muted-foreground">Create a problem bank before adding slots.</p>
                )}
              </div>
              <div className="space-y-2">
                <Label htmlFor="modal-slot-response">Response type</Label>
                <select
                  id="modal-slot-response"
                  name="response_type"
                  value={slotForm.response_type}
                  onChange={handleSlotFormChange}
                  className="h-10 w-full rounded-md border px-3 text-sm"
                >
                  {RESPONSE_TYPE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="modal-slot-instruction">Instructions for students</Label>
                <Textarea
                  id="modal-slot-instruction"
                  name="instruction"
                  value={slotForm.instruction}
                  onChange={handleSlotFormChange}
                  placeholder="Explain how you expect students to approach this slot."
                  className="min-h-[100px]"
                />
                <p className="text-xs text-muted-foreground">
                  Optional guidance that students see while answering this slot.
                </p>
              </div>
              {slotFormError && <p className="text-sm text-destructive">{slotFormError}</p>}
              <div className="flex justify-end gap-3">
                <Button type="button" variant="outline" onClick={closeSlotModal}>
                  Cancel
                </Button>
                <Button type="submit" disabled={!canCreateSlot || isCreatingSlot}>
                  {isCreatingSlot ? 'Adding…' : 'Add slot'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </AppShell>
  );
};

export default QuizEditorPage;
