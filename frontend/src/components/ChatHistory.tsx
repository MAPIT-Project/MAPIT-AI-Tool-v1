import React from 'react';
import {
  Box,
  VStack,
  Text,
  Button,
  useColorModeValue,
  Divider,
  IconButton,
} from '@chakra-ui/react';
import { FiX } from 'react-icons/fi';

interface ChatSession {
  id: string;
  title: string;
  timestamp: string;
}

interface ChatHistoryProps {
  sessions: ChatSession[];
  currentSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onRemoveSession: (sessionId: string) => void;
}

export const ChatHistory: React.FC<ChatHistoryProps> = ({
  sessions,
  currentSessionId,
  onSelectSession,
  onRemoveSession,
}) => {
  const bgColor = useColorModeValue('white', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const hoverBg = useColorModeValue('gray.50', 'gray.600');

  return (
    <Box
      width="250px"
      height="100%"
      borderRight="1px"
      borderColor={borderColor}
      bg={bgColor}
      p={4}
      overflow="hidden"
      display="flex"
      flexDirection="column"
    >
      <Text fontSize="lg" fontWeight="bold" mb={2}>
        Chat History
      </Text>
      <Divider />
      <Box
        flex="1"
        overflowY="auto"
        css={{
          '&::-webkit-scrollbar': {
            width: '4px',
          },
          '&::-webkit-scrollbar-track': {
            background: '#f1f1f1',
            borderRadius: '4px',
          },
          '&::-webkit-scrollbar-thumb': {
            background: '#888',
            borderRadius: '4px',
          },
          '&::-webkit-scrollbar-thumb:hover': {
            background: '#555',
          },
        }}
      >
        <VStack align="stretch" spacing={4} pr={2}>
          {sessions.map((session) => (
            <Box
              key={session.id}
              position="relative"
              width="100%"
            >
              <Button
                variant="ghost"
                justifyContent="flex-start"
                textAlign="left"
                height="auto"
                p={3}
                bg={session.id === currentSessionId ? 'blue.50' : 'transparent'}
                _hover={{ bg: hoverBg }}
                onClick={() => onSelectSession(session.id)}
                width="100%"
                whiteSpace="normal"
                wordBreak="break-word"
              >
                <VStack align="start" spacing={1} width="100%">
                  <Text fontWeight="medium" noOfLines={1} width="100%">
                    {session.title}
                  </Text>
                  <Text fontSize="xs" color="gray.400" width="100%">
                    {new Date(session.timestamp).toLocaleDateString()}
                  </Text>
                </VStack>
              </Button>
              <IconButton
                aria-label="Remove chat"
                icon={<FiX />}
                size="xs"
                position="absolute"
                top={1}
                right={1}
                colorScheme="red"
                variant="ghost"
                onClick={(e) => {
                  e.stopPropagation();
                  onRemoveSession(session.id);
                }}
              />
            </Box>
          ))}
        </VStack>
      </Box>
    </Box>
  );
}; 