import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import Home from '../app/page'

global.fetch = jest.fn(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve([]),
  })
) as jest.Mock;

describe('Home Page UI Tests', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockClear();
  });

  it('renders the initial layout and sidebar elements correctly', async () => {
    render(<Home />);
    
    expect(screen.getByText(/AI/)).toBeInTheDocument();
    expect(screen.getByText(/Knowledge Platform/)).toBeInTheDocument();
    expect(screen.getByText('New Chat')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Ask anything...')).toBeInTheDocument();
    
    // Check main chat empty state
    await waitFor(() => {
        expect(screen.getByText('How can I help you today?')).toBeInTheDocument();
    });
  });

  it('allows user to type into the message input field', async () => {
    render(<Home />);
    
    const input = screen.getByPlaceholderText('Ask anything...');
    fireEvent.change(input, { target: { value: 'What is the internal RAG policy?' } });
    
    expect(input).toHaveValue('What is the internal RAG policy?');
  });
});
