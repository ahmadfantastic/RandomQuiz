
import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import AllSlotInteractions from '../quiz-analytics/AllSlotInteractions';
import api from '@/lib/api';

const GlobalInteractionsTab = () => {
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const response = await api.get('/api/problem-banks/analysis/global/interactions/');
                setData(response.data);
            } catch (err) {
                console.error('Failed to fetch global interactions:', err);
                setError('Failed to load interaction data.');
            } finally {
                setLoading(false);
            }
        };

        fetchData();
    }, []);

    if (loading) {
        return <div className="p-4 text-center">Loading interactions...</div>;
    }

    if (error) {
        return <div className="p-4 text-center text-red-500">{error}</div>;
    }

    if (!data || data.length === 0) {
        return (
            <div className="flex h-64 items-center justify-center rounded-lg border border-dashed p-8 text-center animate-in fade-in-50">
                <div className="mx-auto flex max-w-[420px] flex-col items-center justify-center text-center">
                    <p className="text-sm text-muted-foreground">
                        No interaction data recorded across any quizzes.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <AllSlotInteractions slots={data} />
        </div>
    );
};

export default GlobalInteractionsTab;
