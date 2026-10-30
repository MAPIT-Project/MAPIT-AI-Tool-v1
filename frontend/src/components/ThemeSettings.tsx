import React from 'react';
import {
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  IconButton,
  useToast,
  HStack,
  Text,
  Box,
} from '@chakra-ui/react';
import { FiSettings, FiSun, FiMoon } from 'react-icons/fi';
import { useTheme } from '../contexts/ThemeContext';
import { useThemeColors } from '../hooks/useThemeColors';

export const ThemeSettings: React.FC = () => {
  const { theme, setTheme } = useTheme();
  const toast = useToast();
  const colors = useThemeColors();

  const handleThemeChange = (newTheme: 'light' | 'dark') => {
    setTheme(newTheme);
    toast({
      title: 'Theme updated',
      description: `${newTheme.charAt(0).toUpperCase() + newTheme.slice(1)} theme applied`,
      status: 'success',
      duration: 2000,
      isClosable: true,
    });
  };

  return (
    <Menu>
      <MenuButton
        as={IconButton}
        aria-label="Theme settings"
        icon={<FiSettings />}
        variant="ghost"
        size={{ base: "sm", md: "md" }}
        borderRadius="lg"
        _hover={{
          bg: colors.hoverBg,
          transform: 'translateY(-1px)',
        }}
        transition="all 0.2s ease-in-out"
      />
      <MenuList
        bg={colors.cardBg}
        borderColor={colors.cardBorder}
        borderRadius="xl"
        boxShadow={colors.shadowLg}
        minW="180px"
      >
        <MenuItem 
          onClick={() => handleThemeChange('light')}
          _hover={{
            bg: colors.hoverBg,
          }}
          borderRadius="lg"
          mx={2}
          my={1}
        >
          <HStack spacing={3} w="100%">
            <Box
              p={2}
              borderRadius="md"
              bg={colors.gradientLight}
              color={colors.primary}
            >
              <FiSun size={16} />
            </Box>
            <Text fontWeight="medium" color={colors.text}>Light Mode</Text>
            {theme === 'light' && (
              <Box
                ml="auto"
                p={1}
                borderRadius="full"
                bg={colors.primary}
                color="white"
                fontSize="xs"
                fontWeight="bold"
              >
                ✓
              </Box>
            )}
          </HStack>
        </MenuItem>
        <MenuItem 
          onClick={() => handleThemeChange('dark')}
          _hover={{
            bg: colors.hoverBg,
          }}
          borderRadius="lg"
          mx={2}
          my={1}
        >
          <HStack spacing={3} w="100%">
            <Box
              p={2}
              borderRadius="md"
              bg={colors.gradientLight}
              color={colors.primary}
            >
              <FiMoon size={16} />
            </Box>
            <Text fontWeight="medium" color={colors.text}>Dark Mode</Text>
            {theme === 'dark' && (
              <Box
                ml="auto"
                p={1}
                borderRadius="full"
                bg={colors.primary}
                color="white"
                fontSize="xs"
                fontWeight="bold"
              >
                ✓
              </Box>
            )}
          </HStack>
        </MenuItem>
      </MenuList>
    </Menu>
  );
}; 