import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Modal } from '@/components/ui/modal';
import api from '@/lib/api';

const ImportRatingsModal = ({ open, onOpenChange, bankId, onImportSuccess }) => {
    const [file, setFile] = useState(null);
    const [isImporting, setIsImporting] = useState(false);
    const [error, setError] = useState('');
    const [result, setResult] = useState('');

    const [previewData, setPreviewData] = useState(null);

    const handlePreview = async () => {
        if (!file) {
            setError('Please select a CSV file.');
            return;
        }

        setIsImporting(true);
        setError('');
        setResult('');

        const formData = new FormData();
        formData.append('file', file);
        formData.append('preview', 'true');

        try {
            const res = await api.post(`/api/problem-banks/${bankId}/import-ratings/`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            setPreviewData(res.data);
        } catch (err) {
            const detail = err.response?.data?.detail || 'Failed to preview file.';
            setError(detail);
        } finally {
            setIsImporting(false);
        }
    };

    const handleImport = async () => {
        if (!file) return;

        setIsImporting(true);
        setError('');
        setResult('');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await api.post(`/api/problem-banks/${bankId}/import-ratings/`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            setResult(res.data.detail);
            if (onImportSuccess) onImportSuccess();
            setTimeout(() => {
                onOpenChange(false);
                setFile(null);
                setResult('');
                setPreviewData(null);
            }, 2000);
        } catch (err) {
            const detail = err.response?.data?.detail || 'Failed to import ratings.';
            setError(detail);
        } finally {
            setIsImporting(false);
        }
    };

    return (
        <Modal
            open={open}
            onOpenChange={(val) => {
                onOpenChange(val);
                if (!val) {
                    setFile(null);
                    setPreviewData(null);
                    setError('');
                    setResult('');
                }
            }}
            title="Import Ratings"
            description="Upload a CSV file with a 'Problem' column, and other columns matching criterion IDs or names."
            className="max-w-3xl"
        >
            <div className="space-y-4">
                {!previewData ? (
                    <div className="space-y-2">
                        <Label htmlFor="ratings-file">CSV File</Label>
                        <Input
                            id="ratings-file"
                            type="file"
                            accept=".csv,text/csv"
                            onChange={(e) => {
                                setFile(e.target.files?.[0] || null);
                                setError('');
                                setResult('');
                            }}
                        />
                        <p className="text-xs text-muted-foreground">
                            Columns: <code>Problem</code>, <code>[criterion_name_or_id]</code>...
                        </p>
                    </div>
                ) : (
                    <div className="space-y-2">
                        <h3 className="font-medium">Preview (First 5 rows)</h3>
                        <div className="border rounded-md overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead className="bg-muted">
                                    <tr>
                                        {previewData.headers.map((h, i) => (
                                            <th key={i} className="px-3 py-2 text-left font-medium">{h}</th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {previewData.rows.map((row, i) => (
                                        <tr key={i} className="border-t">
                                            {previewData.headers.map((h, j) => (
                                                <td key={j} className="px-3 py-2">{row[h]}</td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        <p className="text-xs text-muted-foreground">
                            Please verify the columns match your expectations.
                        </p>
                    </div>
                )}

                {error && <p className="text-sm text-destructive">{error}</p>}
                {result && <p className="text-sm text-green-600">{result}</p>}

                <div className="flex justify-end gap-2">
                    <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    {!previewData ? (
                        <Button type="button" onClick={handlePreview} disabled={isImporting || !file}>
                            {isImporting ? 'Loading...' : 'Preview'}
                        </Button>
                    ) : (
                        <>
                            <Button type="button" variant="outline" onClick={() => setPreviewData(null)} disabled={isImporting}>
                                Back
                            </Button>
                            <Button type="button" onClick={handleImport} disabled={isImporting}>
                                {isImporting ? 'Importing...' : 'Confirm Import'}
                            </Button>
                        </>
                    )}
                </div>
            </div>
        </Modal>
    );
};

export default ImportRatingsModal;
