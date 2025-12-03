import React from 'react';
import { Modal } from '@/components/ui/modal';
import InstructorRatingInterface from './InstructorRatingInterface';

const RatingModal = ({ open, onOpenChange, problemId, bankId, problemLabel }) => {
    return (
        <Modal
            open={open}
            onOpenChange={onOpenChange}
            title={`Rate ${problemLabel}`}
            description="Rate this problem based on the bank's rubric."
        >
            <InstructorRatingInterface problemId={problemId} bankId={bankId} />
        </Modal>
    );
};

export default RatingModal;
