import {
  Box,
  Flex,
  Image,
  Button,
  useToast,
  Text,
  HStack,
  Select,
  IconButton,
  useDisclosure,
  Drawer,
  DrawerBody,
  DrawerHeader,
  DrawerOverlay,
  DrawerContent,
  DrawerCloseButton,
  VStack,
  Divider,
} from '@chakra-ui/react';
import { FiLogOut, FiMenu } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useThemeColors } from '../hooks/useThemeColors';
import { ThemeSettings } from './ThemeSettings';
import { EuHorizonLogo } from './EuHorizonLogo';
import { DataRefreshBadge } from './DataRefreshBadge';
import mapitLogo from '../assets/mapit_logo_no_bg.png';

interface NavbarProps {
  selectedModel?: string;
  onModelChange?: (model: string) => void;
}

const LAST_DATA_REFRESH = '27 May 2026';

export const Navbar = ({ selectedModel, onModelChange }: NavbarProps) => {
  const { logout, currentUser } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const colors = useThemeColors();
  const { isOpen, onOpen, onClose } = useDisclosure();

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/');
      onClose(); // Close mobile menu after logout
    } catch (error) {
      toast({
        title: 'Error signing out',
        description: error instanceof Error ? error.message : 'An error occurred',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
    }
  };

  return (
    <>
      <Box
        bg={colors.sidebarBg}
        px={{ base: 3, md: 6 }}
        borderBottom="1px"
        borderStyle="solid"
        borderColor={colors.sidebarBorder}
        position="fixed"
        top={0}
        left={0}
        right={0}
        zIndex={1000}
        backdropFilter="blur(10px)"
        boxShadow={colors.shadow}
      >
        <Flex h={{ base: 14, md: 16 }} alignItems="center" justifyContent="space-between">
          {/* Logo and Title - Responsive */}
          <HStack spacing={{ base: 2, md: 4 }} alignItems="center">
            <Image
              src={mapitLogo}
              alt="Mapit AI Logo"
              height={{ base: "36px", md: "48px" }}
              width={{ base: "36px", md: "48px" }}
              objectFit="contain"
              borderRadius="md"
            />
            <Box display={{ base: 'none', sm: 'block' }}>
              <Text
                fontSize={{ base: 'lg', md: 'xl' }}
                fontWeight="bold"
                bgGradient="linear(to-r, ai.primary.500, ai.accent.500)"
                bgClip="text"
                letterSpacing="tight"
              >
                MAPIT AI
              </Text>
              <Text
                fontSize={{ base: 'xs', md: 'xs' }}
                color={colors.text + '80'}
                fontWeight="medium"
                letterSpacing="wide"
                textTransform="uppercase"
                mt={-1}
              >
                Domain Expert Tool
              </Text>
            </Box>
            <HStack spacing={3} ml={{ base: 0, md: 3 }} display={{ base: 'none', sm: 'flex' }} alignItems="center">
              <EuHorizonLogo height={{ base: '40px', md: '56px' }} tooltipPlacement="bottom" />
              <Box display={{ base: 'none', md: 'block' }}>
                <DataRefreshBadge dateLabel={LAST_DATA_REFRESH} compact fontSize="xs" />
              </Box>
            </HStack>
          </HStack>

          {/* Desktop Controls */}
          <Flex alignItems="center" gap={3} display={{ base: 'none', md: 'flex' }}>
            {selectedModel && onModelChange && (
              <Box minW="200px">
                <Select 
                  value={selectedModel} 
                  onChange={(e) => onModelChange(e.target.value)}
                  size="sm"
                  bg={colors.inputBg}
                  borderColor={colors.inputBorder}
                  color={colors.text}
                  borderRadius="lg"
                  _hover={{
                    borderColor: colors.primary,
                  }}
                  _focus={{
                    borderColor: colors.primary,
                    boxShadow: `0 0 0 1px ${colors.primary}30`,
                  }}
                >
                  <option value="openai-gpt4o-mini">OpenAI GPT-4o-mini</option>
                  <option value="openai-gpt5-mini">OpenAI GPT-5-mini</option>
                </Select>
              </Box>
            )}
            <ThemeSettings />
            <HStack spacing={2} alignItems="center">
              {currentUser && (
                <Text
                  fontSize="sm"
                  color={colors.text}
                  fontWeight="medium"
                  maxW="150px"
                  isTruncated
                >
                  {currentUser.displayName || currentUser.email}
                </Text>
              )}
              <Button
                variant="ghost"
                leftIcon={<FiLogOut />}
                onClick={handleLogout}
                size="sm"
                borderRadius="lg"
                _hover={{
                  bg: colors.hoverBg,
                  transform: 'translateY(-1px)',
                }}
                transition="all 0.2s ease-in-out"
              >
                Sign Out
              </Button>
            </HStack>
          </Flex>

          {/* Mobile Menu Button */}
          <IconButton
            aria-label="Open menu"
            icon={<FiMenu />}
            onClick={onOpen}
            variant="ghost"
            size="md"
            display={{ base: 'flex', md: 'none' }}
            color={colors.text}
            _hover={{
              bg: colors.hoverBg,
            }}
          />
        </Flex>
      </Box>

      {/* Mobile Drawer */}
      <Drawer isOpen={isOpen} placement="right" onClose={onClose} size="full">
        <DrawerOverlay />
        <DrawerContent bg={colors.sidebarBg}>
          <DrawerCloseButton color={colors.text} />
          <DrawerHeader borderBottomWidth="1px" borderColor={colors.sidebarBorder}>
            <HStack spacing={3}>
              <Image
                src={mapitLogo}
                alt="Mapit AI Logo"
                height="44px"
                width="44px"
                objectFit="contain"
                borderRadius="md"
              />
              <Text
                fontSize="lg"
                fontWeight="bold"
                bgGradient="linear(to-r, ai.primary.500, ai.accent.500)"
                bgClip="text"
              >
                MAPIT AI
              </Text>
            </HStack>
            <Text
              mt={2}
              fontSize="xs"
              color={colors.primary}
              fontWeight="semibold"
            >
              Last data refresh: {LAST_DATA_REFRESH}
            </Text>
          </DrawerHeader>
          <DrawerBody p={4}>
            <VStack spacing={6} align="stretch">
              {/* User Info */}
              {currentUser && (
                <Box
                  p={4}
                  bg={colors.cardBg}
                  borderRadius="lg"
                  border="1px solid"
                  borderColor={colors.cardBorder}
                >
                  <Text fontSize="sm" color={colors.text + '80'} mb={1}>
                    Signed in as
                  </Text>
                  <Text fontSize="md" fontWeight="medium" color={colors.text}>
                    {currentUser.displayName || currentUser.email}
                  </Text>
                </Box>
              )}

              {/* Model Selection */}
              {selectedModel && onModelChange && (
                <Box>
                  <Text fontSize="sm" fontWeight="medium" color={colors.text} mb={2}>
                    AI Model
                  </Text>
                  <Select 
                    value={selectedModel} 
                    onChange={(e) => onModelChange(e.target.value)}
                    size="md"
                    bg={colors.inputBg}
                    borderColor={colors.inputBorder}
                    color={colors.text}
                    borderRadius="lg"
                    _hover={{
                      borderColor: colors.primary,
                    }}
                    _focus={{
                      borderColor: colors.primary,
                      boxShadow: `0 0 0 1px ${colors.primary}30`,
                    }}
                  >
                    <option value="openai-gpt4o-mini">OpenAI GPT-4o-mini</option>
                    <option value="openai-gpt5-mini">OpenAI GPT-5-mini</option>
                  </Select>
                </Box>
              )}

              <Divider borderColor={colors.sidebarBorder} />

              <Box>
                <Text fontSize="sm" fontWeight="medium" color={colors.text} mb={3}>
                  EU funding
                </Text>
                <EuHorizonLogo height="44px" tooltipPlacement="top" />
              </Box>

              <Divider borderColor={colors.sidebarBorder} />

              {/* Theme Settings */}
              <Box>
                <Text fontSize="sm" fontWeight="medium" color={colors.text} mb={3}>
                  Theme
                </Text>
                <ThemeSettings />
              </Box>

              <Divider borderColor={colors.sidebarBorder} />

              {/* Sign Out Button */}
              <Button
                variant="ghost"
                leftIcon={<FiLogOut />}
                onClick={handleLogout}
                size="lg"
                borderRadius="lg"
                color={colors.error}
                _hover={{
                  bg: colors.error + '20',
                }}
                justifyContent="flex-start"
              >
                Sign Out
              </Button>
            </VStack>
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </>
  );
}; 