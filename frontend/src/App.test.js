//frontend/src/App.test.js
import { render, screen } from '@testing-library/react';
import App from './App';

test('renders main navigation tabs', () => {
  render(<App />);
  expect(screen.getByText(/Cheque Validation/i)).toBeInTheDocument();
  expect(screen.getByText(/PAN Form Extraction/i)).toBeInTheDocument();
});
