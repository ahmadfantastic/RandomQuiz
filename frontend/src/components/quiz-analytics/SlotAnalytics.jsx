import React from 'react';
import TextSlotAnalytics from './TextSlotAnalytics';
import RatingSlotAnalytics from './RatingSlotAnalytics';

const SlotAnalytics = ({ slot }) => {
    if (!slot) return null;

    if (slot.response_type === 'open_text') {
        return <TextSlotAnalytics slot={slot} />;
    } else if (slot.response_type === 'rating') {
        return <RatingSlotAnalytics slot={slot} />;
    }

    return <div>Unsupported slot type: {slot.response_type}</div>;
};

export default SlotAnalytics;
