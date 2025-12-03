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

    const handleImport = async (e) => {
        e.preventDefault();
        if (!file) {
            setError('Please select a CSV file.');
            return;
        }

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
            onOpenChange={onOpenChange}
            title="Import Ratings"
            description="Upload a CSV file with 'order' and columns matching criterion IDs."
        >
            <form onSubmit={handleImport} className="space-y-4">
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
                        Columns: <code>order</code>, <code>[criterion_id]</code>...
                    </p>
                </div>
                {error && <p className="text-sm text-destructive">{error}</p>}
                {result && <p className="text-sm text-green-600">{result}</p>}
                <div className="flex justify-end gap-2">
                    <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
                        Cancel
                    </Button>
                    <Button type="submit" disabled={isImporting || !file}>
                        {isImporting ? 'Importing...' : 'Import Ratings'}
                    </Button>
                </div>
            </form>
        </Modal>
    );
};

export default ImportRatingsModal;
