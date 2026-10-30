import React, { useState } from 'react';
import {
  Box,
  Button,
  FormControl,
  FormLabel,
  Input,
  VStack,
  Text,
  useToast,
  Container,
  Heading,
  Divider,
  Image,
  Spinner,
  Checkbox,
  HStack,
} from '@chakra-ui/react';
import { FiUserPlus, FiLogIn } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useThemeColors } from '../hooks/useThemeColors';
import mapitLogo from '../assets/mapit_logo_no_bg.png';
import { EuHorizonLogo } from './EuHorizonLogo';
import { DataRefreshBadge } from './DataRefreshBadge';

const LAST_DATA_REFRESH = '27 May 2026';

export const Auth: React.FC = () => {
  const colors = useThemeColors();
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [rememberMe, setRememberMe] = useState(true); // Default to true for better UX

  const { signIn, signUp, /* signInWithGoogle, */ loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (isSignUp) {
        await signUp(email, password);
      } else {
        await signIn(email, password);
      }
      navigate('/chat');
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'An error occurred',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  /* const handleGoogleSignIn = async () => {
    setLoading(true);
    try {
      await signInWithGoogle();
      navigate('/chat');
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Google sign-in failed',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  }; */
  if (authLoading) {
    return (
      <Box bg={colors.bg} minH="100vh" display="flex" alignItems="center" justifyContent="center">
        <VStack spacing={6}>
          <Box
            position="relative"
            borderRadius="xl"
            p={4}
            bg={colors.gradient}
            boxShadow={colors.shadowLg}
          >
            <Spinner size="xl" color="white" />
          </Box>
          <Text fontSize="lg" fontWeight="medium" color={colors.text}>Loading MAPIT AI...</Text>
        </VStack>
      </Box>
    );
  }

  return (
    <Box bg={colors.bg} minH="100vh" py={{ base: 12, md: 20 }} position="relative" overflow="hidden">
      {/* Background gradient overlay */}
      <Box
        position="absolute"
        top={0}
        left={0}
        right={0}
        bottom={0}
        bg={colors.gradient}
        opacity={0.05}
        zIndex={0}
      />
      
      <Container maxW="container.sm" position="relative" zIndex={1} px={{ base: 4, md: 6 }}>
        <VStack spacing={{ base: 8, md: 12 }} textAlign="center">
          {/* Logo and Title Section */}
          <VStack spacing={{ base: 6, md: 8 }}>
            <Box
              position="relative"
              borderRadius="2xl"
              p={{ base: 4, md: 6 }}
              bg={colors.gradient}
              boxShadow={colors.shadowLg}
              _before={{
                content: '""',
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                borderRadius: '2xl',
                background: colors.gradient,
                opacity: 0.8,
                zIndex: -1,
              }}
            >
              <Image
                src={mapitLogo}
                alt="Mapit AI Logo"
                boxSize={{ base: "90px", md: "132px" }}
                objectFit="contain"
                borderRadius="xl"
              />
            </Box>
            
            <VStack spacing={4}>
              <Heading
                as="h1"
                size={{ base: "2xl", md: "3xl" }}
                bgGradient="linear(to-r, ai.primary.500, ai.accent.500)"
                bgClip="text"
                fontWeight="bold"
                letterSpacing="tight"
              >
                MAPIT AI
              </Heading>
              <Text
                fontSize={{ base: "lg", md: "xl" }}
                fontWeight="medium"
                color={colors.text + '80'}
                textTransform="uppercase"
                letterSpacing="wide"
                mt={-1}
              >
                Domain Expert Tool
              </Text>
              <HStack spacing={3} flexWrap="wrap" justify="center">
                <EuHorizonLogo height={{ base: '40px', md: '48px' }} tooltipPlacement="bottom" />
                <DataRefreshBadge dateLabel={LAST_DATA_REFRESH} />
              </HStack>
            </VStack>
          </VStack>

          {/* Auth Form */}
          <Box 
            w="100%"
            maxW="400px"
            p={{ base: 6, md: 8 }}
            bg={colors.cardBg}
            borderRadius="2xl"
            border="1px solid"
            borderColor={colors.cardBorder}
            boxShadow={colors.shadowLg}
            backdropFilter="blur(10px)"
          >
            <VStack spacing={6} align="stretch">
              <Heading 
                as="h2" 
                size={{ base: "lg", md: "xl" }}
                color={colors.text}
                textAlign="center"
                fontWeight="bold"
              >
                {isSignUp ? 'Create Account' : 'Sign In'}
              </Heading>
              
              <form onSubmit={handleSubmit}>
                <VStack spacing={4} align="stretch">
                  <FormControl isRequired>
                    <FormLabel fontSize={{ base: "sm", md: "md" }} color={colors.text}>
                      Email
                    </FormLabel>
                    <Input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="Enter your email"
                      size={{ base: "md", md: "lg" }}
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
                  </FormControl>
                  
                  <FormControl isRequired>
                    <FormLabel fontSize={{ base: "sm", md: "md" }} color={colors.text}>
                      Password
                    </FormLabel>
                    <Input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter your password"
                      size={{ base: "md", md: "lg" }}
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
                  </FormControl>
                  
                  {!isSignUp && (
                    <HStack justify="space-between" align="center">
                      <Checkbox
                        isChecked={rememberMe}
                        onChange={(e) => setRememberMe(e.target.checked)}
                        colorScheme="blue"
                        size="md"
                      >
                        <Text fontSize="sm" color={colors.text}>
                          Remember me
                        </Text>
                      </Checkbox>
                    </HStack>
                  )}
                  
                  <Button
                    type="submit"
                    bg={colors.gradient}
                    color="white"
                    size={{ base: "md", md: "lg" }}
                    leftIcon={isSignUp ? <FiUserPlus /> : <FiLogIn />}
                    isLoading={loading}
                    loadingText={isSignUp ? "Creating Account..." : "Signing In..."}
                    isDisabled={loading}
                    _hover={{ 
                      bg: colors.gradientDark,
                      transform: 'translateY(-2px)',
                      boxShadow: colors.shadowLg,
                    }}
                    _active={{
                      transform: 'translateY(0)',
                    }}
                    px={{ base: 8, md: 10 }}
                    py={{ base: 4, md: 6 }}
                    fontSize={{ base: "md", md: "lg" }}
                    fontWeight="semibold"
                    borderRadius="xl"
                    transition="all 0.2s ease-in-out"
                  >
                    {isSignUp ? 'Create Account' : 'Sign In'}
                  </Button>
                </VStack>
              </form>

              <Divider borderColor={colors.cardBorder} />

              <VStack spacing={3}>
                <Text fontSize={{ base: "sm", md: "md" }} color={colors.text + '80'}>
                  {isSignUp ? 'Already have an account?' : "Don't have an account?"}
                </Text>
                <Button
                  variant="ghost"
                  onClick={() => setIsSignUp(!isSignUp)}
                  color={colors.primary}
                  _hover={{
                    bg: colors.hoverBg,
                    transform: 'translateY(-1px)',
                  }}
                  fontSize={{ base: "sm", md: "md" }}
                  fontWeight="medium"
                >
                  {isSignUp ? 'Sign In Instead' : 'Create Account'}
                </Button>
              </VStack>
            </VStack>
          </Box>
        </VStack>
      </Container>
    </Box>
  );
};