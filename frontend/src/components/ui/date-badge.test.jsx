import React from 'react';
import { render, screen } from '@testing-library/react';
import DateBadge from './date-badge';

// Mock formatDateTime
vi.mock('@/lib/formatDateTime', () => ({
    formatDateTime: (date) => (date ? `Formatted ${date}` : null),
}));

describe('DateBadge', () => {
    it('renders formatted date when value is provided', () => {
        render(<DateBadge value="2023-01-01" />);
        expect(screen.getByText('Formatted 2023-01-01')).toBeInTheDocument();
    });

    it('renders fallback when value is missing', () => {
        render(<DateBadge />);
        expect(screen.getByText('Not available')).toBeInTheDocument();
    });

    it('renders custom fallback', () => {
        render(<DateBadge fallback="No date" />);
        expect(screen.getByText('No date')).toBeInTheDocument();
    });
});
