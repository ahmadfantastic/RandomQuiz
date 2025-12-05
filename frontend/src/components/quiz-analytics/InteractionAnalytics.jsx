import React from 'react';
import AllSlotInteractions from './AllSlotInteractions';

const InteractionAnalytics = ({ data }) => {
    if (!data) return null;

    // data is expected to be an array of slots with interactions
    // AllSlotInteractions expects { slots } prop
    return (
        <div className="space-y-8">
            <AllSlotInteractions slots={data} />
        </div>
    );
};

export default InteractionAnalytics;
