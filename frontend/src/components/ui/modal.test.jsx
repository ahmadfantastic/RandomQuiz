import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Modal } from './modal';

describe('Modal', () => {
    it('does not render when open is false', () => {
        render(
            <Modal open={false} title="Test Modal">
                <p>Modal Content</p>
            </Modal>
        );
        expect(screen.queryByText('Test Modal')).not.toBeInTheDocument();
    });

    it('renders correctly when open is true', () => {
        render(
            <Modal open={true} title="Test Modal" description="Test Description">
                <p>Modal Content</p>
            </Modal>
        );
        expect(screen.getByText('Test Modal')).toBeInTheDocument();
        expect(screen.getByText('Test Description')).toBeInTheDocument();
        expect(screen.getByText('Modal Content')).toBeInTheDocument();
    });

    it('calls onOpenChange when close button is clicked', () => {
        const handleOpenChange = vi.fn();
        render(
            <Modal open={true} onOpenChange={handleOpenChange}>
                <p>Content</p>
            </Modal>
        );
        fireEvent.click(screen.getByRole('button', { name: /close/i }));
        expect(handleOpenChange).toHaveBeenCalledWith(false);
    });

    it('calls onOpenChange when clicking outside', () => {
        const handleOpenChange = vi.fn();
        render(
            <Modal open={true} onOpenChange={handleOpenChange}>
                <p>Content</p>
            </Modal>
        );
        // The backdrop has role="dialog"
        fireEvent.click(screen.getByRole('dialog'));
        expect(handleOpenChange).toHaveBeenCalledWith(false);
    });

    it('closes on escape key', () => {
        const handleOpenChange = vi.fn();
        render(
            <Modal open={true} onOpenChange={handleOpenChange}>
                <p>Content</p>
            </Modal>
        );
        fireEvent.keyDown(document, { key: 'Escape' });
        expect(handleOpenChange).toHaveBeenCalledWith(false);
    });
});
