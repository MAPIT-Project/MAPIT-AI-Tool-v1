import React from 'react';
import { Box, Text, Button } from '@chakra-ui/react';
import { useAuth } from '../contexts/AuthContext';

export const TestRoute: React.FC = () => {
  const { currentUser, loading } = useAuth();

  return (
    <Box p={8}>
      <Text fontSize="2xl" mb={4}>Test Route</Text>
      <Text>Loading: {loading ? 'true' : 'false'}</Text>
      <Text>User: {currentUser ? 'Authenticated' : 'Not authenticated'}</Text>
      <Text>User ID: {currentUser?.uid || 'None'}</Text>
      <Button onClick={() => console.log('Auth state:', { currentUser, loading })}>
        Log Auth State
      </Button>
    </Box>
  );
}; 