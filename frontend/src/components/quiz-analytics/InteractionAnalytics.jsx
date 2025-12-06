import React from 'react';
import AllSlotInteractions from './AllSlotInteractions';

const InteractionAnalytics = ({ data }) => {
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
        <div className="space-y-8">
            <AllSlotInteractions slots={data} />
        </div>
    );
};

export default InteractionAnalytics;
