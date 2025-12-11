import React from 'react';
import { useParams } from 'react-router-dom';
import { Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import api from '@/lib/api';
import AllSlotInteractions from './AllSlotInteractions';

const InteractionAnalytics = ({ data }) => {
    const { quizId } = useParams();

    const handleDownloadCSV = async () => {
        try {
            const response = await api.get(`/api/quizzes/${quizId}/analytics/interactions/`, {
                params: { download: 'csv' },
                responseType: 'blob',
            });

            // Try to get filename from header
            const contentDisposition = response.headers['content-disposition'];
            let filename = `quiz-${quizId}-interactions.csv`;
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
                if (filenameMatch && filenameMatch.length === 2)
                    filename = filenameMatch[1];
            }

            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', filename);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (error) {
            console.error('Failed to download CSV', error);
        }
    };

    if (!data || data.length === 0) {
        return (
            <div className="flex h-64 items-center justify-center rounded-lg border border-dashed p-8 text-center animate-in fade-in-50">
                <div className="mx-auto flex max-w-[420px] flex-col items-center justify-center text-center">
                    <p className="text-sm text-muted-foreground">
                        No interaction data recorded yet.
                    </p>
                </div>
            </div>
        );
    }

    // data is expected to be an array of slots with interactions
    // AllSlotInteractions expects { slots } prop
    return (
        <div className="space-y-4">
            <div className="flex justify-end print:hidden">
                <Button variant="outline" size="sm" onClick={handleDownloadCSV}>
                    <Download className="mr-2 h-4 w-4" />
                    Download CSV
                </Button>
            </div>
            <AllSlotInteractions slots={data} />
        </div>
    );
};

export default InteractionAnalytics;
