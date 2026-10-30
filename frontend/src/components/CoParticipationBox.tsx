import { useState } from "react";
import {
  Box,
  VStack,
  Input,
  Button,
  Text,
  useToast,
} from '@chakra-ui/react';
import { FiShare2, FiGitBranch } from 'react-icons/fi';
import { postExpand, postVisualize } from '../utils/api';
import { useThemeColors } from '../hooks/useThemeColors';

// Animated Spinner Component
const AnimatedSpinner = ({ size = "xs", color = "blue.500" }: { size?: string, color?: string }) => (
  <Box
    display="inline-flex"
    alignItems="center"
    justifyContent="center"
    animation="spin 1s linear infinite"
    sx={{
      '@keyframes spin': {
        '0%': { transform: 'rotate(0deg)' },
        '100%': { transform: 'rotate(360deg)' }
      }
    }}
  >
    <Box
      width={size}
      height={size}
      borderRadius="50%"
      border="2px solid"
      borderColor={`${color}20`}
      borderTopColor={color}
    />
  </Box>
);

export default function CoParticipationBox() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();
  const colors = useThemeColors();

  const handleVisualize = async () => {
    setError(null);
    
    if (query.trim().length < 3) {
      setError("Please enter a topic or phrase.");
      return;
    }
    
    setLoading(true);
    
    try {
      // Step 1: Expand the query with GPT-4o
      const { expanded_query_lucene } = await postExpand(query.trim());
      
      // Step 2: Create visualization
      const { url } = await postVisualize({
        expanded_query_lucene,
        min_score: 1.0,
        min_weight: 2,
        epsilon: 0.1,
        limit: 2000,
        run_louvain: true,
        graph_name: "orgOrg_hybrid",
        write_prop: "communityHybrid",
      });
      
      // Step 3: Open visualization in new tab
      // Construct full URL with backend port since the URL is relative to backend
      const fullUrl = url.startsWith('http') ? url : `/api/${url}`;
      window.open(fullUrl, "_blank", "noopener,noreferrer");
      
      // Show success toast
      toast({
        title: "Visualization created",
        description: "The co-participation network has been opened in a new tab.",
        status: "success",
        duration: 3000,
        isClosable: true,
      });
      
    } catch (err: any) {
      const errorMessage = err.message || "An unexpected error occurred.";
      setError(errorMessage);
      
      toast({
        title: "Error",
        description: errorMessage,
        status: "error",
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      bg={colors.cardBg}
      border="1px solid"
      borderColor={colors.cardBorder}
      borderRadius="xl"
      p={3}
      boxShadow={colors.shadow}
    >
      <VStack spacing={2} align="stretch">
        <Box>
          <Text 
            fontSize="lg" 
            fontWeight="bold" 
            mb={2} 
            color={colors.text}
            display="flex"
            alignItems="center"
            gap={2}
          >
            <FiGitBranch />
            Co-participation
          </Text>
        </Box>
        
        <VStack spacing={2} align="stretch">
          <Input
            placeholder='e.g., "Quantum Computing"'
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={loading}
            bg={colors.inputBg}
            borderColor={colors.inputBorder}
            color={colors.text}
            _placeholder={{ color: colors.text + '60' }}
            borderRadius="lg"
            _hover={{
              borderColor: colors.primary,
            }}
            _focus={{
              borderColor: colors.primary,
              boxShadow: `0 0 0 1px ${colors.primary}30`,
            }}
          />
          <Button
            onClick={handleVisualize}
            disabled={loading || !query.trim()}
            bg={colors.gradient}
            color="white"
            borderRadius="lg"
            px={6}
            _hover={{
              bg: colors.gradientDark,
              transform: 'translateY(-1px)',
              boxShadow: colors.shadowLg,
            }}
            _active={{
              transform: 'translateY(0)',
            }}
            transition="all 0.2s ease-in-out"
            leftIcon={loading ? <AnimatedSpinner size="12px" color="white" /> : <FiShare2 />}
            isLoading={loading}
            loadingText="Loading..."
          >
            Visualize
          </Button>
        </VStack>
        
        {error && (
          <Box 
            mt={2} 
            p={4} 
            bg="red.50" 
            border="1px solid" 
            borderColor="red.200" 
            borderRadius="lg"
            _dark={{
              bg: 'red.900',
              borderColor: 'red.700',
            }}
          >
            <Text fontSize="sm" color="red.600" display="flex" alignItems="center" gap={2}>
              {error}
            </Text>
          </Box>
        )}
      </VStack>
    </Box>
  );
}
