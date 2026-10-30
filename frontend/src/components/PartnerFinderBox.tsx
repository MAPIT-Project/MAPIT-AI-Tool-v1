import { useState } from "react";
import {
  Box,
  VStack,
  HStack,
  Input,
  Button,
  Text,
  useToast,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  IconButton,
  Tooltip,
} from '@chakra-ui/react';
import { FiSearch, FiUsers, FiCopy } from 'react-icons/fi';
import { postFindPartners } from '../utils/api';
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

interface Partner {
  id: string;
  name: string;
  shortName: string;
  country: string;
  type: string;
  score: number;
  method: string;
}



export default function PartnerFinderBox() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [partners, setPartners] = useState<Partner[]>([]);
  const [originalQuery, setOriginalQuery] = useState<string>("");
  const [expandedQuery, setExpandedQuery] = useState<string>("");
  const toast = useToast();
  const colors = useThemeColors();
  const { isOpen, onOpen, onClose } = useDisclosure();

  const handleFindPartners = async () => {
    setError(null);
    
    if (query.trim().length < 2) {
      setError("Please enter at least 2 characters.");
      return;
    }
    
    setLoading(true);
    
    try {
      const response = await postFindPartners(query.trim());
      setPartners(response.partners);
      setOriginalQuery(response.original_query || "");
      setExpandedQuery(response.expanded_query || "");
      
      if (response.partners.length === 0) {
        toast({
          title: "No partners found",
          description: "Try a different search term or check your query.",
          status: "info",
          duration: 3000,
          isClosable: true,
        });
      } else {
        toast({
          title: "Partners found",
          description: `Found ${response.partners.length} similar organizations.`,
          status: "success",
          duration: 3000,
          isClosable: true,
        });
        onOpen(); // Open the modal to show results
      }
      
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

  const formatScore = (score: number) => {
    return (score * 100).toFixed(1) + '%';
  };

  const getMethodColor = (method: string) => {
    if (method === 'SentenceTransformer') {
      return 'blue';
    } else if (method === 'SemanticGNN') {
      return 'green';
    } else if (method === 'ProjectFTS') {
      return 'purple';
    } else {
      return 'gray';
    }
  };

  const copyResultsToClipboard = async () => {
    try {
      let content = `Partner Finder Results\n`;
      content += `Original Query: "${originalQuery}"\n`;
      if (expandedQuery && expandedQuery !== originalQuery) {
        content += `Expanded Query: "${expandedQuery}"\n`;
      }
      content += `\nFound ${partners.length} similar organizations:\n\n`;
      
      partners.forEach((partner, index) => {
        content += `${index + 1}. ${partner.name || 'N/A'} (${partner.country || 'N/A'})\n`;
        content += `   ID: ${partner.id}\n`;
        content += `   Type: ${partner.type || 'N/A'}\n`;
        content += `   Similarity: ${formatScore(partner.score)}\n`;
        content += `   Method: ${partner.method}\n\n`;
      });
      
      await navigator.clipboard.writeText(content);
      
      toast({
        title: "Results copied",
        description: "Partner search results have been copied to clipboard.",
        status: "success",
        duration: 2000,
        isClosable: true,
      });
    } catch (err) {
      toast({
        title: "Copy failed",
        description: "Failed to copy results to clipboard.",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  return (
    <>
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
              <FiUsers />
              Partner Finder
            </Text>
          </Box>
          
          <VStack spacing={2} align="stretch">
            <Input
              placeholder='Enter keywords'
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  handleFindPartners();
                }
              }}
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
              onClick={handleFindPartners}
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
              leftIcon={loading ? <AnimatedSpinner size="12px" color="white" /> : <FiSearch />}
              isLoading={loading}
              loadingText="Finding..."
            >
              Find Partners
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

      {/* Results Modal */}
      <Modal isOpen={isOpen} onClose={onClose} size="6xl">
        <ModalOverlay />
        <ModalContent maxW="90vw" maxH="90vh" bg={colors.cardBg} borderColor={colors.cardBorder}>
          <ModalHeader>
            <VStack align="start" spacing={2}>
                          <Text fontSize="xl" fontWeight="bold" color={colors.text}>
              Partner Search Results
            </Text>
                          <Text fontSize="sm" color={colors.text + '80'}>
              Query: "{originalQuery}"
            </Text>
              <HStack spacing={4}>
                <Badge colorScheme="blue">
                  {partners.length} Partners Found
                </Badge>
              </HStack>
            </VStack>
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody p={0}>
            <Box p={4} display="flex" flexDirection="column" maxH="calc(90vh - 200px)" overflow="hidden">
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={3} flexShrink={0}>
                <Text color={colors.text} fontSize="sm">
                  Found {partners.length} similar organizations based on your query.
                </Text>
                <Tooltip label="Copy results to clipboard" placement="top">
                  <IconButton
                    aria-label="Copy results"
                    icon={<FiCopy size={12} />}
                    size={{ base: "xs", md: "sm" }}
                    onClick={copyResultsToClipboard}
                    bg={colors.gradient}
                    color="white"
                    borderRadius="lg"
                    _hover={{
                      bg: colors.gradientDark,
                      transform: 'translateY(-1px)',
                      boxShadow: colors.shadowLg,
                    }}
                    _active={{
                      transform: 'translateY(0)',
                    }}
                    transition="all 0.2s ease-in-out"
                  />
                </Tooltip>
              </Box>
              
              {expandedQuery && expandedQuery !== originalQuery && (
                <Box mb={3} p={2} bg={colors.inputBg} borderRadius="lg" border="1px solid" borderColor={colors.cardBorder} flexShrink={0}>
                  <Text fontSize="xs" fontWeight="bold" color={colors.text} mb={1}>
                    Query Expansion:
                  </Text>
                  <Text fontSize="xs" color={colors.text + '80'} mb={1}>
                    <strong>Original:</strong> "{originalQuery}"
                  </Text>
                  <Text fontSize="xs" color={colors.text + '80'}>
                    <strong>Expanded:</strong> "{expandedQuery}"
                  </Text>
                </Box>
              )}
              
              <Box flex="1" overflowY="auto" overflowX="auto">
                <Table variant="simple" size="sm">
                  <Thead position="sticky" top={0} bg={colors.cardBg} zIndex={1}>
                    <Tr>
                      <Th color={colors.text}>#</Th>
                      <Th color={colors.text}>ID</Th>
                      <Th color={colors.text}>Name</Th>
                      <Th color={colors.text}>Country</Th>
                      <Th color={colors.text}>Type</Th>
                      <Th color={colors.text}>Similarity</Th>
                      <Th color={colors.text}>Method</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {partners.map((partner, index) => (
                      <Tr key={`${partner.id}-${index}`}>
                        <Td color={colors.text} fontSize="xs" fontWeight="bold" textAlign="center">
                          {index + 1}
                        </Td>
                        <Td color={colors.text} fontSize="xs" fontFamily="mono">
                          {partner.id}
                        </Td>
                        <Td color={colors.text} maxW="200px">
                          <Text noOfLines={2} title={partner.name}>
                            {partner.name || 'N/A'}
                          </Text>
                        </Td>
                        <Td color={colors.text}>
                          {partner.country || 'N/A'}
                        </Td>
                        <Td color={colors.text}>
                          {partner.type || 'N/A'}
                        </Td>
                        <Td color={colors.text} fontWeight="bold">
                          {formatScore(partner.score)}
                        </Td>
                        <Td>
                          <Badge colorScheme={getMethodColor(partner.method)} variant="subtle">
                            {partner.method}
                          </Badge>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </Box>
              

            </Box>
          </ModalBody>
        </ModalContent>
      </Modal>
    </>
  );
}
