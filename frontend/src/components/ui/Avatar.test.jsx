import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import Avatar from './Avatar';

describe('Avatar', () => {
    it('renders image when src is provided', () => {
        render(<Avatar src="https://example.com/avatar.jpg" name="John Doe" />);
        const img = screen.getByRole('img', { name: /john doe/i });
        expect(img).toBeInTheDocument();
        expect(img).toHaveAttribute('src', 'https://example.com/avatar.jpg');
    });

    it('renders initials when src is not provided', () => {
        render(<Avatar name="John Doe" />);
        expect(screen.getByText('JD')).toBeInTheDocument();
        expect(screen.queryByRole('img')).not.toBeInTheDocument();
    });

    it('renders initials when image fails to load', () => {
        render(<Avatar src="https://example.com/invalid.jpg" name="Jane Doe" />);
        const img = screen.getByRole('img', { name: /jane doe/i });
        fireEvent.error(img);
        expect(screen.getByText('JD')).toBeInTheDocument();
        expect(screen.queryByRole('img')).not.toBeInTheDocument();
    });

    it('renders default initials when name is missing', () => {
        render(<Avatar />);
        expect(screen.getByText('RQ')).toBeInTheDocument();
    });
});
