import React, { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { Box, VStack, Text, Button, Heading } from '@chakra-ui/react';
import { useNavigate } from 'react-router-dom';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} />;
    }

    return this.props.children;
  }
}

const ErrorFallback: React.FC<{ error?: Error }> = ({ error }) => {
  const navigate = useNavigate();

  const handleGoHome = () => {
    navigate('/', { replace: true });
  };

  return (
    <Box h="100vh" display="flex" alignItems="center" justifyContent="center" bg="gray.50">
      <VStack spacing={6} p={8} maxW="md" textAlign="center">
        <Heading size="lg" color="red.500">
          Oops! Something went wrong
        </Heading>
        <Text color="gray.600">
          We encountered an unexpected error. This might be due to a network issue or authentication problem.
        </Text>
        {error && (
          <Box p={4} bg="red.50" borderRadius="md" border="1px solid" borderColor="red.200">
            <Text fontSize="sm" color="red.700" fontFamily="mono">
              {error.message}
            </Text>
          </Box>
        )}
        <Button colorScheme="blue" onClick={handleGoHome}>
          Go to Home Page
        </Button>
      </VStack>
    </Box>
  );
};
