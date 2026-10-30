import {
  Box,
  Container,
  Heading,
  Text,
  VStack,
  Button,
  HStack,
  Image,
  Spinner,
  Icon,
} from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';
import { FiZap, FiCpu, FiDatabase, FiGlobe } from 'react-icons/fi';
import { useAuth } from '../contexts/AuthContext';
import { useThemeColors } from '../hooks/useThemeColors';
import mapitLogo from '../assets/mapit_logo_no_bg.png';
import { EuHorizonLogo } from './EuHorizonLogo';
import { DataRefreshBadge } from './DataRefreshBadge';

const LAST_DATA_REFRESH = '27 May 2026';

export const LandingPage = () => {
  const colors = useThemeColors();
  const { currentUser, loading } = useAuth();

  if (loading) {
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
      
      <Container maxW="container.xl" position="relative" zIndex={1} px={{ base: 4, md: 6 }}>
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
                mt={0}
              >
                Domain Expert Tool
              </Text>
              <HStack spacing={3} flexWrap="wrap" justify="center">
                <EuHorizonLogo height={{ base: '40px', md: '48px' }} tooltipPlacement="bottom" />
                <DataRefreshBadge dateLabel={LAST_DATA_REFRESH} />
              </HStack>
            </VStack>
          </VStack>
          
          <Text 
            fontSize={{ base: "lg", md: "xl" }} 
            color={colors.text} 
            maxW="3xl" 
            lineHeight="tall" 
            fontWeight="medium"
            px={{ base: 2, md: 0 }}
          >
            Empowering domain experts with advanced AI-driven insights—bridging cutting-edge technology with deep subject expertise for EU funding opportunities.
          </Text>

          {/* Feature Icons */}
          <HStack spacing={{ base: 4, md: 8 }} mt={8} flexWrap="wrap" justify="center">
            <VStack spacing={2} minW={{ base: "80px", md: "auto" }}>
              <Box
                p={{ base: 3, md: 4 }}
                borderRadius="xl"
                bg={colors.gradientLight}
                color={colors.primary}
                boxShadow={colors.shadow}
              >
                <Icon as={FiCpu} boxSize={{ base: 5, md: 6 }} />
              </Box>
              <Text fontSize={{ base: "xs", md: "sm" }} fontWeight="medium" color={colors.text}>AI Powered</Text>
            </VStack>
            <VStack spacing={2} minW={{ base: "80px", md: "auto" }}>
              <Box
                p={{ base: 3, md: 4 }}
                borderRadius="xl"
                bg={colors.gradientLight}
                color={colors.primary}
                boxShadow={colors.shadow}
              >
                <Icon as={FiDatabase} boxSize={{ base: 5, md: 6 }} />
              </Box>
              <Text fontSize={{ base: "xs", md: "sm" }} fontWeight="medium" color={colors.text}>Smart Data</Text>
            </VStack>
            <VStack spacing={2} minW={{ base: "80px", md: "auto" }}>
              <Box
                p={{ base: 3, md: 4 }}
                borderRadius="xl"
                bg={colors.gradientLight}
                color={colors.primary}
                boxShadow={colors.shadow}
              >
                <Icon as={FiGlobe} boxSize={{ base: 5, md: 6 }} />
              </Box>
              <Text fontSize={{ base: "xs", md: "sm" }} fontWeight="medium" color={colors.text}>EU Focus</Text>
            </VStack>
          </HStack>

          <HStack spacing={6}>
            {currentUser ? (
              <Button
                as={RouterLink}
                to="/chat"
                size={{ base: "md", md: "lg" }}
                bg={colors.gradient}
                color="white"
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
                leftIcon={<FiZap />}
              >
                Go to Chat
              </Button>
            ) : (
              <Button
                as={RouterLink}
                to="/auth"
                size={{ base: "md", md: "lg" }}
                bg={colors.gradient}
                color="white"
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
                leftIcon={<FiZap />}
              >
                Get Started
              </Button>
            )}
          </HStack>

          {/* About Section */}
          <Box 
            maxW="4xl" 
            mt={{ base: 12, md: 16 }}
            p={{ base: 6, md: 8 }}
            bg={colors.cardBg}
            borderRadius="2xl"
            border="1px solid"
            borderColor={colors.cardBorder}
            boxShadow={colors.shadow}
            mx={{ base: 2, md: 0 }}
          >
            <VStack spacing={{ base: 4, md: 6 }} align="stretch">
              <Heading 
                as="h2" 
                size={{ base: "lg", md: "xl" }}
                color={colors.text}
                textAlign="center"
                fontWeight="bold"
              >
                About MAPIT AI
              </Heading>
              <Text 
                fontSize={{ base: "md", md: "lg" }} 
                color={colors.text} 
                lineHeight="tall" 
                textAlign="center"
                px={{ base: 2, md: 0 }}
              >
                The MAPIT AI Expert tool is a core part of the MAPIT project, designed to integrate domain-specific knowledge with state-of-the-art AI. By leveraging a unique blend of technical expertise and advanced algorithms, we empower experts in various domains to extract, analyze, and apply insights with greater efficiency.
              </Text>
              <Text 
                fontSize={{ base: "md", md: "lg" }} 
                color={colors.text} 
                lineHeight="tall" 
                textAlign="center"
                px={{ base: 2, md: 0 }}
              >
                Whether you are a researcher, a professional, or simply curious about the intersection of AI and domain expertise, our platform provides a comprehensive suite of tools to support your journey in EU funding opportunities.
              </Text>
            </VStack>
          </Box>
        </VStack>
      </Container>
    </Box>
  );
}; 