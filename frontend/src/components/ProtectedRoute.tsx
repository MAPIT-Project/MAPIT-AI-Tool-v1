import React, { useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { Box, Spinner, Text, VStack } from '@chakra-ui/react';
import { useAuth } from '../contexts/AuthContext';

export const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { currentUser, loading } = useAuth();

  console.log('ProtectedRoute: loading=', loading, 'currentUser=', currentUser ? 'exists' : 'null');
  
  // Additional debugging for auth state
  useEffect(() => {
    console.log('ProtectedRoute: Auth state changed - loading:', loading, 'user:', currentUser?.email || 'none');
  }, [loading, currentUser]);

  // Show loading spinner while authentication is being checked
  if (loading) {
    console.log('ProtectedRoute: Showing loading spinner');
    return (
      <Box h="100vh" display="flex" alignItems="center" justifyContent="center">
        <VStack spacing={4}>
          <Spinner size="xl" color="blue.500" />
          <Text fontSize="lg" fontWeight="medium">Loading MAPIT AI...</Text>
          <Text fontSize="sm" color="gray.500">Authenticating user...</Text>
        </VStack>
      </Box>
    );
  }

  // If not authenticated, redirect to entrance page
  if (!currentUser) {
    console.log('ProtectedRoute: No authenticated user, redirecting to /');
    return <Navigate to="/" replace />;
  }

  // If authenticated, render the protected content
  console.log('ProtectedRoute: User authenticated, rendering protected content');
  return <>{children}</>;
}; 