import React, { useEffect, useRef, useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { DndContext, useDraggable, useDroppable } from '@dnd-kit/core';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { ChevronDown, GripVertical } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Modal } from '@/components/ui/modal';
import api from '@/lib/api';
import useProblemStatements from '@/lib/useProblemStatements';
import MDEditor from '@uiw/react-md-editor';
import '@uiw/react-markdown-preview/markdown.css';
import '@uiw/react-md-editor/markdown-editor.css';
import { cn } from '@/lib/utils';
import AppShell from '@/components/layout/AppShell';
import ProblemBankRubricEditor from '@/components/problem-bank/ProblemBankRubricEditor';
import RatingModal from '@/components/problem-bank/RatingModal';
import ImportRatingsModal from '@/components/problem-bank/ImportRatingsModal';
import RubricManagerModal from '@/components/problem-bank/RubricManagerModal';

const ProblemListPlaceholder = () => (
  <div className="space-y-3 animate-pulse">
    {[1, 2, 3].map((placeholder) => (
      <div
        key={placeholder}
        className="rounded-lg border border-border bg-muted/10 px-4 py-3"
      >
        <div className="h-4 w-1/3 rounded-full bg-muted/40" />
        <div className="mt-3 space-y-2">
          <div className="h-2 rounded bg-muted/20" />
          <div className="h-2 w-3/4 rounded bg-muted/20" />
        </div>
      </div>
    ))}
  </div>
);

const ProblemItem = ({
  problem,
  isOpen,
  onToggle,
  onEdit,
  onDelete,
  onRate,
  statementEntry,
  isDeleting,
  canEdit,
}) => {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({
    id: `problem-${problem.id}`,
    data: { problem },
    disabled: !canEdit,
  });

  const style = transform
    ? {
      transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
      zIndex: 50,
    }
    : undefined;

  const label = problem.display_label || `Problem ${problem.id}`;
  const hasStatementEntry = statementEntry && 'statement' in statementEntry;
  const rawStatement = hasStatementEntry ? statementEntry.statement : '';
  const hasStatementText = rawStatement?.trim();
  const statementMarkupHtml = hasStatementText
    ? DOMPurify.sanitize(marked.parse(rawStatement))
    : '';
  const isLoadingStatement = !statementEntry || Boolean(statementEntry.loading);
  const statementError = statementEntry?.error;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="rounded-lg border bg-card text-card-foreground shadow-sm"
    >
      <div className="flex items-center">
        {canEdit && (
          <div
            {...listeners}
            {...attributes}
            className="cursor-grab px-3 py-3 text-muted-foreground hover:text-foreground"
          >
            <GripVertical className="h-4 w-4" />
          </div>
        )}
        <button
          type="button"
          className="flex-1 flex items-center justify-between px-2 py-3 text-left"
          onClick={() => onToggle(problem.id)}
          aria-expanded={isOpen}
        >
          <span className="text-sm font-semibold">{label}</span>
          <ChevronDown
            className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : 'rotate-0'}`}
          />
        </button>
      </div>
      {isOpen && (
        <div className="px-4 pb-4 space-y-3 border-t pt-3">
          {isLoadingStatement ? (
            <p className="text-sm text-muted-foreground">Loading problem markup…</p>
          ) : statementError ? (
            <p className="text-sm text-destructive">{statementError}</p>
          ) : statementMarkupHtml ? (
            <div
              className="prose max-w-none text-sm markup-content"
              dangerouslySetInnerHTML={{ __html: statementMarkupHtml }}
            />
          ) : (
            <p className="text-sm text-muted-foreground">No problem statement provided.</p>
          )}
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onRate(problem.id, label)}
            >
              Rate
            </Button>
            {canEdit && (
              <>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={isLoadingStatement}
                  onClick={() => onEdit(problem.id)}
                >
                  Edit
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  disabled={isLoadingStatement || isDeleting}
                  onClick={() => onDelete(problem.id)}
                >
                  {isDeleting ? 'Deleting…' : 'Delete'}
                </Button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const ProblemGroup = ({ group, children, canEdit }) => {
  const { setNodeRef, isOver } = useDroppable({
    id: `group-${group || 'ungrouped'}`,
    data: { group },
    disabled: !canEdit,
  });

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-1">
        {group || 'Ungrouped Problems'}
      </h3>
      <div
        ref={setNodeRef}
        className={cn(
          'space-y-3 min-h-[50px] rounded-lg border-2 border-dashed p-2 transition-colors',
          isOver ? 'border-primary/50 bg-primary/5' : 'border-transparent'
        )}
      >
        {children}
      </div>
    </div>
  );
};

const ProblemBankManager = () => {
  const [banks, setBanks] = useState([]);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [selectedBank, setSelectedBank] = useState(null);
  const [problemStatement, setProblemStatement] = useState('');
  const [problemGroup, setProblemGroup] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isAddGroupModalOpen, setIsAddGroupModalOpen] = useState(false);
  const [newGroupName, setNewGroupName] = useState('');
  const [temporaryGroups, setTemporaryGroups] = useState([]);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [importName, setImportName] = useState('');
  const [importDescription, setImportDescription] = useState('');
  const [importFile, setImportFile] = useState(null);
  const [importError, setImportError] = useState('');
  const [isImporting, setIsImporting] = useState(false);
  const [openProblemId, setOpenProblemId] = useState(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingProblemId, setEditingProblemId] = useState(null);
  const [editingStatement, setEditingStatement] = useState('');
  const [editingGroup, setEditingGroup] = useState('');
  const [isSavingEdit, setIsSavingEdit] = useState(false);
  const [editError, setEditError] = useState('');
  const editStatementSyncedRef = useRef(false);
  const { statements: problemStatements, loadStatement: loadProblemStatement, resetStatements } =
    useProblemStatements();
  const [problemActionError, setProblemActionError] = useState('');
  const [bankListError, setBankListError] = useState('');
  const [isLoadingBanks, setIsLoadingBanks] = useState(true);
  const [isBankDetailsLoading, setIsBankDetailsLoading] = useState(false);
  const [deletingProblems, setDeletingProblems] = useState({});
  const canEditSelectedBank = Boolean(selectedBank?.is_owner);
  const selectedBankOwnerLabel = selectedBank?.owner_username || 'the owner';
  const [isRubricModalOpen, setIsRubricModalOpen] = useState(false);
  const [isImportRatingsModalOpen, setIsImportRatingsModalOpen] = useState(false);
  const [ratingModalState, setRatingModalState] = useState({ open: false, problemId: null, problemLabel: '' });

  // New state for rubric management
  const [rubricId, setRubricId] = useState('');
  const [availableRubrics, setAvailableRubrics] = useState([]);
  const [isRubricManagerOpen, setIsRubricManagerOpen] = useState(false);

  const loadBanks = async () => {
    setIsLoadingBanks(true);
    setBankListError('');
    try {
      const res = await api.get('/api/problem-banks/');
      setBanks(res.data);
    } catch (error) {
      const detail = error.response?.data?.detail || 'Unable to load problem banks right now.';
      setBankListError(detail);
      setBanks([]);
    } finally {
      setIsLoadingBanks(false);
    }
  };

  const loadRubrics = async () => {
    try {
      const res = await api.get('/api/rubrics/');
      setAvailableRubrics(res.data);
    } catch (error) {
      console.error('Failed to load rubrics', error);
    }
  };

  const loadBankDetails = async (bankId, bankMeta = null) => {
    setProblemActionError('');
    resetStatements();
    setOpenProblemId(null);
    setIsBankDetailsLoading(true);
    if (bankMeta) {
      setSelectedBank((prev) => (prev?.id === bankId ? prev : { ...bankMeta, problems: [] }));
    }
    try {
      const res = await api.get(`/api/problem-banks/${bankId}/`);
      const problems = await api.get(`/api/problem-banks/${bankId}/problems/`);
      setSelectedBank({ ...res.data, problems: problems.data });
    } catch (error) {
      const detail = error.response?.data?.detail || 'Unable to load this bank right now.';
      setProblemActionError(detail);
    } finally {
      setIsBankDetailsLoading(false);
    }
  };

  const handleProblemToggle = (problemId) => {
    const nextId = openProblemId === problemId ? null : problemId;
    setOpenProblemId(nextId);
    if (
      nextId &&
      !problemStatements[nextId]?.statement &&
      !problemStatements[nextId]?.loading
    ) {
      loadProblemStatement(nextId);
    }
  };

  useEffect(() => {
    loadBanks();
    loadRubrics();
  }, []);

  useEffect(() => {
    if (!editingProblemId) {
      editStatementSyncedRef.current = false;
      return;
    }
    if (editStatementSyncedRef.current) {
      return;
    }
    const entry = problemStatements[editingProblemId];
    if (!entry || entry.loading) {
      return;
    }
    if (!Object.prototype.hasOwnProperty.call(entry, 'statement')) {
      return;
    }
    setEditingStatement(entry.statement ?? '');
    setEditingGroup(entry.group ?? '');
    editStatementSyncedRef.current = true;
  }, [editingProblemId, problemStatements]);

  const handleCreateBank = async (event) => {
    event.preventDefault();
    if (!name.trim()) return;
    await api.post('/api/problem-banks/', { name, description, rubric_id: rubricId || null });
    setName('');
    setDescription('');
    setRubricId('');
    loadBanks();
    setIsCreateModalOpen(false);
  };

  const handleAddProblem = async (event) => {
    event.preventDefault();
    if (!selectedBank) return;
    if (!selectedBank.is_owner) {
      setProblemActionError(`Only ${selectedBankOwnerLabel} can add problems to this bank.`);
      return;
    }
    await api.post(`/api/problem-banks/${selectedBank.id}/problems/`, {
      statement: problemStatement,
      group: problemGroup.trim() || null,
    });
    setProblemStatement('');
    setProblemGroup('');
    loadBankDetails(selectedBank.id, selectedBank);
  };

  const closeEditModal = () => {
    setIsEditModalOpen(false);
    setEditingProblemId(null);
    setEditingStatement('');
    setEditingGroup('');
    setEditError('');
    editStatementSyncedRef.current = false;
  };

  const handleOpenEditModal = (problemId) => {
    setEditingProblemId(problemId);
    setIsEditModalOpen(true);
    setEditError('');
    setEditingStatement('');
    setEditingGroup('');
    editStatementSyncedRef.current = false;
    const entry = problemStatements[problemId];
    const hasStatementLoaded = entry && Object.prototype.hasOwnProperty.call(entry, 'statement');
    if (!hasStatementLoaded && !entry?.loading) {
      loadProblemStatement(problemId);
    }
  };

  const handleSaveEdit = async (event) => {
    event.preventDefault();
    if (!editingProblemId) return;
    setIsSavingEdit(true);
    setEditError('');
    try {
      await api.patch(`/api/problems/${editingProblemId}/`, {
        statement: editingStatement,
        group: editingGroup.trim() || null,
      });
      await loadProblemStatement(editingProblemId);
      setOpenProblemId(editingProblemId);
      closeEditModal();
    } catch (error) {
      const detail = error.response?.data?.detail || 'Unable to update this problem right now.';
      setEditError(detail);
    } finally {
      setIsSavingEdit(false);
    }
  };

  const handleDeleteProblem = async (problemId) => {
    if (
      !window.confirm(
        'Are you sure you want to delete this problem? This action cannot be undone.'
      )
    ) {
      return;
    }
    if (editingProblemId === problemId) {
      closeEditModal();
    }
    setProblemActionError('');
    setDeletingProblems((prev) => ({ ...prev, [problemId]: true }));
    try {
      await api.delete(`/api/problems/${problemId}/`);
      if (selectedBank) {
        await loadBankDetails(selectedBank.id, selectedBank);
      }
    } catch (error) {
      const detail = error.response?.data?.detail || 'Unable to delete this problem right now.';
      setProblemActionError(detail);
    } finally {
      setDeletingProblems((prev) => {
        const next = { ...prev };
        delete next[problemId];
        return next;
      });
    }
  };

  const handleOpenRatingModal = (problemId, label) => {
    setRatingModalState({ open: true, problemId, problemLabel: label });
  };

  const resetImportForm = () => {
    setImportName('');
    setImportDescription('');
    setImportFile(null);
    setImportError('');
    setIsImporting(false);
  };

  const handleImportModalChange = (open) => {
    setIsImportModalOpen(open);
    if (!open) {
      resetImportForm();
    }
  };

  const handleImportBank = async (event) => {
    event.preventDefault();
    if (!importName.trim()) {
      setImportError('Provide a name for the bank.');
      return;
    }
    if (!importFile) {
      setImportError('Select a CSV file to import.');
      return;
    }
    setIsImporting(true);
    setImportError('');
    const formData = new FormData();
    formData.append('name', importName.trim());
    formData.append('description', importDescription);
    formData.append('file', importFile);
    try {
      await api.post('/api/problem-banks/import/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      loadBanks();
      setIsImportModalOpen(false);
      resetImportForm();
    } catch (error) {
      const detail = error.response?.data?.detail || 'Unable to import the bank from CSV.';
      setImportError(detail);
    } finally {
      setIsImporting(false);
    }
  };

  const editingProblemEntry = editingProblemId ? problemStatements[editingProblemId] : null;
  const isEditingStatementLoading = Boolean(
    editingProblemId && (!editingProblemEntry || editingProblemEntry.loading)
  );
  const editingStatementLoadError = editingProblemEntry?.error;
  const bankCardTitle = isBankDetailsLoading
    ? 'Loading Bank…'
    : selectedBank
      ? selectedBank.name
      : 'Select a Bank';
  const bankCardDescription = isBankDetailsLoading
    ? 'Fetching problems for the selected bank…'
    : selectedBank
      ? canEditSelectedBank
        ? 'Review questions and add new problems below.'
        : `Only ${selectedBankOwnerLabel} can edit this bank. You can review the problems here.`
      : 'Pick a bank from the list to review it here.';
  const selectedBankProblems = selectedBank?.problems ?? [];

  const groupedProblems = useMemo(() => {
    const groups = {};
    groups[''] = [];
    selectedBankProblems.forEach((p) => {
      const g = p.group || '';
      if (!groups[g]) groups[g] = [];
      groups[g].push(p);
    });
    temporaryGroups.forEach((g) => {
      if (!groups[g]) groups[g] = [];
    });
    return groups;
  }, [selectedBankProblems, temporaryGroups]);

  const handleAddGroup = (e) => {
    e.preventDefault();
    if (!newGroupName.trim()) return;
    setTemporaryGroups((prev) => [...prev, newGroupName.trim()]);
    setNewGroupName('');
    setIsAddGroupModalOpen(false);
  };

  const handleDragEnd = async (event) => {
    const { active, over } = event;
    if (!over) return;

    const problemId = active.data.current?.problem?.id;
    const targetGroup = over.data.current?.group;

    if (!problemId) return;

    const problem = selectedBankProblems.find((p) => p.id === problemId);
    if (problem && (problem.group || '') === (targetGroup || '')) return;

    try {
      await api.patch(`/api/problems/${problemId}/`, { group: targetGroup || null });
      loadBankDetails(selectedBank.id, selectedBank);
    } catch (error) {
      console.error('Failed to move problem', error);
      setProblemActionError('Failed to move problem to new group.');
    }
  };

  return (
    <AppShell
      title="Problem banks"
      description="Organize reusable questions while browsing every instructor's bank; only owners can edit their content."
    >
      <div className="sticky top-0 z-20 bg-background/50 backdrop-blur-sm px-4 lg:px-0 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-muted-foreground">Create and manage reusable problem libraries.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setIsRubricManagerOpen(true)}>
            Manage Rubrics
          </Button>
          <Button variant="outline" onClick={() => setIsImportModalOpen(true)}>
            Import from CSV
          </Button>
          <Button onClick={() => setIsCreateModalOpen(true)}>Create a bank</Button>
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-[360px,1fr]">
        <Card className="lg:min-h-[320px] lg:sticky lg:top-16 lg:self-start lg:max-h-[calc(100vh-4rem)] lg:overflow-auto">
          <CardHeader>
            <CardTitle>Problem banks</CardTitle>
            <CardDescription>Browse every bank in your workspace; only the owner can edit its problems.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {bankListError && <p className="text-sm text-destructive">{bankListError}</p>}
            {isLoadingBanks ? (
              <div className="space-y-3">
                {[1, 2, 3].map((placeholder) => (
                  <div
                    key={placeholder}
                    className="h-16 animate-pulse rounded-lg border border-dashed border-muted bg-muted/30"
                  />
                ))}
              </div>
            ) : (
              <>
                {banks.length === 0 && (
                  <p className="text-sm text-muted-foreground">No problem banks yet. Create one to get started.</p>
                )}
                {banks.map((bank) => {
                  const ownerLabel = bank.is_owner
                    ? 'You own this bank'
                    : `Owned by ${bank.owner_username || 'another instructor'}`;
                  return (
                    <button
                      key={bank.id}
                      type="button"
                      onClick={() => loadBankDetails(bank.id, bank)}
                      className={cn(
                        'flex w-full flex-col rounded-lg border px-4 py-3 text-left transition hover:border-primary hover:text-primary',
                        selectedBank?.id === bank.id && 'border-primary bg-primary/5 text-primary'
                      )}
                    >
                      <div className="flex flex-col gap-0.5">
                        <span className="font-medium">{bank.name}</span>
                        {bank.description && (
                          <span className="text-sm text-muted-foreground">{bank.description}</span>
                        )}
                        <span className="text-xs text-muted-foreground">{ownerLabel}</span>
                      </div>
                    </button>
                  );
                })}
              </>
            )}
          </CardContent>
        </Card>
        <Card className="min-h-[400px] mt-6">
          <CardHeader>
            <CardTitle>{bankCardTitle}</CardTitle>
            <CardDescription>{bankCardDescription}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {problemActionError && (
              <p className="text-sm text-destructive">{problemActionError}</p>
            )}
            {!selectedBank && isBankDetailsLoading ? (
              <div className="space-y-4 animate-pulse">
                <div className="h-4 w-3/4 rounded-full bg-muted/40" />
                <div className="h-3 w-1/2 rounded-full bg-muted/30" />
                <div className="space-y-3">
                  {[1, 2, 3].map((placeholder) => (
                    <div key={placeholder} className="rounded-lg border px-4 py-3">
                      <div className="h-4 w-1/3 rounded-full bg-muted/40" />
                      <div className="mt-3 space-y-2">
                        <div className="h-2 rounded bg-muted/20" />
                        <div className="h-2 w-3/4 rounded bg-muted/20" />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="space-y-2 rounded-lg border p-4">
                  <div className="h-4 w-1/3 rounded-full bg-muted/40" />
                  <div className="mt-3 space-y-2">
                    <div className="h-3 rounded bg-muted/30" />
                    <div className="h-24 rounded bg-muted/10" />
                  </div>
                  <div className="mt-4 h-10 w-32 rounded-full bg-muted/30" />
                </div>
              </div>
            ) : selectedBank ? (
              <>
                {selectedBank.description && (
                  <div className="rounded-lg border bg-muted/40 p-4 text-sm text-muted-foreground">
                    {selectedBank.description}
                  </div>
                )}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-muted-foreground">Problems</p>
                    {canEditSelectedBank && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 text-xs"
                        onClick={() => setIsAddGroupModalOpen(true)}
                      >
                        + Add Group
                      </Button>
                    )}
                    {canEditSelectedBank && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 text-xs ml-2"
                        onClick={() => setIsRubricModalOpen(true)}
                      >
                        Edit Rubric
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 text-xs ml-2"
                      onClick={() => setIsImportRatingsModalOpen(true)}
                    >
                      Import Ratings
                    </Button>
                    <Link to={`/problem-banks/${selectedBank.id}/analysis`}>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 text-xs ml-2"
                      >
                        Analysis
                      </Button>
                    </Link>
                  </div>
                  {!canEditSelectedBank && (
                    <p className="text-xs text-muted-foreground">
                      This bank is read-only. Only {selectedBankOwnerLabel} can manage its problems.
                    </p>
                  )}
                  <div className="space-y-3">
                    {isBankDetailsLoading ? (
                      <ProblemListPlaceholder />
                    ) : selectedBankProblems.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No problems yet. Add one using the form below.</p>
                    ) : (
                      <DndContext onDragEnd={handleDragEnd}>
                        <div className="space-y-6">
                          {Object.entries(groupedProblems)
                            .sort((a, b) => {
                              if (a[0] === '') return -1;
                              if (b[0] === '') return 1;
                              return a[0].localeCompare(b[0]);
                            })
                            .map(([groupName, problems]) => (
                              <ProblemGroup
                                key={groupName}
                                group={groupName}
                                canEdit={canEditSelectedBank}
                              >
                                {problems.map((problem) => (
                                  <ProblemItem
                                    key={problem.id}
                                    problem={problem}
                                    isOpen={openProblemId === problem.id}
                                    onToggle={handleProblemToggle}
                                    onEdit={handleOpenEditModal}
                                    onDelete={handleDeleteProblem}
                                    onRate={handleOpenRatingModal}
                                    statementEntry={problemStatements[problem.id]}
                                    isDeleting={Boolean(deletingProblems[problem.id])}
                                    canEdit={canEditSelectedBank}
                                  />
                                ))}
                              </ProblemGroup>
                            ))}
                        </div>
                      </DndContext>
                    )}
                  </div>
                </div>
                {isBankDetailsLoading ? (
                  <div className="space-y-2 rounded-lg border p-4">
                    <div className="h-4 w-2/5 rounded-full bg-muted/40" />
                    <div className="mt-3 space-y-2">
                      <div className="h-3 rounded bg-muted/30" />
                      <div className="h-24 rounded bg-muted/10" />
                    </div>
                    <div className="mt-4 h-10 w-32 rounded-full bg-muted/30" />
                  </div>
                ) : canEditSelectedBank ? (
                  <div className="space-y-4 rounded-lg border p-4">
                    <p className="text-sm font-medium">Add a new problem</p>
                    <form className="space-y-4" onSubmit={handleAddProblem}>
                      <div className="space-y-2">
                        <Label htmlFor="problem-statement">Statement (Markdown)</Label>
                        <div id="problem-statement">
                          <MDEditor
                            value={problemStatement}
                            onChange={(value) => setProblemStatement(value ?? '')}
                            height={240}
                            preview="edit"
                          />
                        </div>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="problem-group">Group (Optional)</Label>
                        <Input
                          id="problem-group"
                          value={problemGroup}
                          onChange={(e) => setProblemGroup(e.target.value)}
                          placeholder="e.g. Multiple Choice, Section A"
                        />
                      </div>
                      <Button type="submit" disabled={!problemStatement.trim()}>
                        Add problem
                      </Button>
                    </form>
                  </div>
                ) : (
                  <div className="space-y-2 rounded-lg border p-4">
                    <p className="text-sm font-medium">Read-only bank</p>
                    <p className="text-sm text-muted-foreground">
                      Only {selectedBankOwnerLabel} can add or edit problems in this bank.
                    </p>
                  </div>
                )}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                Choose a problem bank from the left to start managing its questions.
              </p>
            )}
          </CardContent>
        </Card>
      </div >
      <Modal
        open={isCreateModalOpen}
        onOpenChange={setIsCreateModalOpen}
        title="Create a bank"
        description="Add its name and short description before adding problems."
      >
        <form className="space-y-4" onSubmit={handleCreateBank}>
          <div className="space-y-2">
            <Label htmlFor="bank-name">Name</Label>
            <Input id="bank-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Exams 2024" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="bank-description">Description</Label>
            <Textarea
              id="bank-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What makes this bank different?"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="bank-rubric">Rubric (Optional)</Label>
            <select
              id="bank-rubric"
              className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              value={rubricId}
              onChange={(e) => setRubricId(e.target.value)}
            >
              <option value="">No Rubric</option>
              {availableRubrics.map(r => (
                <option key={r.id} value={r.id}>{r.name}</option>
              ))}
            </select>
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!name.trim()}>
              Save bank
            </Button>
          </div>
        </form>
      </Modal>
      <Modal
        open={isImportModalOpen}
        onOpenChange={handleImportModalChange}
        title="Import from CSV"
        description="Upload a CSV with 'order' and 'problem' columns to create a pre-filled bank."
      >
        <form className="space-y-4" onSubmit={handleImportBank}>
          <div className="space-y-2">
            <Label htmlFor="import-name">Name</Label>
            <Input id="import-name" value={importName} onChange={(e) => setImportName(e.target.value)} placeholder="Practice set" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="import-description">Description</Label>
            <Textarea
              id="import-description"
              value={importDescription}
              onChange={(e) => setImportDescription(e.target.value)}
              placeholder="What is included in this bank?"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="import-file">CSV file</Label>
            <Input
              id="import-file"
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => {
                const file = event.target.files?.[0];
                setImportFile(file || null);
                setImportError('');
              }}
            />
            <p className="text-xs text-muted-foreground">The CSV must have "order" and "problem" headers.</p>
          </div>
          {importError && <p className="text-sm text-destructive">{importError}</p>}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => handleImportModalChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isImporting || !importName.trim() || !importFile}>
              {isImporting ? 'Importing…' : 'Import bank'}
            </Button>
          </div>
        </form>
      </Modal>
      <Modal
        open={isEditModalOpen}
        onOpenChange={(open) => {
          if (!open) {
            closeEditModal();
          }
        }}
        title="Edit problem"
        description="Update the Markdown statement for this problem."
      >
        <form className="space-y-4" onSubmit={handleSaveEdit}>
          {editError && <p className="text-sm text-destructive">{editError}</p>}
          {editingStatementLoadError && (
            <p className="text-sm text-destructive">{editingStatementLoadError}</p>
          )}
          <div className="space-y-2">
            <Label htmlFor="edit-problem-statement">Statement (Markdown)</Label>
            <div id="edit-problem-statement">
              {isEditingStatementLoading ? (
                <p className="text-sm text-muted-foreground">Loading current statement…</p>
              ) : (
                <MDEditor
                  value={editingStatement}
                  onChange={(value) => setEditingStatement(value ?? '')}
                  height={240}
                  preview="edit"
                />
              )}
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="edit-problem-group">Group (Optional)</Label>
            <Input
              id="edit-problem-group"
              value={editingGroup}
              onChange={(e) => setEditingGroup(e.target.value)}
              placeholder="e.g. Multiple Choice, Section A"
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={closeEditModal}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSavingEdit || isEditingStatementLoading}>
              {isSavingEdit ? 'Saving…' : 'Save changes'}
            </Button>
          </div>
        </form>
      </Modal>
      <Modal
        open={isAddGroupModalOpen}
        onOpenChange={setIsAddGroupModalOpen}
        title="Add a group"
        description="Create a new group to organize your problems."
      >
        <form className="space-y-4" onSubmit={handleAddGroup}>
          <div className="space-y-2">
            <Label htmlFor="new-group-name">Group Name</Label>
            <Input
              id="new-group-name"
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
              placeholder="e.g. Section B"
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setIsAddGroupModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={!newGroupName.trim()}>
              Add Group
            </Button>
          </div>
        </form>
      </Modal>
      <ProblemBankRubricEditor
        open={isRubricModalOpen}
        onOpenChange={setIsRubricModalOpen}
        bankId={selectedBank?.id}
      />
      <RatingModal
        open={ratingModalState.open}
        onOpenChange={(open) => setRatingModalState(prev => ({ ...prev, open }))}
        problemId={ratingModalState.problemId}
        bankId={selectedBank?.id}
        problemLabel={ratingModalState.problemLabel}
      />
      <ImportRatingsModal
        open={isImportRatingsModalOpen}
        onOpenChange={setIsImportRatingsModalOpen}
        bankId={selectedBank?.id}
        onImportSuccess={() => loadBankDetails(selectedBank?.id, selectedBank)}
      />
      <RubricManagerModal
        open={isRubricManagerOpen}
        onOpenChange={setIsRubricManagerOpen}
        onRubricCreated={loadRubrics}
      />
    </AppShell >
  );
};

export default ProblemBankManager;
