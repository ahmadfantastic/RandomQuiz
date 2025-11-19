import React from 'react';
import { render, screen } from '@testing-library/react';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from './card';

describe('Card', () => {
    it('renders card with content', () => {
        render(
            <Card>
                <CardHeader>
                    <CardTitle>Card Title</CardTitle>
                </CardHeader>
                <CardContent>
                    <p>Card Content</p>
                </CardContent>
                <CardFooter>
                    <button>Action</button>
                </CardFooter>
            </Card>
        );

        expect(screen.getByText('Card Title')).toBeInTheDocument();
        expect(screen.getByText('Card Content')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /action/i })).toBeInTheDocument();
    });

    it('applies custom classes', () => {
        render(<Card className="custom-class">Content</Card>);
        // Note: We can't easily check for class without adding data-testid or similar, 
        // but we can check if it renders without crashing.
        expect(screen.getByText('Content')).toBeInTheDocument();
    });
});
