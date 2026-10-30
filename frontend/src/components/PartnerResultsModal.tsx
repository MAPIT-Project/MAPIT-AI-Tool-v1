import {
  Box,
  VStack,
  HStack,
  Text,
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
  IconButton,
  Tooltip,
  useToast,
} from '@chakra-ui/react';
import { FiCopy } from 'react-icons/fi';
import { useThemeColors } from '../hooks/useThemeColors';

interface Partner {
  id: string;
  name: string;
  shortName: string;
  country: string;
  type: string;
  score: number;
  method: string;
}

interface PartnerResultsModalProps {
  isOpen: boolean;
  onClose: () => void;
  partners: Partner[];
  luceneQuery?: string;
  originalQuery?: string;
  expandedQuery?: string;
}

export default function PartnerResultsModal({
  isOpen,
  onClose,
  partners,
  luceneQuery,
  originalQuery,
  expandedQuery
}: PartnerResultsModalProps) {
  const colors = useThemeColors();
  const toast = useToast();

  const formatScore = (score: number) => {
    return (score * 100).toFixed(1) + '%';
  };

  const getMethodColor = (method: string) => {
    switch (method) {
      case 'SentenceTransformer':
        return 'blue';
      case 'SemanticGNN':
        return 'green';
      case 'ProjectFTS':
      case 'Fulltext':
        return 'purple';
      default:
        return 'gray';
    }
  };

  const copyResultsToClipboard = async () => {
    try {
      const resultsText = partners.map((partner, index) => 
        `${index + 1}. ${partner.name} (${partner.country}) - ${formatScore(partner.score)} - ${partner.method}`
      ).join('\n');
      
      const fullText = `Partner Search Results\nQuery: ${luceneQuery || originalQuery}\n\n${resultsText}`;
      
      await navigator.clipboard.writeText(fullText);
      
      toast({
        title: "Results copied",
        description: "Partner search results have been copied to clipboard.",
        status: "success",
        duration: 2000,
        isClosable: true,
      });
    } catch (error) {
      console.error('Failed to copy results:', error);
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
    <Modal isOpen={isOpen} onClose={onClose} size="6xl">
      <ModalOverlay />
              <ModalContent maxW="90vw" maxH="90vh" bg={colors.cardBg} borderColor={colors.cardBorder}>
        <ModalHeader>
          <VStack align="start" spacing={2}>
            <Text fontSize="xl" fontWeight="bold" color={colors.text}>
              Partner Search Results
            </Text>
            <Text fontSize="sm" color={colors.text + '80'}>
              Query: "{originalQuery || luceneQuery}"
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
            
            {/* Show query information */}
            {(luceneQuery || originalQuery) && (
              <Box mb={3} p={2} bg={colors.inputBg} borderRadius="lg" border="1px solid" borderColor={colors.cardBorder} flexShrink={0}>
                <Text fontSize="xs" fontWeight="bold" color={colors.text} mb={1}>
                  Query Information:
                </Text>
                {luceneQuery && (
                  <Text fontSize="xs" color={colors.text + '80'} mb={1}>
                    <strong>Lucene Query:</strong> "{luceneQuery}"
                  </Text>
                )}
                {originalQuery && expandedQuery && expandedQuery !== originalQuery && (
                  <>
                    <Text fontSize="xs" color={colors.text + '80'} mb={1}>
                      <strong>Original:</strong> "{originalQuery}"
                    </Text>
                    <Text fontSize="xs" color={colors.text + '80'}>
                      <strong>Expanded:</strong> "{expandedQuery}"
                    </Text>
                  </>
                )}
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
  );
}
