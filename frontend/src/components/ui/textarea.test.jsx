import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Textarea } from './textarea';

describe('Textarea', () => {
    it('renders correctly', () => {
        render(<Textarea placeholder="Enter text" />);
        expect(screen.getByPlaceholderText('Enter text')).toBeInTheDocument();
    });

    it('handles value changes', () => {
        const handleChange = vi.fn();
        render(<Textarea onChange={handleChange} />);
        const textarea = screen.getByRole('textbox');
        fireEvent.change(textarea, { target: { value: 'test content' } });
        expect(handleChange).toHaveBeenCalled();
        expect(textarea).toHaveValue('test content');
    });
});
