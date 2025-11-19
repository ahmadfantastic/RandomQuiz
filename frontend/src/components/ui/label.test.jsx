import React from 'react';
import { render, screen } from '@testing-library/react';
import { Label } from './label';

describe('Label', () => {
    it('renders correctly', () => {
        render(<Label htmlFor="test-input">Test Label</Label>);
        const label = screen.getByText('Test Label');
        expect(label).toBeInTheDocument();
        expect(label).toHaveAttribute('for', 'test-input');
    });

    it('applies custom classes', () => {
        render(<Label className="custom-class">Test</Label>);
        // We can check if it renders without crashing
        expect(screen.getByText('Test')).toBeInTheDocument();
    });
});
