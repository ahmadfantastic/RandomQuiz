import React, { useEffect, useState } from 'react';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import AppShell from '@/components/layout/AppShell';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Modal } from '@/components/ui/modal';
import api from '@/lib/api';
import { cn } from '@/lib/utils';

const ProblemBankManager = () => {
  const [banks, setBanks] = useState([]);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [selectedBank, setSelectedBank] = useState(null);
  const [problemStatement, setProblemStatement] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [importName, setImportName] = useState('');
  const [importDescription, setImportDescription] = useState('');
  const [importFile, setImportFile] = useState(null);
  const [importError, setImportError] = useState('');
  const [isImporting, setIsImporting] = useState(false);
  const [openProblemId, setOpenProblemId] = useState(null);

  const loadBanks = () => {
    api.get('/api/problem-banks/').then((res) => setBanks(res.data));
  };

  const loadBankDetails = async (bankId) => {
    const res = await api.get(`/api/problem-banks/${bankId}/`);
    const problems = await api.get(`/api/problem-banks/${bankId}/problems/`);
    setSelectedBank({ ...res.data, problems: problems.data });
  };

  useEffect(() => {
    loadBanks();
  }, []);

  const handleCreateBank = async (event) => {
    event.preventDefault();
    if (!name.trim()) return;
    await api.post('/api/problem-banks/', { name, description });
    setName('');
    setDescription('');
    loadBanks();
    setIsCreateModalOpen(false);
  };

  const handleAddProblem = async (event) => {
    event.preventDefault();
    if (!selectedBank) return;
    await api.post(`/api/problem-banks/${selectedBank.id}/problems/`, {
      statement: problemStatement,
    });
    setProblemStatement('');
    loadBankDetails(selectedBank.id);
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

  return (
    <AppShell
      title="Problem banks"
      description="Organize reusable questions and keep your quizzes consistent by working from the same source."
    >
      <div className="sticky top-0 z-20 bg-background/50 backdrop-blur-sm px-4 lg:px-0 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-muted-foreground">Create and manage reusable problem libraries.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setIsImportModalOpen(true)}>
            Import from CSV
          </Button>
          <Button onClick={() => setIsCreateModalOpen(true)}>Create a bank</Button>
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-[360px,1fr]">
        <Card className="lg:min-h-[320px] lg:sticky lg:top-16 lg:self-start lg:max-h-[calc(100vh-4rem)] lg:overflow-auto">
          <CardHeader>
            <CardTitle>Your banks</CardTitle>
            <CardDescription>Select one to view or add problems.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {banks.length === 0 && <p className="text-sm text-muted-foreground">You have not created any banks yet.</p>}
            {banks.map((bank) => (
              <button
                key={bank.id}
                type="button"
                onClick={() => loadBankDetails(bank.id)}
                className={cn(
                  'flex w-full flex-col rounded-lg border px-4 py-3 text-left transition hover:border-primary hover:text-primary',
                  selectedBank?.id === bank.id && 'border-primary bg-primary/5 text-primary'
                )}
              >
                <span className="font-medium">{bank.name}</span>
                {bank.description && <span className="text-sm text-muted-foreground">{bank.description}</span>}
              </button>
            ))}
          </CardContent>
        </Card>
        <Card className="min-h-[400px] mt-6">
          <CardHeader>
            <CardTitle>{selectedBank ? selectedBank.name : 'Select a bank'}</CardTitle>
            <CardDescription>
              {selectedBank ? 'Review questions and add new problems below.' : 'Pick a bank from the list to review it here.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {selectedBank ? (
              <>
                {selectedBank.description && (
                  <div className="rounded-lg border bg-muted/40 p-4 text-sm text-muted-foreground">{selectedBank.description}</div>
                )}
                <div className="space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">Problems</p>
                  <div className="space-y-3">
                    {selectedBank.problems.length === 0 && (
                      <p className="text-sm text-muted-foreground">No problems yet. Add one using the form below.</p>
                    )}
                    {selectedBank.problems.map((problem, idx) => {
                      const label = problem.display_label || `Problem ${idx + 1}`;
                      const isOpen = openProblemId === problem.id;
                      const html = DOMPurify.sanitize(marked.parse(problem.statement || ''));
                      return (
                        <div key={problem.id} className="rounded-lg border">
                          <button
                            type="button"
                            className="w-full flex items-center justify-between px-4 py-3 text-left"
                            onClick={() => setOpenProblemId(isOpen ? null : problem.id)}
                            aria-expanded={isOpen}
                          >
                            <span className="text-sm font-semibold">{label}</span>
                            <svg
                              viewBox="0 0 20 20"
                              fill="none"
                              stroke="currentColor"
                              className={`h-4 w-4 transition-transform ${isOpen ? 'rotate-180' : 'rotate-0'}`}
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M5 8l5 5 5-5" />
                            </svg>
                          </button>
                          {isOpen && (
                            <div className="px-4 pb-4">
                              <div className="prose max-w-none text-sm" dangerouslySetInnerHTML={{ __html: html }} />
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
                <div className="space-y-4 rounded-lg border p-4">
                  <p className="text-sm font-medium">Add a new problem</p>
                  <form className="space-y-4" onSubmit={handleAddProblem}>
                    <div className="space-y-2">
                      <Label htmlFor="problem-statement">Statement</Label>
                      <Textarea
                        id="problem-statement"
                        value={problemStatement}
                        onChange={(e) => setProblemStatement(e.target.value)}
                        placeholder="Describe the problem to students..."
                      />
                    </div>
                    <Button type="submit" disabled={!problemStatement.trim()}>
                      Add problem
                    </Button>
                  </form>
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">Choose a problem bank from the left to start managing its questions.</p>
            )}
          </CardContent>
        </Card>
      </div>
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
    </AppShell>
  );
};

export default ProblemBankManager;
