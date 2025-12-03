import React, { useMemo, useState, useRef } from 'react';
import { Trash2, Loader2, Upload, Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Link, useParams } from 'react-router-dom';
import { format } from 'date-fns';
import api from '@/lib/api';

const QuizResponsesTab = ({
  attempts,
  attemptError,
  loadAttempts,
  openAttemptModal,
  requestAttemptDeletion,
  onAddResponse,
}) => {
  const { quizId } = useParams();
  const fileInputRef = useRef(null);
  const [isImporting, setIsImporting] = useState(false);

  const handleDownloadTemplate = async () => {
    try {
      const response = await api.get(`/api/quizzes/${quizId}/import-template/`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `quiz_${quizId}_responses_template.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Failed to download template:', error);
      alert('Failed to download template.');
    }
  };

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsImporting(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await api.post(`/api/quizzes/${quizId}/import-responses/`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const { detail, errors } = response.data;
      let message = detail;
      if (errors && errors.length > 0) {
        message += '\n\nErrors:\n' + errors.join('\n');
      }
      alert(message);
      loadAttempts();
    } catch (error) {
      console.error('Import failed:', error);
      const detail = error.response?.data?.detail || 'Import failed.';
      alert(detail);
    } finally {
      setIsImporting(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Student Responses</h3>
          <p className="text-sm text-muted-foreground">
            View and manage all student attempts
          </p>
        </div>
        <div className="flex gap-2">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            className="hidden"
            accept=".xlsx, .xls"
          />
          <Button variant="outline" onClick={handleDownloadTemplate} title="Download Excel Template">
            <Download className="h-4 w-4 mr-2" />
            Template
          </Button>
          <Button variant="outline" onClick={handleImportClick} disabled={isImporting}>
            {isImporting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Upload className="h-4 w-4 mr-2" />}
            Import
          </Button>
          <Button variant="outline" onClick={onAddResponse}>
            Add Response
          </Button>
          <Button variant="outline" asChild>
            <Link to={`/quizzes/${quizId}/analytics`}>Analytics</Link>
          </Button>
          <Button variant="outline" onClick={loadAttempts}>Refresh</Button>
        </div>
      </div>

      {attemptError && (
        <div className="p-4 text-sm text-red-500 bg-red-50 rounded-md">
          {attemptError}
        </div>
      )}

      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Student Identifier</TableHead>
              <TableHead>Started At</TableHead>
              <TableHead>Completed At</TableHead>
              <TableHead className="w-[100px]">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {attempts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground">
                  No responses yet.
                </TableCell>
              </TableRow>
            ) : (
              attempts.map((attempt) => (
                <TableRow key={attempt.id}>
                  <TableCell className="font-medium">
                    {attempt.student_identifier}
                  </TableCell>
                  <TableCell>
                    {attempt.started_at
                      ? format(new Date(attempt.started_at), 'PP p')
                      : '-'}
                  </TableCell>
                  <TableCell>
                    {attempt.completed_at
                      ? format(new Date(attempt.completed_at), 'PP p')
                      : '-'}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openAttemptModal(attempt)}
                      >
                        View
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-destructive hover:text-destructive"
                        onClick={() => requestAttemptDeletion(attempt)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};

export default QuizResponsesTab;
